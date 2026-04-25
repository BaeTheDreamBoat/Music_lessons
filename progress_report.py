"""Adaptive note selection and per-note statistics for all lesson types."""

import json
import os
import random
import time
from collections import defaultdict
from datetime import datetime
import tkinter as tk

from music_lessons import (
    NOTE_STATS_FILE,
    same_midi, save_config, save_lesson_stats,
    parse_note, note_to_midi, SHARP_TO_FLAT,
)


def build_sequence(cfg, mode, pool, duration_s):
    """Return a weighted sequence large enough to cover the full lesson duration."""
    stats = cfg.setdefault(f"note_stats_{mode}", {})

    expanded = []
    seen: set[int] = set()
    for note in pool:
        midi = note_to_midi(note)
        if midi not in seen:
            seen.add(midi)
            name, oct_ = parse_note(note)
            if name in SHARP_TO_FLAT:
                expanded.append(note)
                expanded.append(f"{SHARP_TO_FLAT[name]}{oct_}")
            else:
                expanded.append(note)

    # Buffer: assume ~1 note per second at fastest; add headroom
    num_notes = max(200, int(duration_s * 2))

    seq: list[str] = []
    recent: list[int] = []
    for _ in range(num_notes):
        available = [n for n in expanded if note_to_midi(n) not in recent] or expanded
        weights   = [stats.get(n, {}).get("avg_time", 5.0) for n in available]
        chosen    = random.choices(available, weights=weights, k=1)[0]
        seq.append(chosen)
        recent.append(note_to_midi(chosen))
        if len(recent) > 2:
            recent.pop(0)
    return seq


def update_note_stats(cfg, mode, note, elapsed):
    """Update per-note adaptive stats after a correct note is played."""
    stats = cfg.setdefault(f"note_stats_{mode}", {})
    if note not in stats:
        stats[note] = {"avg_time": 5.0, "count": 0, "win_streak": 0, "loss_streak": 0}
    s   = stats[note]
    avg = s["avg_time"]
    capped = min(elapsed, 5.0)
    if capped > avg:
        s["win_streak"]  = 0
        s["loss_streak"] = min(s["loss_streak"] + 1, 3)
        streak_mult      = s["loss_streak"] / 3
        adjusted         = avg + (capped - avg) * streak_mult
    else:
        s["loss_streak"] = 0
        s["win_streak"]  = min(s["win_streak"] + 1, 3)
        streak_mult      = s["win_streak"] / 3
        adjusted         = avg - (avg - capped) * streak_mult
    count         = s["count"]
    s["avg_time"] = (avg * count + adjusted) / (count + 1)
    s["count"]   += 1
    save_config(cfg)


class BasLesson:
    """Shared audio-listening loop inherited by all lesson types."""

    _note_hold_refund = True  # False in identify (button-press) lessons

    def __init__(self, app):
        self.app               = app
        self._target           = None
        self._hold_start       = None
        self._note_start_time  = None
        self._idx              = 0
        self._seq: list[str]   = []
        self._mode             = ""
        self._bg               = None
        self._lesson_start_time          = None
        self._lesson_duration_s          = 0.0
        self._original_lesson_duration_s = 0.0
        self._notes_completed            = 0
        self._note_times                 = []
        self._note_tone_duration         = 0.0
        self._lesson_ended       = False
        self._period_var         = None
        self._graph_frame        = None
        self._playlist_callback   = None
        self._playlist_next_label = None
        self._pending_pause       = 0.0

    # ── Countdown + start ─────────────────────────────────────────────────────

    def _begin(self, duration_s):
        delay = int(round(self.app.cfg.get("startup_delay", 3)))
        if delay <= 0:
            self._draw_next()
            self._start_lesson_timer(duration_s)
            return
        self._countdown_lbl = tk.Label(
            self._bg, text=str(delay),
            font=("Arial", 120, "bold"), bg="white", fg="#333333",
        )
        self._countdown_lbl.place(relx=0.5, rely=0.5, anchor="center")
        self.app.root.after(1000, lambda: self._countdown_tick(delay - 1, duration_s))

    def _countdown_tick(self, remaining, duration_s):
        try:
            if not self._bg.winfo_exists():
                return
        except Exception:
            return
        if remaining <= 0:
            try:
                self._countdown_lbl.destroy()
            except Exception:
                pass
            self._draw_next()
            self._start_lesson_timer(duration_s)
            return
        try:
            self._countdown_lbl.config(text=str(remaining))
        except Exception:
            pass
        self.app.root.after(1000, lambda: self._countdown_tick(remaining - 1, duration_s))

    # ── Lesson timer ──────────────────────────────────────────────────────────

    def _start_lesson_timer(self, duration_s):
        self._lesson_duration_s          = duration_s
        self._original_lesson_duration_s = duration_s
        self._lesson_start_time = time.monotonic() + self._pending_pause
        self._pending_pause     = 0.0
        self._lesson_ended      = False
        self._notes_completed   = 0
        self._note_times        = []
        self._note_tone_duration = 0.0
        self._time_tick()

    def _add_time(self, seconds):
        self._lesson_duration_s += seconds
        try:
            self._prog['maximum'] = self._lesson_duration_s
        except Exception:
            pass

    def _pause_for_tone(self):
        """Pause the lesson clock for the tone duration without affecting the lesson's total length."""
        tone_duration = self.app.cfg.get("tone_duration", 1.5)
        self._note_tone_duration = tone_duration
        if self._lesson_start_time is not None:
            self._lesson_start_time += tone_duration
        else:
            self._pending_pause += tone_duration

    def _time_tick(self):
        if self._lesson_ended:
            return
        try:
            if not self._bg.winfo_exists():
                return
        except Exception:
            return
        elapsed = max(0.0, time.monotonic() - self._lesson_start_time)
        try:
            self._prog['value'] = min(elapsed, self._lesson_duration_s)
        except Exception:
            pass
        if elapsed >= self._lesson_duration_s:
            self._lesson_ended = True
            self._complete()
            return
        self.app.root.after(500, self._time_tick)

    # ── Audio detection ───────────────────────────────────────────────────────

    def _listen(self, target):
        self._target     = target
        self._hold_start = None
        dur = self.app.cfg["note_duration"]
        thr = self.app.cfg["mic_threshold"]
        self._poll(dur, thr)

    def _poll(self, dur, thr):
        if self._lesson_ended:
            return
        try:
            if not self._bg.winfo_exists():
                return
        except Exception:
            return
        if self.app._vol > thr and same_midi(self.app._note, self._target):
            if self._hold_start is None:
                self._hold_start = time.monotonic()
            if time.monotonic() - self._hold_start >= dur:
                self._hit()
                return
        else:
            self._hold_start = None
        self.app.root.after(50, lambda: self._poll(dur, thr))

    # ── Progression ───────────────────────────────────────────────────────────

    def _hit(self):
        if self._lesson_ended:
            return
        self._notes_completed += 1
        elapsed = time.monotonic() - (self._note_start_time or time.monotonic())
        response_time = max(0.1, elapsed - self._note_tone_duration)
        self._note_tone_duration = 0.0
        self._note_times.append(response_time)
        update_note_stats(self.app.cfg, self._mode, self._target, response_time)
        refund = 0.4  # green flash duration
        if self._note_hold_refund:
            refund += self.app.cfg["note_duration"]
        self._add_time(refund)
        self._bg.config(bg="#32cd32")
        self._flash_widgets()
        self.app.root.after(400, self._advance)

    def _flash_widgets(self):
        """Override to flash mode-specific widgets on correct note."""

    def _advance(self):
        if self._lesson_ended:
            return
        self._idx += 1
        self._bg.config(bg="white")
        self._reset_widgets()
        self._draw_next()

    def _reset_widgets(self):
        """Override to reset mode-specific widget colours after flash."""

    def _draw_next(self):
        raise NotImplementedError

    # ── Completion screen ─────────────────────────────────────────────────────

    def _complete(self):
        self._lesson_ended = True
        if self._note_times:
            avg_seconds = sum(self._note_times) / len(self._note_times)
            avg_per_min = round(60.0 / avg_seconds, 1)
        else:
            avg_per_min = 0.0

        save_lesson_stats(self._mode, avg_per_min)

        self._bg.config(bg="white")
        for w in self._bg.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        tk.Label(self._bg, text="Lesson Complete!", font=("Arial", 36, "bold"),
                 bg="white", fg="#228b22").pack(pady=(10, 2))
        tk.Label(self._bg, text=f"Avg notes/min: {avg_per_min}",
                 font=("Arial", 18), bg="white").pack()

        toggle_frame = tk.Frame(self._bg, bg="white")
        toggle_frame.pack(pady=6)
        self._period_var = tk.StringVar(value="current")
        for label, value in (("Current", "current"), ("Week", "week"), ("Month", "month"), ("Year", "year")):
            tk.Radiobutton(
                toggle_frame, text=label, variable=self._period_var, value=value,
                command=self._draw_stats_graph, bg="white", font=("Arial", 11),
                indicatoron=False, padx=10, pady=4,
            ).pack(side=tk.LEFT, padx=2)

        self._graph_frame = tk.Frame(self._bg, bg="white")
        self._graph_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))

        btn_frame = tk.Frame(self._bg, bg="white")
        btn_frame.pack(pady=6)
        tk.Button(btn_frame, text="← Menu", command=self.app.show_menu).pack(side=tk.LEFT, padx=6)
        if self._playlist_callback is not None:
            cb         = self._playlist_callback
            self._playlist_callback = None
            next_label = self._playlist_next_label
            btn_text   = f"Next: {next_label} →" if next_label else "Finish →"
            tk.Button(btn_frame, text=btn_text, bg="#1a5276", fg="white",
                      font=("Arial", 11, "bold"), command=cb).pack(side=tk.LEFT, padx=6)

        self._draw_stats_graph()

    def _draw_stats_graph(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from datetime import timedelta

        for w in self._graph_frame.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        records = []
        if os.path.exists(NOTE_STATS_FILE):
            with open(NOTE_STATS_FILE) as f:
                records = json.load(f)

        records = [r for r in records if r.get("mode") == self._mode]

        if not records:
            tk.Label(self._graph_frame, text="No history yet.",
                     font=("Arial", 12), bg="white", fg="#888888").pack(expand=True)
            return

        period = self._period_var.get()
        today  = datetime.now().date()

        if period == "current":
            # Last 10 individual entries
            subset = records[-10:]
            keys   = [f"{r['date']}\n{r['time'][:5]}" for r in subset]
            values = [r["avg_notes_per_min"] for r in subset]
            title  = "Last 10 Sessions"

        elif period == "week":
            # Daily averages for the past 7 days
            cutoff  = today - timedelta(days=6)
            subset  = [r for r in records
                       if datetime.strptime(r["date"], "%Y-%m-%d").date() >= cutoff]
            grouped = defaultdict(list)
            for r in subset:
                grouped[r["date"]].append(r["avg_notes_per_min"])
            # Fill all 7 days so gaps show clearly
            all_days = [(cutoff + timedelta(days=i)).strftime("%Y-%m-%d")
                        for i in range(7)]
            keys   = all_days
            values = [sum(grouped[d]) / len(grouped[d]) if grouped[d] else 0
                      for d in all_days]
            # Shorten labels to Mon/Tue etc.
            keys   = [datetime.strptime(d, "%Y-%m-%d").strftime("%a %-d") for d in all_days]
            title  = "Daily Average — Past Week"

        elif period == "month":
            # Weekly averages for the past 4 weeks
            cutoff  = today - timedelta(weeks=4)
            subset  = [r for r in records
                       if datetime.strptime(r["date"], "%Y-%m-%d").date() >= cutoff]
            grouped = defaultdict(list)
            for r in subset:
                d   = datetime.strptime(r["date"], "%Y-%m-%d").date()
                # ISO week key: "Apr W3" style
                key = d.strftime("%b W") + str((d.day - 1) // 7 + 1)
                grouped[key].append(r["avg_notes_per_min"])
            keys   = sorted(grouped,
                            key=lambda k: next(
                                r["date"] for r in subset
                                if datetime.strptime(r["date"], "%Y-%m-%d").date().strftime("%b W")
                                   + str((datetime.strptime(r["date"], "%Y-%m-%d").date().day - 1) // 7 + 1) == k
                            ))
            values = [sum(grouped[k]) / len(grouped[k]) for k in keys]
            title  = "Weekly Average — Past Month"

        else:  # year
            # Monthly averages for the past 12 months
            cutoff  = today.replace(day=1)
            # Go back 11 months from the current month start
            month   = cutoff.month
            year    = cutoff.year
            months  = []
            for _ in range(12):
                months.append((year, month))
                month -= 1
                if month == 0:
                    month = 12
                    year -= 1
            months.reverse()
            grouped = defaultdict(list)
            for r in records:
                d = datetime.strptime(r["date"], "%Y-%m-%d").date()
                grouped[(d.year, d.month)].append(r["avg_notes_per_min"])
            keys   = [datetime(y, m, 1).strftime("%b %y") for y, m in months]
            values = [sum(grouped[(y, m)]) / len(grouped[(y, m)]) if grouped[(y, m)] else 0
                      for y, m in months]
            title  = "Monthly Average — Past Year"

        fig = Figure(figsize=(5, 2.6), dpi=90, facecolor="white")
        ax  = fig.add_subplot(111)
        xs  = range(len(keys))
        ax.plot(xs, values, color="#228b22", marker="o", linewidth=2, markersize=5)
        ax.fill_between(xs, values, alpha=0.15, color="#228b22")
        ax.set_xticks(list(xs))
        ax.set_xticklabels(keys, rotation=35, ha="right", fontsize=7)
        ax.set_ylabel("Avg notes/min", fontsize=9)
        ax.set_title(title, fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self._graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

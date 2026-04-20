"""Adaptive note selection and per-note statistics for all lesson types."""

import random
import time
import tkinter as tk

from music_lessons import same_midi, save_config, parse_note, note_to_midi, SHARP_TO_FLAT


def build_sequence(cfg, mode, pool, num_notes):
    """Return a weighted, 2-note-cooldown sequence drawn from the expanded pool."""
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

    def __init__(self, app):
        self.app              = app
        self._target          = None
        self._hold_start      = None
        self._note_start_time = None
        self._idx             = 0
        self._seq: list[str]  = []
        self._mode            = ""
        self._bg              = None

    # ── Audio detection ───────────────────────────────────────────────────────

    def _listen(self, target):
        self._target     = target
        self._hold_start = None
        dur = self.app.cfg["note_duration"]
        thr = self.app.cfg["mic_threshold"]
        self._poll(dur, thr)

    def _poll(self, dur, thr):
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
        elapsed = time.monotonic() - (self._note_start_time or time.monotonic())
        update_note_stats(self.app.cfg, self._mode, self._target, elapsed)
        self._bg.config(bg="#32cd32")
        self._flash_widgets()
        self.app.root.after(400, self._advance)

    def _flash_widgets(self):
        """Override to flash mode-specific widgets on correct note."""

    def _advance(self):
        self._idx += 1
        self._bg.config(bg="white")
        self._reset_widgets()
        self._draw_next()

    def _reset_widgets(self):
        """Override to reset mode-specific widget colours after flash."""

    def _draw_next(self):
        raise NotImplementedError

    def _complete(self):
        self._bg.config(bg="white")
        for w in self._bg.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        tk.Label(self._bg, text="Lesson Complete!", font=("Arial", 42, "bold"),
                 bg="white", fg="#228b22").pack(expand=True)
        tk.Button(self._bg, text="\u2190 Menu", command=self.app.show_menu).pack(pady=10)

#!/usr/bin/env python3
"""Music Lessons - Interactive note recognition trainer."""

import tkinter as tk
from tkinter import ttk
import json
import os
import threading
import random
import time
import numpy as np
import pyaudio
from PIL import Image, ImageTk

# ─── Constants ────────────────────────────────────────────────────────────────

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
IMAGES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

NOTE_NAMES    = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
DIATONIC      = ['C','D','E','F','G','A','B']
ALL_NOTES     = [f"{n}{o}" for o in range(0, 9) for n in NOTE_NAMES]
SHARP_TO_FLAT = {'C#':'Db','D#':'Eb','F#':'Gb','G#':'Ab','A#':'Bb'}
FLAT_TO_SHARP = {v: k for k, v in SHARP_TO_FLAT.items()}

DEFAULT_CONFIG = {
    "lower_note":            "C4",
    "upper_note":            "B5",
    "num_notes":             10,
    "note_duration":         2.0,
    "mic_threshold":         0.02,
    "mic_device_index":      None,
    "note_scale":            1.0,
    "a4_y":                  230,
    "step_height":           14.0,
    "sharp_x_offset":        -30,
    "sharp_y_offset":        -5,
    "flat_x_offset":         -28,
    "flat_y_offset":          0,
    "ledger_above_y_offset":  0,
    "ledger_below_y_offset":  0,
}

CANVAS_W = 800
CANVAS_H = 440

# ─── Music utilities ──────────────────────────────────────────────────────────

def parse_note(s):
    """'A#4'->('A#',4), 'Bb4'->('Bb',4), 'C4'->('C',4)"""
    if len(s) >= 2 and s[1] == '#':
        return s[:2], int(s[2:])
    if len(s) >= 3 and s[1] == 'b':   # Bb4, Db4, etc. (not B4 — len only 2)
        return s[:2], int(s[2:])
    return s[0], int(s[1:])

def note_to_midi(s):
    name, oct_ = parse_note(s)
    sharp = FLAT_TO_SHARP.get(name, name)
    return (oct_ + 1) * 12 + NOTE_NAMES.index(sharp)

def midi_to_note(m):
    return f"{NOTE_NAMES[m % 12]}{m // 12 - 1}"

def freq_to_note(freq):
    if freq <= 0:
        return None
    midi = round(12 * np.log2(freq / 440.0) + 69)
    return midi_to_note(midi)

def staff_pos(s):
    """Diatonic staff position: E4=0, F4=1, G4=2, A4=3, B4=4, C5=5 …"""
    name, oct_ = parse_note(s)
    base = name[0]
    if base not in DIATONIC:
        return None
    return (oct_ - 4) * 7 + DIATONIC.index(base) - 2

def is_sharp(s):
    name, _ = parse_note(s)
    return '#' in name

def is_flat(s):
    name, _ = parse_note(s)
    return 'b' in name   # lowercase only — 'B' natural has no lowercase b

def same_midi(a, b):
    if not a or not b:
        return False
    try:
        return note_to_midi(a) == note_to_midi(b)
    except (ValueError, IndexError):
        return False

# ─── Config ───────────────────────────────────────────────────────────────────

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            cfg.update(json.load(f))
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

# ─── Audio engine ─────────────────────────────────────────────────────────────

class AudioEngine:
    CHUNK = 4096
    RATE  = 44100

    def __init__(self):
        self.pa      = pyaudio.PyAudio()
        self.stream  = None
        self._vol    = 0.0
        self._note   = None
        self._lock   = threading.Lock()

    def get_input_devices(self):
        devs = []
        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                devs.append((i, info['name']))
        return devs

    def start(self, device_index=None):
        self.stream = self.pa.open(
            format=pyaudio.paFloat32, channels=1, rate=self.RATE,
            input=True, frames_per_buffer=self.CHUNK,
            stream_callback=self._cb,
            input_device_index=device_index,
        )
        self.stream.start_stream()

    def restart(self, device_index=None):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        self.start(device_index)

    def _cb(self, in_data, frame_count, time_info, status):
        samples = np.frombuffer(in_data, dtype=np.float32).copy()
        rms  = float(np.sqrt(np.mean(samples ** 2)))
        note = self._detect(samples) if rms > 0.005 else None
        with self._lock:
            self._vol  = rms
            self._note = note
        return (None, pyaudio.paContinue)

    def _detect(self, samples):
        samples -= samples.mean()
        corr  = np.correlate(samples, samples, mode='full')[len(samples) - 1:]
        d     = np.diff(corr)
        rises = np.where((d[:-1] < 0) & (d[1:] >= 0))[0]
        if not len(rises):
            return None
        start = rises[0] + 1
        if start >= len(corr):
            return None
        peak = int(np.argmax(corr[start:])) + start
        if peak == 0 or corr[peak] < 0.05 * corr[0]:
            return None
        freq = self.RATE / peak
        if not (60 < freq < 4200):
            return None
        return freq_to_note(freq)

    def get_state(self):
        with self._lock:
            return self._vol, self._note

    def stop(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.pa.terminate()

# ─── Application ──────────────────────────────────────────────────────────────

class App:
    def __init__(self, root):
        self.root   = root
        self.root.title("Music Lessons")
        self.root.geometry("920x740")
        self.cfg    = load_config()
        self.audio  = AudioEngine()
        self._input_devices = self.audio.get_input_devices()
        self.audio.start(self.cfg.get("mic_device_index"))
        self._imgs  = {}
        self._load_images()
        self._vol   = 0.0
        self._note  = None
        self._refs  = []          # PhotoImage keep-alive list
        self._game_cache = (None, {})
        self._mic_poll()
        self.show_menu()

    # ── Image loading ──────────────────────────────────────────────────────────

    def _load_images(self):
        self._imgs = {}
        self._game_cache = (None, {})
        staff_path = os.path.join(IMAGES_PATH, "staff.png")
        if not os.path.exists(staff_path):
            return
        raw_staff   = Image.open(staff_path).convert("RGBA")
        staff_scale = CANVAS_W / raw_staff.width
        note_mul    = float(self.cfg.get("note_scale", 1.0))

        new_h = int(raw_staff.height * staff_scale)
        self._imgs["staff"] = raw_staff.resize((CANVAS_W, new_h), Image.LANCZOS)

        for name in ("note", "line", "sharp", "flat"):
            p = os.path.join(IMAGES_PATH, f"{name}.png")
            if os.path.exists(p):
                img = Image.open(p).convert("RGBA")
                s   = staff_scale * note_mul
                self._imgs[name] = img.resize(
                    (max(1, int(img.width * s)), max(1, int(img.height * s))),
                    Image.LANCZOS,
                )

    # ── Mic polling ────────────────────────────────────────────────────────────

    def _mic_poll(self):
        self._vol, self._note = self.audio.get_state()
        try:
            self._redraw_mic_bar()
        except Exception:
            pass
        self.root.after(50, self._mic_poll)

    def _redraw_mic_bar(self):
        if not hasattr(self, '_mic_cv') or not self._mic_cv.winfo_exists():
            return
        W, H = 280, 26
        thresh = self.thr_var.get()
        fill_w  = min(int(self._vol / 0.2 * W), W)
        thr_x   = min(int(thresh  / 0.2 * W), W)
        c = self._mic_cv
        c.delete("all")
        c.create_rectangle(0, 0, fill_w, H, fill="#00cc00", outline="")
        c.create_rectangle(fill_w, 0, W, H, fill="#1a1a1a", outline="")
        c.create_line(thr_x, 0, thr_x, H, fill="red", width=2)
        if hasattr(self, '_note_lbl') and self._note_lbl.winfo_exists():
            self._note_lbl.config(text=self._note or "---")

    # ── Layout helpers ─────────────────────────────────────────────────────────

    def _clear(self):
        for w in self.root.winfo_children():
            w.destroy()
        self._refs = []

    # ── Main menu ──────────────────────────────────────────────────────────────

    def show_menu(self):
        self._clear()
        f = tk.Frame(self.root, padx=18, pady=10)
        f.pack(fill=tk.BOTH, expand=True)

        tk.Label(f, text="Music Lessons", font=("Arial", 22, "bold")).grid(
            row=0, column=0, columnspan=6, pady=10)

        # Note range
        tk.Label(f, text="Note Range:").grid(row=1, column=0, sticky='e')
        tk.Label(f, text="Lower:").grid(row=1, column=1, sticky='e')
        self.lo_var = tk.StringVar(value=self.cfg["lower_note"])
        ttk.Combobox(f, textvariable=self.lo_var, values=ALL_NOTES,
                     width=7, state='readonly').grid(row=1, column=2, padx=4)
        tk.Label(f, text="Upper:").grid(row=1, column=3, sticky='e')
        self.hi_var = tk.StringVar(value=self.cfg["upper_note"])
        ttk.Combobox(f, textvariable=self.hi_var, values=ALL_NOTES,
                     width=7, state='readonly').grid(row=1, column=4, padx=4)
        self.lo_var.trace_add("write", lambda *_: self._save_range())
        self.hi_var.trace_add("write", lambda *_: self._save_range())

        # Count & duration
        tk.Label(f, text="# Notes:").grid(row=2, column=0, sticky='e', pady=6)
        self.num_var = tk.IntVar(value=self.cfg["num_notes"])
        tk.Spinbox(f, from_=1, to=200, textvariable=self.num_var, width=5).grid(row=2, column=2)

        tk.Label(f, text="Duration (s):").grid(row=3, column=0, sticky='e', pady=4)
        self.dur_var = tk.DoubleVar(value=self.cfg["note_duration"])
        tk.Spinbox(f, from_=0.5, to=10.0, increment=0.5,
                   textvariable=self.dur_var, width=5).grid(row=3, column=2)

        # Mic device dropdown
        tk.Label(f, text="Mic Device:").grid(row=4, column=0, sticky='e', pady=4)
        dev_names   = [name for _, name in self._input_devices]
        saved_idx   = self.cfg.get("mic_device_index")
        current_dev = dev_names[0] if dev_names else ""
        for idx, name in self._input_devices:
            if idx == saved_idx:
                current_dev = name
                break
        self.mic_dev_var = tk.StringVar(value=current_dev)
        ttk.Combobox(f, textvariable=self.mic_dev_var, values=dev_names,
                     state='readonly', width=36).grid(
                     row=4, column=1, columnspan=4, sticky='w', padx=4)
        self.mic_dev_var.trace_add("write", lambda *_: self._on_mic_change())

        # Mic level bar
        tk.Label(f, text="Mic Level:").grid(row=5, column=0, sticky='e', pady=5)
        mic_row = tk.Frame(f)
        mic_row.grid(row=5, column=1, columnspan=5, sticky='w')
        self._mic_cv = tk.Canvas(mic_row, width=280, height=26, bg="#1a1a1a",
                                  highlightthickness=1)
        self._mic_cv.pack(side=tk.LEFT)
        self.thr_var = tk.DoubleVar(value=self.cfg["mic_threshold"])
        tk.Scale(mic_row, variable=self.thr_var, from_=0.0, to=0.2,
                 resolution=0.002, orient=tk.HORIZONTAL, length=200,
                 showvalue=False).pack(side=tk.LEFT, padx=8)
        self._note_lbl = tk.Label(mic_row, text="---", font=("Arial", 16, "bold"), width=5)
        self._note_lbl.pack(side=tk.LEFT)

        # Note image scale
        tk.Label(f, text="Note Scale:").grid(row=6, column=0, sticky='e', pady=4)
        self.ns_var = tk.DoubleVar(value=self.cfg.get("note_scale", 1.0))
        tk.Spinbox(f, from_=0.05, to=5.0, increment=0.05,
                   textvariable=self.ns_var, width=6).grid(row=6, column=2)
        tk.Button(f, text="Apply", command=self._apply_note_scale).grid(row=6, column=3, padx=4)

        # Mode selection
        ttk.Separator(f, orient='horizontal').grid(
            row=7, column=0, columnspan=6, sticky='ew', pady=6)
        tk.Label(f, text="Mode:", font=("Arial", 12, "bold")).grid(row=8, column=0, sticky='e')
        self.mode_var = tk.StringVar(value="Staff")
        tk.Radiobutton(f, text="Staff",   variable=self.mode_var, value="Staff"  ).grid(row=8, column=1, sticky='w')
        tk.Radiobutton(f, text="Letters", variable=self.mode_var, value="Letters").grid(row=8, column=2, sticky='w')
        tk.Button(f, text="Start", bg="#228b22", fg="white",
                  font=("Arial", 11, "bold"),
                  command=self._start_lesson).grid(row=8, column=5, padx=8)

        # Debug selection
        ttk.Separator(f, orient='horizontal').grid(
            row=9, column=0, columnspan=6, sticky='ew', pady=6)
        tk.Label(f, text="Debug:", font=("Arial", 12, "bold")).grid(row=10, column=0, sticky='e')
        self.dbg_var = tk.StringVar(value="Note on scale")
        opts = ["Note on scale", "sharp location", "flat location",
                "notes above scale", "notes below scale"]
        for i, opt in enumerate(opts):
            r, c = divmod(i, 3)
            tk.Radiobutton(f, text=opt, variable=self.dbg_var,
                           value=opt).grid(row=10+r, column=1+c, sticky='w')
        tk.Button(f, text="Start Debug", bg="#cc6600", fg="white",
                  command=self._start_debug).grid(row=11, column=5, padx=8)

    def _save_range(self):
        self.cfg["lower_note"] = self.lo_var.get()
        self.cfg["upper_note"] = self.hi_var.get()
        save_config(self.cfg)

    def _save_lesson_cfg(self):
        self.cfg["num_notes"]     = self.num_var.get()
        self.cfg["note_duration"] = self.dur_var.get()
        self.cfg["mic_threshold"] = self.thr_var.get()
        save_config(self.cfg)

    def _on_mic_change(self):
        name = self.mic_dev_var.get()
        for idx, n in self._input_devices:
            if n == name:
                self.cfg["mic_device_index"] = idx
                save_config(self.cfg)
                try:
                    self.audio.restart(idx)
                except Exception:
                    pass
                break

    def _apply_note_scale(self):
        self.cfg["note_scale"] = round(self.ns_var.get(), 4)
        save_config(self.cfg)
        self._load_images()

    # ── Lesson setup ───────────────────────────────────────────────────────────

    def _note_range(self):
        lo = note_to_midi(self.cfg["lower_note"])
        hi = note_to_midi(self.cfg["upper_note"])
        return [midi_to_note(m) for m in range(lo, hi + 1)]

    def _pick_display(self, sharp_note):
        """For chromatic notes, randomly choose sharp or flat spelling."""
        name, oct_ = parse_note(sharp_note)
        if name in SHARP_TO_FLAT and random.random() < 0.5:
            return f"{SHARP_TO_FLAT[name]}{oct_}"
        return sharp_note

    def _start_lesson(self):
        self._save_lesson_cfg()
        pool = self._note_range()
        if not pool:
            return
        n = self.cfg["num_notes"]
        self._idx  = 0
        self._mode = self.mode_var.get()
        stats      = self.cfg.setdefault(f"note_stats_{self._mode}", {})
        self._seq  = []
        recent: list[int] = []
        for _ in range(n):
            available = [note for note in pool if note_to_midi(note) not in recent] or pool
            weights   = [stats.get(str(note_to_midi(note)), {}).get("avg_time", 5.0) for note in available]
            chosen    = random.choices(available, weights=weights, k=1)[0]
            self._seq.append(self._pick_display(chosen))
            recent.append(note_to_midi(chosen))
            if len(recent) > 2:
                recent.pop(0)
        if self._mode == "Staff":
            self._staff_screen()
        else:
            self._letters_screen()

    # ── Staff lesson ───────────────────────────────────────────────────────────

    def _staff_screen(self):
        self._clear()
        self._bg = tk.Frame(self.root, bg="white")
        self._bg.pack(fill=tk.BOTH, expand=True)

        self._prog = ttk.Progressbar(self._bg, maximum=len(self._seq))
        self._prog.pack(fill=tk.X, padx=20, pady=6)

        self._cv = tk.Canvas(self._bg, bg="white", width=CANVAS_W)
        self._cv.pack(fill=tk.BOTH, expand=True)
        self._cv.bind("<Configure>", self._on_staff_resize)

        tk.Button(self._bg, text="← Menu", command=self.show_menu).pack(pady=4)
        self._draw_staff_note()

    def _compute_game_layout(self, canvas_h):
        """Return (sf, step_eff, a4_y_eff) scaled so B3–C7 fit in canvas_h."""
        MARGIN = 30
        a4_off   = self.cfg["a4_y"] - CANVAS_H // 2
        step     = self.cfg["step_height"]
        term_top = 16 * step - a4_off   # C7 (pos=19) distance above centre
        term_bot = a4_off + 6 * step    # B3 (pos=-3) distance below centre
        sf = (canvas_h // 2 - MARGIN) / max(term_top, term_bot, 1)
        return sf, step * sf, canvas_h // 2 + a4_off * sf

    def _get_game_imgs(self, sf):
        """Return images scaled by sf from the calibration base. Cached."""
        key = round(sf, 4)
        if self._game_cache[0] == key:
            return self._game_cache[1]
        scaled = {}
        for name, img in self._imgs.items():
            if name == "staff":
                w, h = img.width, max(1, int(img.height * sf))
            else:
                w = max(1, int(img.width * sf))
                h = max(1, int(img.height * sf))
            scaled[name] = img.resize((w, h), Image.LANCZOS)
        self._game_cache = (key, scaled)
        return scaled

    def _on_staff_resize(self, _event):
        if hasattr(self, '_seq') and hasattr(self, '_cv') and 0 <= self._idx < len(self._seq):
            self._render_staff_note(self._seq[self._idx])

    def _draw_staff_note(self):
        if self._idx >= len(self._seq):
            self._complete()
            return
        note = self._seq[self._idx]
        self._render_staff_note(note)
        self._prog['value'] = self._idx
        self._note_start_time = time.monotonic()
        self._listen(note)

    def _render_staff_note(self, note):
        c = self._cv
        c.delete("all")
        self._refs = []

        canvas_h = max(c.winfo_height(), 100)
        cx       = max(c.winfo_width(), CANVAS_W) // 2

        sf, step_eff, a4_y_eff = self._compute_game_layout(canvas_h)
        imgs = self._get_game_imgs(sf)

        def y_for(p):
            return a4_y_eff - (p - 3) * step_eff

        pos = staff_pos(note)
        ny  = y_for(pos) if pos is not None else a4_y_eff

        # Staff
        if "staff" in imgs:
            tk_s = ImageTk.PhotoImage(imgs["staff"])
            self._refs.append(tk_s)
            c.create_image(cx, canvas_h // 2, image=tk_s)

        # Ledger lines
        if "line" in imgs and pos is not None:
            loff_above = self.cfg["ledger_above_y_offset"] * sf
            loff_below = self.cfg["ledger_below_y_offset"] * sf
            if pos <= -2:
                lo_p = pos if pos % 2 == 0 else pos + 1
                for p in range(-2, lo_p - 1, -2):
                    tk_l = ImageTk.PhotoImage(imgs["line"])
                    self._refs.append(tk_l)
                    c.create_image(cx, y_for(p) + loff_below, image=tk_l)
            if pos >= 10:
                hi_p = pos if pos % 2 == 0 else pos - 1
                for p in range(10, hi_p + 1, 2):
                    tk_l = ImageTk.PhotoImage(imgs["line"])
                    self._refs.append(tk_l)
                    c.create_image(cx, y_for(p) + loff_above, image=tk_l)

        # Accidentals
        if is_sharp(note) and "sharp" in imgs:
            tk_sh = ImageTk.PhotoImage(imgs["sharp"])
            self._refs.append(tk_sh)
            c.create_image(cx + self.cfg["sharp_x_offset"] * sf,
                           ny  + self.cfg["sharp_y_offset"] * sf, image=tk_sh)
        elif is_flat(note) and "flat" in imgs:
            tk_fl = ImageTk.PhotoImage(imgs["flat"])
            self._refs.append(tk_fl)
            c.create_image(cx + self.cfg["flat_x_offset"] * sf,
                           ny  + self.cfg["flat_y_offset"] * sf, image=tk_fl)

        # Note head
        if "note" in imgs:
            tk_n = ImageTk.PhotoImage(imgs["note"])
            self._refs.append(tk_n)
            c.create_image(cx, ny, image=tk_n)

    # ── Letters lesson ─────────────────────────────────────────────────────────

    def _letters_screen(self):
        self._clear()
        self._bg = tk.Frame(self.root, bg="white")
        self._bg.pack(fill=tk.BOTH, expand=True)

        self._prog = ttk.Progressbar(self._bg, maximum=len(self._seq))
        self._prog.pack(fill=tk.X, padx=20, pady=6)

        self._lbl = tk.Label(self._bg, text="", font=("Arial", 80, "bold"), bg="white")
        self._lbl.pack(expand=True)

        tk.Button(self._bg, text="← Menu", command=self.show_menu).pack(pady=4)
        self._draw_letter_note()

    def _draw_letter_note(self):
        if self._idx >= len(self._seq):
            self._complete()
            return
        note = self._seq[self._idx]
        self._bg.config(bg="white")
        self._lbl.config(text=note, bg="white", fg="black")
        self._prog['value'] = self._idx
        self._note_start_time = time.monotonic()
        self._listen(note)

    # ── Note listening ─────────────────────────────────────────────────────────

    def _listen(self, target):
        self._target     = target
        self._hold_start = None
        duration  = self.cfg["note_duration"]
        threshold = self.cfg["mic_threshold"]
        self._poll(duration, threshold)

    def _poll(self, dur, thr):
        try:
            if not self._bg.winfo_exists():
                return
        except Exception:
            return

        if self._vol > thr and same_midi(self._note, self._target):
            if self._hold_start is None:
                self._hold_start = time.monotonic()
            if time.monotonic() - self._hold_start >= dur:
                self._hit()
                return
        else:
            self._hold_start = None

        self.root.after(50, lambda: self._poll(dur, thr))

    def _update_note_stats(self, note, elapsed):
        midi = note_to_midi(note)
        key  = str(midi)
        stats = self.cfg.setdefault(f"note_stats_{self._mode}", {})
        if key not in stats:
            stats[key] = {"avg_time": 5.0, "count": 0, "win_streak": 0, "loss_streak": 0}
        s   = stats[key]
        avg = s["avg_time"]
        capped = min(elapsed, 5.0)
        if capped > avg:
            s["win_streak"] = 0
            s["loss_streak"] = min(s["loss_streak"] + 1, 3)
            streak_mult = s["loss_streak"] / 3
            adjusted = avg + (capped - avg) * streak_mult
        else:
            s["loss_streak"] = 0
            s["win_streak"] = min(s["win_streak"] + 1, 3)
            streak_mult = s["win_streak"] / 3
            adjusted = avg - (avg - capped) * streak_mult
        count = s["count"]
        s["avg_time"] = (avg * count + adjusted) / (count + 1)
        s["count"] += 1
        save_config(self.cfg)

    def _hit(self):
        elapsed = time.monotonic() - getattr(self, '_note_start_time', time.monotonic())
        self._update_note_stats(self._target, elapsed)
        self._bg.config(bg="#32cd32")
        for w in (self._cv, self._lbl) if hasattr(self, '_lbl') else (self._cv,):
            try:
                w.config(bg="#32cd32")
            except Exception:
                pass
        self.root.after(400, self._advance)

    def _advance(self):
        self._idx += 1
        if self._mode == "Staff":
            self._bg.config(bg="white")
            try:
                self._cv.config(bg="white")
            except Exception:
                pass
            self._draw_staff_note()
        else:
            self._bg.config(bg="white")
            self._draw_letter_note()

    def _complete(self):
        self._bg.config(bg="white")
        for w in self._bg.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        tk.Label(self._bg, text="Lesson Complete!", font=("Arial", 42, "bold"),
                 bg="white", fg="#228b22").pack(expand=True)
        tk.Button(self._bg, text="← Menu", command=self.show_menu).pack(pady=10)

    # ── Debug helpers ──────────────────────────────────────────────────────────

    def _debug_frame(self, title, subtitle=""):
        self._clear()
        f = tk.Frame(self.root, bg="white")
        f.pack(fill=tk.BOTH, expand=True)
        tk.Label(f, text=title, font=("Arial", 14, "bold"), bg="white").pack(pady=5)
        if subtitle:
            tk.Label(f, text=subtitle, bg="white", wraplength=720).pack()
        c = tk.Canvas(f, bg="white", width=CANVAS_W, height=CANVAS_H)
        c.pack()
        return f, c

    def _blit_staff(self, c):
        if "staff" not in self._imgs:
            return
        tk_s = ImageTk.PhotoImage(self._imgs["staff"])
        if not hasattr(c, '_refs'):
            c._refs = []
        c._refs.append(tk_s)
        c.create_image(CANVAS_W // 2, CANVAS_H // 2, image=tk_s)

    # ── Debug: note on scale ───────────────────────────────────────────────────

    def _start_debug(self):
        {
            "Note on scale":    self._dbg_note_on_scale,
            "sharp location":   lambda: self._dbg_accidental("sharp"),
            "flat location":    lambda: self._dbg_accidental("flat"),
            "notes above scale":lambda: self._dbg_ledger("above"),
            "notes below scale":lambda: self._dbg_ledger("below"),
        }[self.dbg_var.get()]()

    def _dbg_note_on_scale(self):
        f, c = self._debug_frame(
            "Debug: Note on Scale",
            "Move A4 onto the correct staff position, then adjust offset until top note lands on C5."
        )
        state = {
            'a4_y':  self.cfg["a4_y"],
            'off':   int(self.cfg["step_height"] * 2),
        }
        W = CANVAS_W

        def redraw():
            c.delete("all")
            c._refs = []
            self._blit_staff(c)
            a4y = state['a4_y']
            c5y = a4y - state['off']
            for img, x, y, lbl in [
                (self._imgs.get("note"), W//2 - 40, a4y, "A4"),
                (self._imgs.get("note"), W//2 + 40, c5y, "C5"),
            ]:
                if img:
                    tk_n = ImageTk.PhotoImage(img)
                    c._refs.append(tk_n)
                    c.create_image(x, y, image=tk_n)
                    c.create_text(x - 30, y, text=lbl, font=("Arial", 11, "bold"))
            c.create_text(8, 8, anchor='nw',
                text=f"a4_y={a4y}  C5 offset={state['off']}  step={state['off']/2:.1f}px",
                font=("Arial", 10))

        redraw()

        bf = tk.Frame(f, bg="white"); bf.pack(pady=4)
        tk.Label(bf, text="A4:", bg="white").grid(row=0, column=0, padx=4)
        tk.Button(bf, text="▲", command=lambda: (state.__setitem__('a4_y', state['a4_y']-1), redraw())).grid(row=0, column=1)
        tk.Button(bf, text="▼", command=lambda: (state.__setitem__('a4_y', state['a4_y']+1), redraw())).grid(row=0, column=2)
        tk.Label(bf, text="   C5 offset:", bg="white").grid(row=0, column=3, padx=4)
        tk.Button(bf, text="▲", command=lambda: (state.__setitem__('off', max(2, state['off']-1)), redraw())).grid(row=0, column=4)
        tk.Button(bf, text="▼", command=lambda: (state.__setitem__('off', state['off']+1), redraw())).grid(row=0, column=5)

        def save():
            self.cfg["a4_y"]        = state['a4_y']
            self.cfg["step_height"] = state['off'] / 2.0
            save_config(self.cfg)
            self.show_menu()

        tk.Button(f, text="Save & Back", bg="#228b22", fg="white", command=save).pack(pady=5)

    # ── Debug: sharp / flat ────────────────────────────────────────────────────

    def _dbg_accidental(self, kind):
        f, c = self._debug_frame(
            f"Debug: {kind} location",
            f"Move the {kind} symbol to the correct position relative to the note (A4)."
        )
        xk, yk = f"{kind}_x_offset", f"{kind}_y_offset"
        state  = {'x': self.cfg[xk], 'y': self.cfg[yk]}
        W      = CANVAS_W
        nx, ny = W // 2, self.cfg["a4_y"]

        def redraw():
            c.delete("all")
            c._refs = []
            self._blit_staff(c)
            for img, x, y in [
                (self._imgs.get("note"), nx, ny),
                (self._imgs.get(kind),   nx + state['x'], ny + state['y']),
            ]:
                if img:
                    tk_i = ImageTk.PhotoImage(img)
                    c._refs.append(tk_i)
                    c.create_image(x, y, image=tk_i)
            c.create_text(8, 8, anchor='nw',
                text=f"x_offset={state['x']}  y_offset={state['y']}", font=("Arial", 10))

        redraw()

        bf = tk.Frame(f, bg="white"); bf.pack(pady=4)
        tk.Button(bf, text="◄", command=lambda: (state.__setitem__('x', state['x']-1), redraw())).grid(row=1, column=0)
        tk.Button(bf, text="▲", command=lambda: (state.__setitem__('y', state['y']-1), redraw())).grid(row=0, column=1)
        tk.Button(bf, text="▼", command=lambda: (state.__setitem__('y', state['y']+1), redraw())).grid(row=2, column=1)
        tk.Button(bf, text="►", command=lambda: (state.__setitem__('x', state['x']+1), redraw())).grid(row=1, column=2)

        def save():
            self.cfg[xk] = state['x']
            self.cfg[yk] = state['y']
            save_config(self.cfg)
            self.show_menu()

        tk.Button(f, text="Save & Back", bg="#228b22", fg="white", command=save).pack(pady=5)

    # ── Debug: ledger line above / below ──────────────────────────────────────

    def _dbg_ledger(self, direction):
        f, c = self._debug_frame(
            f"Debug: notes {direction} scale",
            f"Move the ledger line to its correct position {direction} the note."
        )
        key   = f"ledger_{direction}_y_offset"
        state = {'y': self.cfg.get(key, -15 if direction == "above" else 15)}
        W     = CANVAS_W
        H     = CANVAS_H
        nx, ny = W // 2, H // 2

        def redraw():
            c.delete("all")
            c._refs = []
            for img, x, y in [
                (self._imgs.get("note"), nx, ny),
                (self._imgs.get("line"), nx, ny + state['y']),
            ]:
                if img:
                    tk_i = ImageTk.PhotoImage(img)
                    c._refs.append(tk_i)
                    c.create_image(x, y, image=tk_i)
            c.create_text(8, 8, anchor='nw',
                text=f"y_offset={state['y']}", font=("Arial", 10))

        redraw()

        bf = tk.Frame(f, bg="white"); bf.pack(pady=4)
        tk.Button(bf, text="▲", command=lambda: (state.__setitem__('y', state['y']-1), redraw())).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="▼", command=lambda: (state.__setitem__('y', state['y']+1), redraw())).pack(side=tk.LEFT, padx=6)

        def save():
            self.cfg[key] = state['y']
            save_config(self.cfg)
            self.show_menu()

        tk.Button(f, text="Save & Back", bg="#228b22", fg="white", command=save).pack(pady=5)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app  = App(root)
    try:
        root.mainloop()
    finally:
        app.audio.stop()

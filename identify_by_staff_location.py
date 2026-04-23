"""Identify Note By Staff Location mode: show a note on staff, user clicks buttons to identify it."""

import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

from music_lessons import (
    staff_pos, is_sharp, is_flat, CANVAS_W, CANVAS_H,
    parse_note, FLAT_TO_SHARP, NOTE_NAMES,
)
from progress_report import BasLesson


NOTE_BUTTONS = ['C', 'C#/Db', 'D', 'D#/Eb', 'E', 'F', 'F#/Gb', 'G', 'G#/Ab', 'A', 'A#/Bb', 'B']


def _target_indices(note):
    name, oct_ = parse_note(note)
    sharp = FLAT_TO_SHARP.get(name, name)
    return NOTE_NAMES.index(sharp), oct_


def _buttons_for_pool(pool):
    """Return (sorted name indices 0-11, sorted octave ints) present in pool."""
    name_set, oct_set = set(), set()
    for note in pool:
        name, oct_ = parse_note(note)
        name_set.add(NOTE_NAMES.index(FLAT_TO_SHARP.get(name, name)))
        oct_set.add(oct_)
    return sorted(name_set), sorted(oct_set)


class IdentifyStaffLesson(BasLesson):

    def show(self, seq, mode, pool):
        self._seq   = seq
        self._mode  = mode
        self._idx   = 0
        self._selected_name = None
        self._selected_oct  = None
        app = self.app
        app._clear()

        name_indices, octaves = _buttons_for_pool(pool)

        self._bg = tk.Frame(app.root, bg="white")
        self._bg.pack(fill=tk.BOTH, expand=True)

        self._prog = ttk.Progressbar(self._bg, maximum=len(seq))
        self._prog.pack(fill=tk.X, padx=20, pady=6)

        self._cv = tk.Canvas(self._bg, bg="white", width=CANVAS_W)
        self._cv.pack(fill=tk.BOTH, expand=True)
        self._cv.bind("<Configure>", self._on_resize)

        name_frame = tk.Frame(self._bg, bg="white")
        name_frame.pack(fill=tk.X, padx=10, pady=(4, 2))
        self._name_btn_map: dict[int, tk.Button] = {}
        for i in name_indices:
            btn = tk.Button(
                name_frame, text=NOTE_BUTTONS[i], font=("Arial", 9, "bold"),
                command=lambda idx=i: self._on_name(idx),
            )
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
            self._name_btn_map[i] = btn

        oct_frame = tk.Frame(self._bg, bg="white")
        oct_frame.pack(fill=tk.X, padx=10, pady=(2, 4))
        self._oct_btn_map: dict[int, tk.Button] = {}
        for o in octaves:
            btn = tk.Button(
                oct_frame, text=str(o), font=("Arial", 10, "bold"),
                command=lambda ov=o: self._on_oct(ov),
            )
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
            self._oct_btn_map[o] = btn

        self._default_btn_bg = next(iter(self._name_btn_map.values())).cget("bg")

        tk.Button(self._bg, text="← Menu", command=app.show_menu).pack(pady=4)
        self._draw_next()

    # ── BasLesson overrides ───────────────────────────────────────────────────

    def _listen(self, target):
        pass  # button-based mode; no audio

    def _draw_next(self):
        if self._idx >= len(self._seq):
            self._complete()
            return
        self._selected_name = None
        self._selected_oct  = None
        self._reset_buttons()
        note = self._seq[self._idx]
        self._target = note
        self._render(note)
        self._prog['value'] = self._idx
        self._note_start_time = time.monotonic()

    def _flash_widgets(self):
        try:
            self._cv.config(bg="#32cd32")
        except Exception:
            pass

    def _reset_widgets(self):
        try:
            self._cv.config(bg="white")
        except Exception:
            pass

    # ── Button logic ─────────────────────────────────────────────────────────

    def _reset_buttons(self):
        bg = getattr(self, "_default_btn_bg", "")
        for btn in (*self._name_btn_map.values(), *self._oct_btn_map.values()):
            btn.config(bg=bg, fg="black", state=tk.NORMAL)

    def _on_name(self, idx):
        note = self._seq[self._idx]
        correct_idx, _ = _target_indices(note)
        if idx == correct_idx:
            self._name_btn_map[idx].config(bg="#32cd32", fg="white")
            self._selected_name = idx
            self._check_complete()
        else:
            self._name_btn_map[idx].config(bg="red", fg="white")

    def _on_oct(self, oct_):
        note = self._seq[self._idx]
        _, correct_oct = _target_indices(note)
        if oct_ == correct_oct:
            self._oct_btn_map[oct_].config(bg="#32cd32", fg="white")
            self._selected_oct = oct_
            self._check_complete()
        else:
            self._oct_btn_map[oct_].config(bg="red", fg="white")

    def _check_complete(self):
        if self._selected_name is not None and self._selected_oct is not None:
            for btn in (*self._name_btn_map.values(), *self._oct_btn_map.values()):
                btn.config(state=tk.DISABLED)
            self._hit()

    # ── Resize ────────────────────────────────────────────────────────────────

    def _on_resize(self, _event):
        if 0 <= self._idx < len(self._seq):
            self._render(self._seq[self._idx])

    # ── Layout (same as StaffLesson) ─────────────────────────────────────────

    def _compute_layout(self, canvas_h):
        MARGIN   = 30
        cfg      = self.app.cfg
        a4_off   = cfg["a4_y"] - CANVAS_H // 2
        step     = cfg["step_height"]
        term_top = 16 * step - a4_off
        term_bot = a4_off + 6 * step
        sf       = (canvas_h // 2 - MARGIN) / max(term_top, term_bot, 1)
        return sf, step * sf, canvas_h // 2 + a4_off * sf

    def _get_scaled_imgs(self, sf):
        key = round(sf, 4)
        if self.app._game_cache[0] == key:
            return self.app._game_cache[1]
        scaled = {}
        for name, img in self.app._imgs.items():
            if name == "staff":
                w, h = img.width, max(1, int(img.height * sf))
            else:
                w = max(1, int(img.width * sf))
                h = max(1, int(img.height * sf))
            scaled[name] = img.resize((w, h), Image.LANCZOS)
        self.app._game_cache = (key, scaled)
        return scaled

    # ── Rendering (same as StaffLesson) ──────────────────────────────────────

    def _render(self, note):
        c = self._cv
        c.delete("all")
        self.app._refs = []

        canvas_h = max(c.winfo_height(), 100)
        cx       = max(c.winfo_width(), CANVAS_W) // 2
        cfg      = self.app.cfg

        sf, step_eff, a4_y_eff = self._compute_layout(canvas_h)
        imgs = self._get_scaled_imgs(sf)

        def y_for(p):
            return a4_y_eff - (p - 3) * step_eff

        pos = staff_pos(note)
        ny  = y_for(pos) if pos is not None else a4_y_eff

        if "staff" in imgs:
            tk_s = ImageTk.PhotoImage(imgs["staff"])
            self.app._refs.append(tk_s)
            c.create_image(cx, canvas_h // 2, image=tk_s)

        if "line" in imgs and pos is not None:
            loff_above = cfg["ledger_above_y_offset"] * sf
            loff_below = cfg["ledger_below_y_offset"] * sf
            if pos <= -2:
                lo_p = pos if pos % 2 == 0 else pos + 1
                for p in range(-2, lo_p - 1, -2):
                    tk_l = ImageTk.PhotoImage(imgs["line"])
                    self.app._refs.append(tk_l)
                    c.create_image(cx, y_for(p) + loff_below, image=tk_l)
            if pos >= 10:
                hi_p = pos if pos % 2 == 0 else pos - 1
                for p in range(10, hi_p + 1, 2):
                    tk_l = ImageTk.PhotoImage(imgs["line"])
                    self.app._refs.append(tk_l)
                    c.create_image(cx, y_for(p) + loff_above, image=tk_l)

        if is_sharp(note) and "sharp" in imgs:
            tk_sh = ImageTk.PhotoImage(imgs["sharp"])
            self.app._refs.append(tk_sh)
            c.create_image(cx + cfg["sharp_x_offset"] * sf,
                           ny + cfg["sharp_y_offset"] * sf, image=tk_sh)
        elif is_flat(note) and "flat" in imgs:
            tk_fl = ImageTk.PhotoImage(imgs["flat"])
            self.app._refs.append(tk_fl)
            c.create_image(cx + cfg["flat_x_offset"] * sf,
                           ny + cfg["flat_y_offset"] * sf, image=tk_fl)

        if "note" in imgs:
            tk_n = ImageTk.PhotoImage(imgs["note"])
            self.app._refs.append(tk_n)
            c.create_image(cx, ny, image=tk_n)

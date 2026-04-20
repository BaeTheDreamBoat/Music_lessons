"""Staff mode: renders notes on a treble clef and listens for the correct pitch."""

import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

from music_lessons import staff_pos, is_sharp, is_flat, CANVAS_W, CANVAS_H
from progress_report import BasLesson


class StaffLesson(BasLesson):

    def show(self, seq, mode):
        self._seq  = seq
        self._mode = mode
        self._idx  = 0
        app = self.app
        app._clear()

        self._bg = tk.Frame(app.root, bg="white")
        self._bg.pack(fill=tk.BOTH, expand=True)

        self._prog = ttk.Progressbar(self._bg, maximum=len(seq))
        self._prog.pack(fill=tk.X, padx=20, pady=6)

        self._cv = tk.Canvas(self._bg, bg="white", width=CANVAS_W)
        self._cv.pack(fill=tk.BOTH, expand=True)
        self._cv.bind("<Configure>", self._on_resize)

        tk.Button(self._bg, text="\u2190 Menu", command=app.show_menu).pack(pady=4)
        self._draw_next()

    # ── BasLesson overrides ───────────────────────────────────────────────────

    def _draw_next(self):
        if self._idx >= len(self._seq):
            self._complete()
            return
        note = self._seq[self._idx]
        self._render(note)
        self._prog['value'] = self._idx
        self._note_start_time = time.monotonic()
        self._listen(note)

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

    # ── Resize ────────────────────────────────────────────────────────────────

    def _on_resize(self, _event):
        if 0 <= self._idx < len(self._seq):
            self._render(self._seq[self._idx])

    # ── Layout ────────────────────────────────────────────────────────────────

    def _compute_layout(self, canvas_h):
        """Return (sf, step_eff, a4_y_eff) so that B3–C7 always fit."""
        MARGIN   = 30
        cfg      = self.app.cfg
        a4_off   = cfg["a4_y"] - CANVAS_H // 2
        step     = cfg["step_height"]
        term_top = 16 * step - a4_off
        term_bot = a4_off + 6 * step
        sf       = (canvas_h // 2 - MARGIN) / max(term_top, term_bot, 1)
        return sf, step * sf, canvas_h // 2 + a4_off * sf

    def _get_scaled_imgs(self, sf):
        """Return images scaled by sf from the calibration base; result is cached."""
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

    # ── Rendering ─────────────────────────────────────────────────────────────

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

        # Staff image
        if "staff" in imgs:
            tk_s = ImageTk.PhotoImage(imgs["staff"])
            self.app._refs.append(tk_s)
            c.create_image(cx, canvas_h // 2, image=tk_s)

        # Ledger lines
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

        # Accidental
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

        # Note head
        if "note" in imgs:
            tk_n = ImageTk.PhotoImage(imgs["note"])
            self.app._refs.append(tk_n)
            c.create_image(cx, ny, image=tk_n)

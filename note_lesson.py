"""Letters mode: displays the note name as large text and listens for the correct pitch."""

import time
import tkinter as tk
from tkinter import ttk

from progress_report import BasLesson


class LettersLesson(BasLesson):

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

        self._lbl = tk.Label(self._bg, text="", font=("Arial", 80, "bold"), bg="white")
        self._lbl.pack(expand=True)

        tk.Button(self._bg, text="\u2190 Menu", command=app.show_menu).pack(pady=4)
        self._draw_next()

    # ── BasLesson overrides ───────────────────────────────────────────────────

    def _draw_next(self):
        if self._idx >= len(self._seq):
            self._complete()
            return
        note = self._seq[self._idx]
        self._bg.config(bg="white")
        self._lbl.config(text=note, bg="white", fg="black")
        self._prog['value'] = self._idx
        self._note_start_time = time.monotonic()
        self._listen(note)

    def _flash_widgets(self):
        try:
            self._lbl.config(bg="#32cd32")
        except Exception:
            pass

    def _reset_widgets(self):
        try:
            self._lbl.config(bg="white", fg="black")
        except Exception:
            pass

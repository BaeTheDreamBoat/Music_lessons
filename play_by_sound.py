"""Play By Sound mode: a tone is played, user must play back that note on their instrument."""

import time
import tkinter as tk
from tkinter import ttk

from progress_report import BasLesson


class SoundLesson(BasLesson):

    def show(self, seq, mode, duration_s):
        self._seq  = seq
        self._mode = mode
        self._idx  = 0
        app = self.app
        app._clear()

        self._bg = tk.Frame(app.root, bg="white")
        self._bg.pack(fill=tk.BOTH, expand=True)

        self._prog = ttk.Progressbar(self._bg, maximum=duration_s)
        self._prog.pack(fill=tk.X, padx=20, pady=6)

        self._lbl = tk.Label(self._bg, text="?", font=("Arial", 80), bg="white", fg="#aaaaaa")
        self._lbl.pack(expand=True)

        self._replay_btn = tk.Button(
            self._bg, text="Replay", font=("Arial", 11),
            command=self._replay,
        )
        self._replay_btn.pack(pady=(0, 6))

        tk.Button(self._bg, text="← Menu", command=app.show_menu).pack(pady=4)
        self._begin(duration_s)

    # ── BasLesson overrides ───────────────────────────────────────────────────

    def _draw_next(self):
        if self._idx >= len(self._seq):
            self._complete()
            return
        note = self._seq[self._idx]
        self._bg.config(bg="white")
        self._lbl.config(text="?", bg="white", fg="#aaaaaa")
        self._replay_btn.config(state=tk.NORMAL)
        self._note_start_time = time.monotonic()
        self._pause_for_tone()
        self._play_tone()
        self._listen(note)

    def _flash_widgets(self):
        try:
            self._lbl.config(bg="#32cd32", fg="white")
        except Exception:
            pass

    def _reset_widgets(self):
        try:
            self._lbl.config(text="?", bg="white", fg="#aaaaaa")
            self._replay_btn.config(state=tk.NORMAL)
        except Exception:
            pass

    # ── Tone playback ─────────────────────────────────────────────────────────

    def _play_tone(self):
        note     = self._seq[self._idx]
        duration = self.app.cfg.get("tone_duration", 1.5)
        volume   = self.app.cfg.get("tone_volume", 0.5)
        self.app.audio.play_tone(note, duration, volume)

    def _replay(self):
        self._play_tone()

"""Identify Note By Sound mode: a tone is played, user clicks buttons to identify it."""

import time
import tkinter as tk
from tkinter import ttk

from music_lessons import parse_note, FLAT_TO_SHARP, NOTE_NAMES
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


class IdentifySoundLesson(BasLesson):

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

        self._lbl = tk.Label(self._bg, text="?", font=("Arial", 80), bg="white", fg="#aaaaaa")
        self._lbl.pack(expand=True)

        ctrl_frame = tk.Frame(self._bg, bg="white")
        ctrl_frame.pack(pady=(0, 6))
        self._replay_btn = tk.Button(
            ctrl_frame, text="Replay", font=("Arial", 11),
            command=self._replay,
        )
        self._replay_btn.pack(side=tk.LEFT, padx=6)
        tk.Button(
            ctrl_frame, text="Reference: C4", font=("Arial", 11),
            command=self._play_reference,
        ).pack(side=tk.LEFT, padx=6)

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
        pass  # button-based mode; no audio listening

    def _draw_next(self):
        if self._idx >= len(self._seq):
            self._complete()
            return
        self._selected_name = None
        self._selected_oct  = None
        self._reset_buttons()
        note = self._seq[self._idx]
        self._target = note
        self._prog['value'] = self._idx
        self._note_start_time = time.monotonic()
        self._bg.config(bg="white")
        self._lbl.config(text="?", bg="white", fg="#aaaaaa")
        self._replay_btn.config(state=tk.NORMAL)
        self._play_tone()

    def _flash_widgets(self):
        try:
            self._lbl.config(bg="#32cd32", fg="white")
        except Exception:
            pass

    def _reset_widgets(self):
        try:
            self._lbl.config(text="?", bg="white", fg="#aaaaaa")
        except Exception:
            pass

    # ── Tone playback ─────────────────────────────────────────────────────────

    def _play_tone(self):
        duration = self.app.cfg.get("tone_duration", 1.5)
        volume   = self.app.cfg.get("tone_volume", 0.5)
        self.app.audio.play_tone(self._seq[self._idx], duration, volume)

    def _replay(self):
        self._play_tone()

    def _play_reference(self):
        volume = self.app.cfg.get("tone_volume", 0.5)
        self.app.audio.play_tone("C4", self.app.cfg.get("tone_duration", 1.5), volume)

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
            self._replay_btn.config(state=tk.DISABLED)
            self._hit()

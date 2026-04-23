"""Main menu GUI and lesson-launch logic."""

import tkinter as tk
from tkinter import ttk

from music_lessons import (
    NOTE_DISPLAY, NOTE_DISPLAY_TO_SHARP, SHARP_TO_DISPLAY,
    note_to_midi, midi_to_note, save_config,
)


class MainMenu:
    def __init__(self, app):
        self.app = app

    def show(self):
        app = self.app
        app._clear()
        cfg = app.cfg

        f = tk.Frame(app.root, padx=18, pady=10)
        f.pack(fill=tk.BOTH, expand=True)
        for i in range(14):
            f.rowconfigure(i, weight=1)

        tk.Label(f, text="Music Lessons", font=("Arial", 22, "bold")).grid(
            row=0, column=0, columnspan=6, pady=10)

        # ── Note range ────────────────────────────────────────────────────────
        tk.Label(f, text="Note Range:").grid(row=1, column=0, sticky='e')
        tk.Label(f, text="Lower:").grid(row=1, column=1, sticky='e')
        self.lo_var = tk.StringVar(value=SHARP_TO_DISPLAY.get(cfg["lower_note"], cfg["lower_note"]))
        ttk.Combobox(f, textvariable=self.lo_var, values=NOTE_DISPLAY,
                     width=10, state='readonly').grid(row=1, column=2, padx=4)
        tk.Label(f, text="Upper:").grid(row=1, column=3, sticky='e')
        self.hi_var = tk.StringVar(value=SHARP_TO_DISPLAY.get(cfg["upper_note"], cfg["upper_note"]))
        ttk.Combobox(f, textvariable=self.hi_var, values=NOTE_DISPLAY,
                     width=10, state='readonly').grid(row=1, column=4, padx=4)
        self.lo_var.trace_add("write", lambda *_: self._save_range())
        self.hi_var.trace_add("write", lambda *_: self._save_range())

        # ── Sound range (used by the two By Sound modes) ──────────────────────
        tk.Label(f, text="Sound Range:").grid(row=2, column=0, sticky='e')
        tk.Label(f, text="Lower:").grid(row=2, column=1, sticky='e')
        self.slo_var = tk.StringVar(value=SHARP_TO_DISPLAY.get(cfg.get("sound_lower_note", "C4"), "C4"))
        ttk.Combobox(f, textvariable=self.slo_var, values=NOTE_DISPLAY,
                     width=10, state='readonly').grid(row=2, column=2, padx=4)
        tk.Label(f, text="Upper:").grid(row=2, column=3, sticky='e')
        self.shi_var = tk.StringVar(value=SHARP_TO_DISPLAY.get(cfg.get("sound_upper_note", "B4"), "B4"))
        ttk.Combobox(f, textvariable=self.shi_var, values=NOTE_DISPLAY,
                     width=10, state='readonly').grid(row=2, column=4, padx=4)
        self.slo_var.trace_add("write", lambda *_: self._save_sound_range())
        self.shi_var.trace_add("write", lambda *_: self._save_sound_range())

        # ── Count & duration ──────────────────────────────────────────────────
        tk.Label(f, text="# Notes:").grid(row=3, column=0, sticky='e', pady=6)
        self.num_var = tk.IntVar(value=cfg["num_notes"])
        tk.Spinbox(f, from_=1, to=200, textvariable=self.num_var, width=5).grid(row=3, column=2)

        tk.Label(f, text="Tone Volume:").grid(row=3, column=3, sticky='e', pady=6)
        self.tone_vol_var = tk.DoubleVar(value=cfg.get("tone_volume", 0.5))
        tk.Spinbox(f, from_=0.05, to=1.0, increment=0.05, format="%.2f",
                   textvariable=self.tone_vol_var, width=5).grid(row=3, column=4)

        tk.Label(f, text="Hold Duration (s):").grid(row=4, column=0, sticky='e', pady=4)
        self.dur_var = tk.DoubleVar(value=cfg["note_duration"])
        tk.Spinbox(f, from_=0.5, to=10.0, increment=0.5,
                   textvariable=self.dur_var, width=5).grid(row=4, column=2)

        tk.Label(f, text="Tone Duration (s):").grid(row=4, column=3, sticky='e', pady=4)
        self.tone_dur_var = tk.DoubleVar(value=cfg.get("tone_duration", 1.5))
        tk.Spinbox(f, from_=0.5, to=10.0, increment=0.5,
                   textvariable=self.tone_dur_var, width=5).grid(row=4, column=4)

        # ── Mic device ────────────────────────────────────────────────────────
        tk.Label(f, text="Mic Device:").grid(row=5, column=0, sticky='e', pady=4)
        dev_names   = [name for _, name in app._input_devices]
        saved_idx   = cfg.get("mic_device_index")
        current_dev = dev_names[0] if dev_names else ""
        for idx, name in app._input_devices:
            if idx == saved_idx:
                current_dev = name
                break
        self.mic_dev_var = tk.StringVar(value=current_dev)
        ttk.Combobox(f, textvariable=self.mic_dev_var, values=dev_names,
                     state='readonly', width=36).grid(
                     row=5, column=1, columnspan=4, sticky='w', padx=4)
        self.mic_dev_var.trace_add("write", lambda *_: self._on_mic_change())

        # ── Mic level bar ─────────────────────────────────────────────────────
        tk.Label(f, text="Mic Level:").grid(row=6, column=0, sticky='e', pady=5)
        mic_row = tk.Frame(f)
        mic_row.grid(row=6, column=1, columnspan=5, sticky='w')
        app._mic_cv = tk.Canvas(mic_row, width=280, height=26, bg="#1a1a1a",
                                highlightthickness=1)
        app._mic_cv.pack(side=tk.LEFT)
        self.thr_var = tk.DoubleVar(value=cfg["mic_threshold"])
        app.thr_var  = self.thr_var
        tk.Scale(mic_row, variable=self.thr_var, from_=0.0, to=0.2,
                 resolution=0.002, orient=tk.HORIZONTAL, length=200,
                 showvalue=False).pack(side=tk.LEFT, padx=8)
        app._note_lbl = tk.Label(mic_row, text="---", font=("Arial", 16, "bold"), width=5)
        app._note_lbl.pack(side=tk.LEFT)

        # ── Note image scale ──────────────────────────────────────────────────
        tk.Label(f, text="Note Scale:").grid(row=7, column=0, sticky='e', pady=4)
        self.ns_var = tk.DoubleVar(value=cfg.get("note_scale", 1.0))
        tk.Spinbox(f, from_=0.05, to=5.0, increment=0.05,
                   textvariable=self.ns_var, width=6).grid(row=7, column=2)
        tk.Button(f, text="Apply", command=self._apply_note_scale).grid(row=7, column=3, padx=4)

        # ── Mode selection ────────────────────────────────────────────────────
        ttk.Separator(f, orient='horizontal').grid(
            row=8, column=0, columnspan=6, sticky='ew', pady=6)
        tk.Label(f, text="Mode:", font=("Arial", 12, "bold")).grid(row=9, column=0, sticky='e')
        self.mode_var = tk.StringVar(value="Play By Staff Location")
        tk.Radiobutton(f, text="Play By Staff Location", variable=self.mode_var, value="Play By Staff Location").grid(row=9, column=1, sticky='w')
        tk.Radiobutton(f, text="Play By Note Name",      variable=self.mode_var, value="Play By Note Name"     ).grid(row=9, column=2, sticky='w')
        tk.Radiobutton(f, text="Play By Sound",          variable=self.mode_var, value="Play By Sound"         ).grid(row=9, column=3, sticky='w')
        tk.Radiobutton(f, text="Identify Note By Staff Location", variable=self.mode_var, value="Identify Note By Staff Location").grid(row=10, column=1, sticky='w')
        tk.Radiobutton(f, text="Identify Note By Sound",          variable=self.mode_var, value="Identify Note By Sound"         ).grid(row=10, column=2, sticky='w')
        tk.Button(f, text="Start", bg="#228b22", fg="white",
                  font=("Arial", 11, "bold"),
                  command=self._start_lesson).grid(row=10, column=5, padx=8)

        # ── Debug selection ───────────────────────────────────────────────────
        ttk.Separator(f, orient='horizontal').grid(
            row=11, column=0, columnspan=6, sticky='ew', pady=6)
        tk.Label(f, text="Debug:", font=("Arial", 12, "bold")).grid(row=12, column=0, sticky='e')
        self.dbg_var = tk.StringVar(value="Note on scale")
        opts = ["Note on scale", "sharp location", "flat location",
                "notes above scale", "notes below scale"]
        for i, opt in enumerate(opts):
            r, c = divmod(i, 3)
            tk.Radiobutton(f, text=opt, variable=self.dbg_var,
                           value=opt).grid(row=12 + r, column=1 + c, sticky='w')
        tk.Button(f, text="Start Debug", bg="#cc6600", fg="white",
                  command=self._start_debug).grid(row=13, column=5, padx=8)

        # Enforce minimum window size so all elements always remain visible
        app.root.update_idletasks()
        min_w = app.root.winfo_reqwidth()
        min_h = app.root.winfo_reqheight()
        app.root.minsize(min_w, min_h)
        cur_w = app.root.winfo_width()
        cur_h = app.root.winfo_height()
        if cur_w < min_w or cur_h < min_h:
            app.root.geometry(f"{max(cur_w, min_w)}x{max(cur_h, min_h)}")

    # ── Config helpers ────────────────────────────────────────────────────────

    def _save_range(self):
        cfg = self.app.cfg
        cfg["lower_note"] = NOTE_DISPLAY_TO_SHARP.get(self.lo_var.get(), self.lo_var.get())
        cfg["upper_note"] = NOTE_DISPLAY_TO_SHARP.get(self.hi_var.get(), self.hi_var.get())
        save_config(cfg)

    def _save_sound_range(self):
        cfg = self.app.cfg
        cfg["sound_lower_note"] = NOTE_DISPLAY_TO_SHARP.get(self.slo_var.get(), self.slo_var.get())
        cfg["sound_upper_note"] = NOTE_DISPLAY_TO_SHARP.get(self.shi_var.get(), self.shi_var.get())
        save_config(cfg)

    def _save_lesson_cfg(self):
        cfg = self.app.cfg
        cfg["num_notes"]      = self.num_var.get()
        cfg["note_duration"]  = self.dur_var.get()
        cfg["tone_duration"]  = self.tone_dur_var.get()
        cfg["tone_volume"]    = self.tone_vol_var.get()
        cfg["mic_threshold"]  = self.thr_var.get()
        save_config(cfg)

    def _on_mic_change(self):
        name = self.mic_dev_var.get()
        for idx, n in self.app._input_devices:
            if n == name:
                self.app.cfg["mic_device_index"] = idx
                save_config(self.app.cfg)
                try:
                    self.app.audio.restart(idx)
                except Exception:
                    pass
                break

    def _apply_note_scale(self):
        self.app.cfg["note_scale"] = round(self.ns_var.get(), 4)
        save_config(self.app.cfg)
        self.app._load_images()

    # ── Lesson launch ─────────────────────────────────────────────────────────

    def _note_range(self):
        cfg = self.app.cfg
        lo  = note_to_midi(cfg["lower_note"])
        hi  = note_to_midi(cfg["upper_note"])
        return [midi_to_note(m) for m in range(lo, hi + 1)]

    def _sound_note_range(self):
        cfg = self.app.cfg
        lo  = note_to_midi(cfg.get("sound_lower_note", "C4"))
        hi  = note_to_midi(cfg.get("sound_upper_note", "B4"))
        return [midi_to_note(m) for m in range(lo, hi + 1)]

    _SOUND_MODES = {"Identify Note By Sound", "Play By Sound"}

    def _start_lesson(self):
        self._save_lesson_cfg()
        mode = self.mode_var.get()
        pool = self._sound_note_range() if mode in self._SOUND_MODES else self._note_range()
        if not pool:
            return
        from progress_report import build_sequence
        seq  = build_sequence(self.app.cfg, mode, pool, self.app.cfg["num_notes"])
        if mode == "Play By Staff Location":
            from play_by_staff_location import StaffLesson
            StaffLesson(self.app).show(seq, mode)
        elif mode == "Identify Note By Staff Location":
            from identify_by_staff_location import IdentifyStaffLesson
            IdentifyStaffLesson(self.app).show(seq, mode, pool)
        elif mode == "Identify Note By Sound":
            from identify_by_sound import IdentifySoundLesson
            IdentifySoundLesson(self.app).show(seq, mode, pool)
        elif mode == "Play By Sound":
            from play_by_sound import SoundLesson
            SoundLesson(self.app).show(seq, mode)
        else:
            from play_by_note_name import LettersLesson
            LettersLesson(self.app).show(seq, mode)

    def _start_debug(self):
        from debug_menus import DebugMenus
        DebugMenus(self.app).show(self.dbg_var.get())

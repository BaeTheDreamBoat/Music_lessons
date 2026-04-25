#!/usr/bin/env python3
"""Music Lessons - Interactive note recognition trainer."""

import json
import os
import time
import threading

import numpy as np
import pyaudio
from PIL import Image

# ─── Constants ────────────────────────────────────────────────────────────────

CONFIG_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
NOTE_STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "note_stats.json")
IMAGES_PATH     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

NOTE_NAMES    = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
DIATONIC      = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
ALL_NOTES     = [f"{n}{o}" for o in range(0, 9) for n in NOTE_NAMES]
SHARP_TO_FLAT = {'C#': 'Db', 'D#': 'Eb', 'F#': 'Gb', 'G#': 'Ab', 'A#': 'Bb'}
FLAT_TO_SHARP = {v: k for k, v in SHARP_TO_FLAT.items()}

# Combo-box display list: chromatic notes shown as "C#4/Db4", naturals as "C4"
NOTE_DISPLAY: list[str] = []
NOTE_DISPLAY_TO_SHARP: dict[str, str] = {}   # "C#4/Db4" -> "C#4",  "C4" -> "C4"
for _n in ALL_NOTES:
    if len(_n) >= 3 and _n[1] == '#':
        _flat = f"{SHARP_TO_FLAT[_n[:2]]}{_n[2:]}"
        _disp = f"{_n}/{_flat}"
        NOTE_DISPLAY.append(_disp)
        NOTE_DISPLAY_TO_SHARP[_disp] = _n
    else:
        NOTE_DISPLAY.append(_n)
        NOTE_DISPLAY_TO_SHARP[_n] = _n
SHARP_TO_DISPLAY = {v: k for k, v in NOTE_DISPLAY_TO_SHARP.items()}

DEFAULT_CONFIG = {
    "lower_note":            "C4",
    "upper_note":            "B5",
    "sound_lower_note":      "C4",
    "sound_upper_note":      "B4",
    "lesson_duration":       5.0,
    "note_duration":         2.0,
    "tone_duration":         1.5,
    "tone_volume":           0.5,
    "startup_delay":         3,
    "playlist_selected":     [],
    "playlist_reps":         1,
    "mic_threshold":         0.02,
    "mic_device_index":      None,
    "note_scale":            1.0,
    "a4_y":                  238,
    "step_height":           28.5,
    "sharp_x_offset":        74,
    "sharp_y_offset":        0,
    "flat_x_offset":         58,
    "flat_y_offset":         -28,
    "ledger_above_y_offset": -2,
    "ledger_below_y_offset":  0,
}

CANVAS_W = 800
CANVAS_H = 440

# ─── Music utilities ──────────────────────────────────────────────────────────

def parse_note(s):
    """'A#4' -> ('A#', 4),  'Bb4' -> ('Bb', 4),  'C4' -> ('C', 4)"""
    if len(s) >= 2 and s[1] == '#':
        return s[:2], int(s[2:])
    if len(s) >= 3 and s[1] == 'b':
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
    return 'b' in name

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
    data = json.dumps(cfg, indent=2)
    threading.Thread(target=lambda: open(CONFIG_FILE, 'w').write(data), daemon=True).start()

def save_lesson_stats(mode, avg_per_min):
    from datetime import datetime
    records = []
    if os.path.exists(NOTE_STATS_FILE):
        with open(NOTE_STATS_FILE) as f:
            records = json.load(f)
    now = datetime.now()
    records.append({
        "date":              now.strftime("%Y-%m-%d"),
        "time":              now.strftime("%H:%M:%S"),
        "mode":              mode,
        "avg_notes_per_min": round(avg_per_min, 1),
    })
    with open(NOTE_STATS_FILE, 'w') as f:
        json.dump(records, f, indent=2)

# ─── Audio engine ─────────────────────────────────────────────────────────────

class AudioEngine:
    CHUNK = 4096
    RATE  = 44100

    def __init__(self):
        self.pa         = pyaudio.PyAudio()
        self.stream     = None
        self._channels  = 1
        self._vol       = 0.0
        self._note      = None
        self._lock      = threading.Lock()
        self._play_stop = threading.Event()

    def get_input_devices(self):
        devs = []
        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                devs.append((i, info['name']))
        return devs

    def _open_stream(self, device_index, channels):
        self._channels = channels
        stream = self.pa.open(
            format=pyaudio.paFloat32, channels=channels, rate=self.RATE,
            input=True, frames_per_buffer=self.CHUNK,
            stream_callback=self._cb,
            input_device_index=device_index,
        )
        stream.start_stream()
        return stream

    def start(self, device_index=None):
        # Build candidate list: preferred device first, then all other input devices
        candidates = []
        if device_index is not None:
            candidates.append(device_index)
        try:
            default_idx = self.pa.get_default_input_device_info()['index']
            if default_idx not in candidates:
                candidates.append(default_idx)
        except OSError:
            pass
        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            if int(info['maxInputChannels']) > 0 and i not in candidates:
                candidates.append(i)

        last_err = None
        for idx in candidates:
            info = self.pa.get_device_info_by_index(idx)
            max_ch = int(info['maxInputChannels'])
            for ch in [1, 2] if max_ch == 0 else [min(max_ch, 1), min(max_ch, 2)]:
                if ch < 1:
                    continue
                try:
                    self.stream = self._open_stream(idx, ch)
                    return
                except (OSError, ValueError) as e:
                    last_err = e
        raise OSError(f"Could not open any input device: {last_err}")

    def restart(self, device_index=None):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        self.start(device_index)

    def _cb(self, in_data, frame_count, time_info, status):
        samples = np.frombuffer(in_data, dtype=np.float32).reshape(-1, self._channels).mean(axis=1)
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

    def play_tone(self, note, duration, volume=0.5):
        """Synthesize and play note for duration seconds (non-blocking). Interrupts any current tone."""
        self._play_stop.set()
        stop = threading.Event()
        self._play_stop = stop
        freq = 440.0 * 2.0 ** ((note_to_midi(note) - 69) / 12.0)
        threading.Thread(target=self._play_blocking, args=(freq, duration, volume, stop), daemon=True).start()

    def _play_blocking(self, freq, duration, volume, stop):
        n = int(self.RATE * duration)
        samples = (volume * np.sin(2 * np.pi * freq * np.linspace(0, duration, n, endpoint=False))).astype(np.float32)
        fade = min(int(self.RATE * 0.02), n // 2)
        samples[:fade]  *= np.linspace(0, 1, fade, dtype=np.float32)
        samples[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)

        pos = [0]

        def callback(_in_data, frame_count, _time_info, _status):
            if stop.is_set():
                return (np.zeros(frame_count, dtype=np.float32).tobytes(), pyaudio.paAbort)
            i = pos[0]
            chunk = samples[i:i + frame_count]
            if len(chunk) < frame_count:
                out = np.zeros(frame_count, dtype=np.float32)
                out[:len(chunk)] = chunk
                pos[0] = n
                return (out.tobytes(), pyaudio.paComplete)
            pos[0] = i + frame_count
            return (chunk.tobytes(), pyaudio.paContinue)

        stream = self.pa.open(
            format=pyaudio.paFloat32, channels=1, rate=self.RATE, output=True,
            frames_per_buffer=2048, stream_callback=callback,
        )
        stream.start_stream()
        while stream.is_active() and not stop.is_set():
            time.sleep(0.05)
        stream.stop_stream()
        stream.close()

    def get_state(self):
        with self._lock:
            return self._vol, self._note

    def stop(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.pa.terminate()

# ─── Application coordinator ──────────────────────────────────────────────────

class App:
    def __init__(self, root):
        self.root   = root
        self.root.title("Music Lessons")
        win_w, win_h = 920, 740
        root.update_idletasks()
        sx = root.winfo_screenwidth()
        sy = root.winfo_screenheight()
        x  = max(0, (sx - win_w) // 2)
        y  = max(0, (sy - win_h) // 2)
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.cfg        = load_config()
        self._last_mode = None
        self.audio  = AudioEngine()
        self._input_devices = self.audio.get_input_devices()
        try:
            self.audio.start(self.cfg.get("mic_device_index"))
        except OSError as e:
            print(f"Warning: could not open microphone: {e}\nUse Settings to select a device.")
        self._imgs       = {}
        self._refs       = []
        self._game_cache = (None, {})
        self._load_images()
        self._vol      = 0.0
        self._note     = None
        self._mic_cv   = None
        self._note_lbl = None
        self.thr_var   = None
        self._mic_poll()
        self.show_menu()

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

    def _mic_poll(self):
        self._vol, self._note = self.audio.get_state()
        try:
            self._redraw_mic_bar()
        except Exception:
            pass
        self.root.after(50, self._mic_poll)

    def _redraw_mic_bar(self):
        if self._mic_cv is None or not self._mic_cv.winfo_exists():
            return
        W, H   = 280, 26
        thresh = self.thr_var.get() if self.thr_var else 0.02
        fill_w = min(int(self._vol / 0.2 * W), W)
        thr_x  = min(int(thresh   / 0.2 * W), W)
        c = self._mic_cv
        c.delete("all")
        c.create_rectangle(0, 0, fill_w, H, fill="#00cc00", outline="")
        c.create_rectangle(fill_w, 0, W, H, fill="#1a1a1a", outline="")
        c.create_line(thr_x, 0, thr_x, H, fill="red", width=2)
        if self._note_lbl and self._note_lbl.winfo_exists():
            self._note_lbl.config(text=self._note or "---")

    def _clear(self):
        for w in self.root.winfo_children():
            w.destroy()
        self._refs     = []
        self._mic_cv   = None
        self._note_lbl = None

    def show_menu(self):
        from menu import MainMenu
        MainMenu(self).show()


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tkinter as tk
    root = tk.Tk()
    app  = App(root)
    try:
        root.mainloop()
    finally:
        app.audio.stop()

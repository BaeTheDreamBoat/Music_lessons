# Functional Specification Document

## Music Lessons — Version 2

------

## General Requirements

- **Language:** Python 3
- **GUI framework:** Tkinter with ttk widgets
- **Audio:** PyAudio (44100 Hz, mono, float32) with autocorrelation-based pitch detection
- **Image handling:** Pillow (PIL)
- **Config persistence:** JSON file (`config.json`) stored alongside the script
- **Images** are placed in `./images/` relative to the script:
  - `staff.png` — treble clef staff
  - `note.png` — whole note head
  - `line.png` — ledger line
  - `sharp.png` — sharp symbol (♯)
  - `flat.png` — flat symbol (♭)

------

## Configuration

All settings are stored in `config.json` and loaded at startup. Missing keys fall back to defaults.

| Key | Default | Description |
|-----|---------|-------------|
| `lower_note` | `C4` | Lower bound of note range |
| `upper_note` | `B5` | Upper bound of note range |
| `num_notes` | `10` | Number of notes per lesson |
| `note_duration` | `2.0` | Seconds the correct note must be held |
| `mic_threshold` | `0.02` | Minimum RMS volume to register a note |
| `mic_device_index` | `null` | PyAudio input device index (null = system default) |
| `note_scale` | `1.0` | Size multiplier for note/sharp/flat/line images |
| `a4_y` | `230` | Absolute canvas Y coordinate of A4 in the debug reference canvas (800×440) |
| `step_height` | `14.0` | Pixels per diatonic step at the debug reference scale |
| `sharp_x_offset` | `-30` | X offset of sharp symbol from note centre, in debug pixels |
| `sharp_y_offset` | `-5` | Y offset of sharp symbol from note centre, in debug pixels |
| `flat_x_offset` | `-28` | X offset of flat symbol from note centre, in debug pixels |
| `flat_y_offset` | `0` | Y offset of flat symbol from note centre, in debug pixels |
| `ledger_above_y_offset` | `0` | Y offset of ledger line relative to note centre when above the staff, in debug pixels |
| `ledger_below_y_offset` | `0` | Y offset of ledger line relative to note centre when below the staff, in debug pixels |

Config is saved immediately whenever any setting changes (range selectors, mic threshold, mic device, note scale, debug save).

------

## Image Scaling Model

### Debug reference scale
All calibration values (`a4_y`, `step_height`, offsets) are defined in terms of a **debug reference canvas** of 800×440 pixels with the staff image scaled to exactly 800 px wide. This is the coordinate system used in all debug screens.

### Game scale factor (`sf`)
At runtime the staff game canvas fills the window vertically. To guarantee every note in the absolute range **B3–C7** (diatonic positions −3 to 19) is always visible with a 30 px margin, a scale factor `sf` is computed each time the canvas is drawn:

```
a4_off   = a4_y − (CANVAS_H / 2)          # A4 offset from reference centre
term_top = 16 × step_height − a4_off      # headroom needed for C7
term_bot = a4_off + 6 × step_height       # headroom needed for B3
sf       = (canvas_h / 2 − 30) / max(term_top, term_bot)
```

The game then uses:
- `step_eff = step_height × sf`
- `a4_y_eff = canvas_h / 2 + a4_off × sf`
- All pixel offsets (sharp, flat, ledger) are also multiplied by `sf`

All images (note, sharp, flat, line) are scaled by `sf` from their debug-reference size. The staff image width stays fixed at 800 px; its height scales by `sf`. Scaled images are cached and only recomputed when `sf` changes (i.e., when the window height changes).

------

## Main Menu

The window opens at 920×740. The main menu is a grid layout with the following controls:

### Note Range
- **Lower** and **Upper** combo boxes, read-only, listing every note from C0–B8 in scientific pitch notation (chromatic, sharps only in the list: `C4`, `C#4`, `D4`, …)
- Selection is saved to config immediately on change
- Both bounds are inclusive; the lesson draws randomly from the full chromatic range between them

### Number of Notes
- Spinbox, range 1–200, default 10
- Saved when the lesson starts

### Duration (s)
- Spinbox, range 0.5–10.0, step 0.5, default 2.0 seconds
- The note must be held continuously above the mic threshold for this duration to count as correct
- Saved when the lesson starts

### Mic Device
- Dropdown listing all system audio input devices by name
- Switching devices restarts the audio stream immediately; the selected device index is saved to config

### Mic Level Bar
- 280×26 px canvas updated every 50 ms showing current RMS volume as a green fill bar
- A red threshold line is positioned by a horizontal slider to the right of the bar (range 0.0–0.2, resolution 0.002)
- The currently detected note is displayed as a bold label to the right of the slider, updated continuously; shows `---` when no note is detected
- The threshold slider value is saved when the lesson starts

### Note Scale
- Spinbox (0.05–5.0, step 0.05) plus an **Apply** button
- Applies a uniform size multiplier to all images except the staff; saved to config and images are reloaded immediately

### Mode Selection
- Radio buttons: **Staff** / **Letters**
- **Start** button (green) launches the selected mode

### Debug Selection
- Radio buttons: **Note on scale** / **sharp location** / **flat location** / **notes above scale** / **notes below scale**
- **Start Debug** button (orange) launches the selected debug screen

------

## Staff Mode

### Layout
- Progress bar across the top
- Canvas filling the remaining window height (responsive)
- "← Menu" button at the bottom

### Note rendering
1. A random note is chosen from the configured chromatic range. Accidentals are spelt as sharps or flats with equal probability (e.g. C#4 may display as C#4 or Db4).
2. The scale factor `sf` is computed for the current canvas height (see Image Scaling Model).
3. The treble clef staff image is drawn centred vertically in the canvas.
4. The note head is drawn at the correct diatonic position:
   - `pos` = diatonic staff position (E4 = 0, F4 = 1, …, A4 = 3, B4 = 4, C5 = 5, …)
   - `y = a4_y_eff − (pos − 3) × step_eff`
5. **Ledger lines** are drawn using the `line.png` image:
   - Below staff (pos ≤ −2): lines at every even position from −2 down to the note's position (or next even position below it), offset by `ledger_below_y_offset × sf`
   - Above staff (pos ≥ 10): lines at every even position from 10 up to the note's position (or next even position above it), offset by `ledger_above_y_offset × sf`
6. A sharp or flat symbol is drawn at `(cx + sharp/flat_x_offset × sf, ny + sharp/flat_y_offset × sf)` when applicable.
7. If the window is resized, the note is redrawn at the new scale without resetting the hold timer.

### Note detection & progression
- Audio is polled every 50 ms
- When `RMS > mic_threshold` **and** the detected pitch matches the target note (enharmonic equivalence via MIDI number), a hold timer starts
- When the note has been held for `note_duration` seconds continuously, the background flashes lime green (#32cd32) for 400 ms, then the next note is shown
- If the note is released or changes, the hold timer resets
- Progress bar value advances by 1 per correct note
- After all notes are completed, a "Lesson Complete!" screen is shown with a "← Menu" button

------

## Letters Mode

Identical flow to Staff mode but displays the note name as large bold text (font size 80) instead of a staff image.

------

## Debug Screens

All debug screens use a fixed 800×440 canvas with the staff drawn at the debug reference scale (staff centred at y = 220). This ensures calibrated values transfer directly to the game, which uses the same coordinate origin.

Each screen has a **Save & Back** button that writes the new values to `config.json` and returns to the main menu.

### Note on Scale
- **Purpose:** Calibrate `a4_y` (vertical position of A4) and `step_height` (pixels per diatonic step)
- Two note heads are drawn side by side: A4 on the left, C5 on the right
- **A4 ▲/▼ buttons:** Move both notes together (adjusts `a4_y`); use this to align the left note with the A4 line on the staff
- **C5 offset ▲/▼ buttons:** Move only the C5 note (adjusts the two-step pixel distance); use this to align the right note with the C5 space on the staff
- The status line shows `a4_y`, the current C5 offset, and the derived `step_height` (= C5 offset ÷ 2)
- On save: `a4_y` = current A4 position; `step_height` = C5 offset ÷ 2

### Sharp Location
- **Purpose:** Calibrate `sharp_x_offset` and `sharp_y_offset`
- Draws a note at A4 and the sharp symbol; arrow buttons (◄ ▲ ▼ ►) move the sharp symbol 1 px at a time
- Status line shows current offsets
- On save: writes `sharp_x_offset` and `sharp_y_offset`

### Flat Location
- **Purpose:** Calibrate `flat_x_offset` and `flat_y_offset`
- Same layout as Sharp Location but for the flat symbol
- On save: writes `flat_x_offset` and `flat_y_offset`

### Notes Above Scale
- **Purpose:** Calibrate `ledger_above_y_offset`
- Blank canvas (no staff); note and ledger line are centred
- ▲/▼ buttons move the ledger line relative to the note
- On save: writes `ledger_above_y_offset`

### Notes Below Scale
- **Purpose:** Calibrate `ledger_below_y_offset`
- Same layout as Notes Above Scale
- On save: writes `ledger_below_y_offset`

------

## Note Range Limits

The absolute playable range is **B3** (lowest) to **C7** (highest). The game's auto-scaling guarantees both extremes are always visible within the canvas regardless of window height. The user-configurable lower/upper bounds may be any notes within this range (or beyond — the scaling will still ensure visibility).

------

## Audio Engine

- PyAudio stream: float32, mono, 44100 Hz, 4096-sample chunks, non-blocking callback
- **Volume:** RMS of each chunk
- **Pitch detection:** Autocorrelation on the mean-centred chunk; finds the first local minimum then the subsequent peak lag; frequency = 44100 ÷ peak_lag; valid range 60–4200 Hz
- Note is identified only when RMS > 0.005 (hard floor, separate from the user-adjustable threshold)
- Enharmonic matching: both spellings of a chromatic note are accepted (C#4 and Db4 both match MIDI 61)

------

## File Layout

```
music_lessons.py      — main script
config.json           — persistent settings (auto-created)
images/
    staff.png
    note.png
    line.png
    sharp.png
    flat.png
```

------

## Dependencies

```
python >= 3.9
pyaudio
numpy
Pillow
```

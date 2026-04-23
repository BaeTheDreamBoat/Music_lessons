# Functional Specification Document

## Music Lessons — Version 3.0

------

## General Requirements

- **Language:** Python 3
- **GUI framework:** Tkinter with ttk widgets
- **Audio:** PyAudio (44100 Hz, mono, float32) for both microphone input (autocorrelation pitch detection) and synthesized tone output (callback-based sine wave)
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
| `lower_note` | `C4` | Lower bound of the general note range |
| `upper_note` | `B5` | Upper bound of the general note range |
| `sound_lower_note` | `C4` | Lower bound of the sound-mode note range |
| `sound_upper_note` | `B4` | Upper bound of the sound-mode note range |
| `num_notes` | `10` | Number of notes per lesson |
| `note_duration` | `2.0` | Seconds the correct note must be held (mic modes) |
| `tone_duration` | `1.5` | Seconds the synthesized tone plays |
| `tone_volume` | `0.5` | Amplitude of synthesized tone (0.05–1.0) |
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
| `note_stats_<mode>` | `{}` | Per-note adaptive stats for each mode, keyed by note name string |

Config is saved immediately whenever any setting changes.

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

### Window behaviour
- The window opens centred on the screen at 920×740.
- After the menu is built, `minsize` is set to the menu's required dimensions so the window cannot be dragged smaller than the content.
- If the window is already smaller than the required size (e.g. returning from a lesson at a reduced size), it is resized to fit automatically.
- The menu frame uses `rowconfigure(weight=1)` on every row so available vertical space is distributed evenly between all rows — elements spread out in a large window and compress toward minimum height in a small one, without scrolling.

### Note Range
- **Lower** and **Upper** combo boxes, read-only, listing every note from C0–B8 in scientific pitch notation; chromatic notes are displayed with both spellings (e.g. `C#4/Db4`), natural notes as plain names (e.g. `C4`)
- Used by: **Play By Staff Location**, **Play By Note Name**
- Selection is saved to config immediately on change

### Sound Range
- Separate **Lower** and **Upper** combo boxes with the same display format as Note Range
- Used exclusively by: **Identify Note By Sound**, **Play By Sound**
- Default range C4–B4 (one octave); intended to be narrower than the general range to suit the higher difficulty of these modes
- Selection is saved to config immediately on change

### Number of Notes
- Spinbox, range 1–200, default 10
- Saved when the lesson starts

### Hold Duration (s)
- Spinbox, range 0.5–10.0, step 0.5, default 2.0 seconds
- The note must be held continuously above the mic threshold for this duration to count as correct (mic-based modes only)
- Saved when the lesson starts

### Tone Duration (s)
- Spinbox, range 0.5–10.0, step 0.5, default 1.5 seconds
- Duration of the synthesized tone played in sound-based modes
- Saved when the lesson starts

### Tone Volume
- Spinbox, range 0.05–1.0, step 0.05, default 0.5
- Amplitude of the synthesized sine-wave tone
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
Radio buttons are arranged in two rows:

**Row 1 — Play modes** (use the general Note Range, mic input):
- Play By Staff Location
- Play By Note Name
- Play By Sound

**Row 2 — Identify modes** (use the Sound Range, button input):
- Identify Note By Staff Location
- Identify Note By Sound

**Start** button (green) launches the selected mode.

Each mode maintains independent note stats; switching modes does not affect other modes' history.

### Debug Selection
- Radio buttons: **Note on scale** / **sharp location** / **flat location** / **notes above scale** / **notes below scale**
- **Start Debug** button (orange) launches the selected debug screen

------

## Play By Staff Location Mode

### Layout
- Progress bar across the top
- Canvas filling the remaining window height (responsive)
- "← Menu" button at the bottom

### Note rendering
1. A note is chosen from the expanded pool (see Adaptive Note Selection). Each chromatic pitch is represented as two separate entries — its sharp spelling and its flat spelling — so C#4 and Db4 are distinct choices with independent stats.
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
- On a correct note, elapsed time is recorded and the note's adaptive stats are updated
- Progress bar value advances by 1 per correct note
- After all notes are completed, a "Lesson Complete!" screen is shown with a "← Menu" button

------

## Play By Note Name Mode

Identical flow to Play By Staff Location but displays the note name as large bold text (font size 80) instead of a staff image. Has its own independent note stats.

------

## Play By Sound Mode

### Layout
- Progress bar across the top
- Large `?` label (font size 80, grey) filling the centre — nothing is shown that reveals the note identity
- **Replay** button to replay the current tone
- "← Menu" button at the bottom

### Flow
1. When a note is shown, the synthesized tone is played immediately via `AudioEngine.play_tone`
2. Listening for the correct pitch begins immediately alongside playback (the user may play along or after the tone ends)
3. Detection and progression are identical to Play By Staff Location (mic threshold, hold duration, flash, stats update)
4. **Replay** replays the tone at any time; it interrupts any currently playing tone
5. Uses the **Sound Range** note pool

------

## Identify Note By Staff Location Mode

### Layout
- Progress bar across the top
- Staff canvas (same rendering as Play By Staff Location, responsive)
- Two rows of answer buttons:
  - **Top row:** note name buttons — one per chromatic pitch present in the active pool, labelled with enharmonic pairs where applicable (e.g. `C#/Db`), ordered C → B
  - **Bottom row:** octave buttons — one per octave present in the active pool, labelled `0`–`9`
- "← Menu" button at the bottom

### Button filtering
Only note names and octave numbers actually present in the active pool are shown. For example, a pool of C5–D5 produces three name buttons (`C`, `C#/Db`, `D`) and one octave button (`5`). Fewer buttons means each button is wider.

### Interaction
- No audio listening; progression is entirely button-driven
- Clicking a **wrong** button turns it red; the button remains red and other buttons may still be clicked
- Clicking the **correct** button turns it green
- Once both the correct name button and the correct octave button are green, all buttons are disabled and the correct-note flash/advance sequence fires (identical to mic modes)
- Stats are tracked identically to mic modes

------

## Identify Note By Sound Mode

### Layout
- Progress bar across the top
- Large `?` label (font size 80, grey)
- Control row: **Replay** button and **Reference: C4** button side by side
- Two rows of answer buttons (same filtering logic as Identify Note By Staff Location)
- "← Menu" button at the bottom

### Flow
1. When a note is shown, the synthesized tone plays immediately
2. The user clicks the matching note name and octave buttons
3. Button interaction is identical to Identify Note By Staff Location (wrong = red, correct = green, both correct = advance)
4. **Replay** replays the current question tone, interrupting any in-progress playback
5. **Reference: C4** always plays a C4 tone at the current tone volume and duration, giving the user a pitch anchor; this button is never disabled
6. Uses the **Sound Range** note pool

------

## Adaptive Note Selection

Each mode tracks per-note statistics that bias which notes appear in future lessons. Stats are stored in `config.json` under `note_stats_<mode name>`, keyed by note name string. Each entry has four fields:

| Field | Initial value | Description |
|-------|---------------|-------------|
| `avg_time` | `5.0` | Running average of adjusted play time in seconds |
| `count` | `0` | Number of times this note has been played |
| `win_streak` | `0` | Consecutive notes played faster than average (max 3) |
| `loss_streak` | `0` | Consecutive notes played slower than average (max 3) |

### Expanded pool
Before building the sequence, the chromatic note pool is expanded so every chromatic pitch appears as **two entries** — its sharp spelling and its flat spelling (e.g. `C#4` and `Db4`). Natural notes appear once. Each entry has its own independent stats.

### Note weighting
Each entry in the expanded pool is assigned a weight equal to its `avg_time` (default 5.0 for unseen entries). Notes are drawn via weighted random selection, so entries with a higher average time appear proportionally more often.

### 2-note cooldown
The same pitch (by MIDI number) cannot appear — in either spelling — until at least 2 other pitches have been played.

### Stats update (on each correct note)
Let `elapsed` = wall-clock seconds from note display to correct answer.

1. **Cap:** `capped = min(elapsed, 5.0)`
2. **Classify:**
   - If `capped > avg_time` (slower — loss): reset `win_streak` to 0; increment `loss_streak` (max 3); `adjusted = avg_time + (capped − avg_time) × (loss_streak / 3)`
   - If `capped ≤ avg_time` (faster — win): reset `loss_streak` to 0; increment `win_streak` (max 3); `adjusted = avg_time − (avg_time − capped) × (win_streak / 3)`
3. **Running average:** `avg_time = (avg_time × count + adjusted) / (count + 1)`; `count += 1`
4. Config is saved immediately after each update.

------

## Audio Engine

### Microphone input
- PyAudio input stream: float32, mono, 44100 Hz, 4096-sample chunks, non-blocking callback
- **Volume:** RMS of each chunk
- **Pitch detection:** Autocorrelation on the mean-centred chunk; finds the first local minimum then the subsequent peak lag; frequency = 44100 ÷ peak_lag; valid range 60–4200 Hz
- Note is identified only when RMS > 0.005 (hard floor, separate from the user-adjustable threshold)

### Tone synthesis (`play_tone`)
- Generates a full-duration sine wave buffer in NumPy before playback begins (no streaming artifacts)
- A 20 ms linear fade-in and fade-out envelope is applied to eliminate clicks
- Playback uses a **callback-based PyAudio output stream** (`frames_per_buffer=2048`); the callback runs on PyAudio's internal audio thread, bypassing Python's GIL for glitch-free delivery
- Non-blocking: launched on a daemon thread; the main thread is never stalled
- **Interruptible:** each call to `play_tone` sets a stop event on the previous playback before starting a new one; the callback checks the event each frame and signals `paAbort` immediately when set — used by the Replay button to cut off the current tone
- Signature: `play_tone(note: str, duration: float, volume: float)`

------

## Debug Screens

All debug screens use a fixed 800×440 canvas with the staff drawn at the debug reference scale (staff centred at y = 220).

Each screen has a **Save & Back** button that writes the new values to `config.json` and returns to the main menu.

### Note on Scale
- **Purpose:** Calibrate `a4_y` and `step_height`
- Two note heads drawn side by side: A4 on the left, C5 on the right
- **A4 ▲/▼:** Move both notes together (adjusts `a4_y`)
- **C5 offset ▲/▼:** Move only the C5 note (adjusts `step_height` = C5 offset ÷ 2)

### Sharp Location
- **Purpose:** Calibrate `sharp_x_offset` and `sharp_y_offset`
- Arrow buttons move the sharp symbol 1 px at a time relative to A4

### Flat Location
- **Purpose:** Calibrate `flat_x_offset` and `flat_y_offset`
- Same layout as Sharp Location

### Notes Above Scale
- **Purpose:** Calibrate `ledger_above_y_offset`
- ▲/▼ buttons move the ledger line relative to the note

### Notes Below Scale
- **Purpose:** Calibrate `ledger_below_y_offset`
- Same layout as Notes Above Scale

------

## Note Range Limits

The absolute playable range is **B3** (lowest) to **C7** (highest). The game's auto-scaling guarantees both extremes are always visible. The user-configurable bounds may be any notes within or beyond this range.

------

## File Layout

```
music_lessons.py                — entry point; constants, utilities, AudioEngine, App coordinator
menu.py                         — MainMenu GUI and lesson-launch logic
play_by_staff_location.py       — StaffLesson: staff rendering and mic detection loop
play_by_note_name.py            — LettersLesson: large-text note display and mic detection loop
play_by_sound.py                — SoundLesson: tone playback and mic detection loop
identify_by_staff_location.py   — IdentifyStaffLesson: staff rendering and button identification
identify_by_sound.py            — IdentifySoundLesson: tone playback and button identification
progress_report.py              — BasLesson (shared audio loop), build_sequence, update_note_stats
debug_menus.py                  — DebugMenus: all five calibration screens
config.json                     — persistent settings (auto-created)
images/
    staff.png
    note.png
    line.png
    sharp.png
    flat.png
```

### Module responsibilities

| Module | Key exports |
|---|---|
| `music_lessons.py` | Constants (`NOTE_NAMES`, `SHARP_TO_FLAT`, `CANVAS_W/H`, …), utility functions (`parse_note`, `note_to_midi`, `staff_pos`, `same_midi`, …), `load_config` / `save_config`, `AudioEngine`, `App` |
| `menu.py` | `MainMenu` — builds the main menu; mic bar; range/mode selectors; delegates lesson and debug launch |
| `play_by_staff_location.py` | `StaffLesson(BasLesson)` — scales and renders the treble clef staff, note head, ledger lines, and accidentals |
| `play_by_note_name.py` | `LettersLesson(BasLesson)` — displays the note name as large bold text |
| `play_by_sound.py` | `SoundLesson(BasLesson)` — plays a synthesized tone and listens for the matching pitch |
| `identify_by_staff_location.py` | `IdentifyStaffLesson(BasLesson)` — renders staff; presents filtered note-name and octave buttons |
| `identify_by_sound.py` | `IdentifySoundLesson(BasLesson)` — plays a synthesized tone; presents filtered buttons; Reference C4 button |
| `progress_report.py` | `BasLesson` — shared audio-polling loop (`_listen`, `_poll`, `_hit`, `_advance`, `_complete`); `build_sequence`; `update_note_stats` |
| `debug_menus.py` | `DebugMenus` — five debug/calibration screens |

### Import strategy

`music_lessons.py` uses **lazy imports** (inside methods) when loading sub-modules, so each sub-module can safely do top-level `from music_lessons import …` without circular-import issues. Sub-modules never import from each other.

------

## Dependencies

```
python >= 3.9
pyaudio
numpy
Pillow
```

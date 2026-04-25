# Functional Specification Document

## Music Lessons — Version 4.1

------

## General Requirements

- **Language:** Python 3
- **GUI framework:** Tkinter with ttk widgets
- **Audio:** PyAudio (44100 Hz, mono, float32) for both microphone input (autocorrelation pitch detection) and synthesized tone output (callback-based sine wave)
- **Image handling:** Pillow (PIL)
- **Graphing:** Matplotlib (FigureCanvasTkAgg embedded in Tkinter)
- **Config persistence:** JSON file (`config.json`) stored alongside the script
- **Lesson history persistence:** JSON file (`note_stats.json`) stored alongside the script
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
| `lesson_duration` | `5.0` | Lesson length in minutes |
| `note_duration` | `2.0` | Seconds the correct note must be held (mic modes) |
| `tone_duration` | `1.5` | Seconds the synthesized tone plays |
| `tone_volume` | `0.5` | Amplitude of synthesized tone (0.05–1.0) |
| `startup_delay` | `3` | Countdown seconds shown before each lesson begins (0 = no countdown) |
| `playlist_selected` | `[]` | List of mode name strings checked in the Play List section |
| `playlist_reps` | `1` | Times each selected playlist lesson repeats before advancing to the next |
| `mic_threshold` | `0.02` | Minimum RMS volume to register a note |
| `mic_device_index` | `null` | PyAudio input device index (null = system default) |
| `note_scale` | `1.0` | Size multiplier for note/sharp/flat/line images |
| `a4_y` | `238` | Absolute canvas Y coordinate of A4 in the debug reference canvas (800×440) |
| `step_height` | `28.5` | Pixels per diatonic step at the debug reference scale |
| `sharp_x_offset` | `74` | X offset of sharp symbol from note centre, in debug pixels |
| `sharp_y_offset` | `0` | Y offset of sharp symbol from note centre, in debug pixels |
| `flat_x_offset` | `58` | X offset of flat symbol from note centre, in debug pixels |
| `flat_y_offset` | `-28` | Y offset of flat symbol from note centre, in debug pixels |
| `ledger_above_y_offset` | `-2` | Y offset of ledger line relative to note centre when above the staff, in debug pixels |
| `ledger_below_y_offset` | `0` | Y offset of ledger line relative to note centre when below the staff, in debug pixels |
| `note_stats_<mode>` | `{}` | Per-note adaptive stats for each mode, keyed by note name string |

Config is saved immediately whenever any setting changes. Serialization (`json.dumps`) runs on the main thread; the actual file write runs on a daemon background thread so the UI is never blocked by disk I/O.

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

### Lesson Duration (min)
- Spinbox, range 0.5–60.0, step 0.5, default 5.0 minutes
- Controls how long each lesson runs; the lesson ends automatically when the time expires regardless of how many notes have been completed
- Saved when the lesson starts

### Hold Duration (s)
- Spinbox, range **0.25–10.0, step 0.25**, default 2.0 seconds
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

### Start Delay (s)
- Spinbox, range 0–10, step 1, default 3 seconds; integer
- Number of seconds in the countdown shown before each lesson begins
- Setting to 0 disables the countdown entirely
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
- The **Start Delay (s)** spinbox sits on the same row as Note Scale, to the right of the Apply button

### Mode Selection
Radio buttons are arranged in two rows:

**Row 1 — Play modes** (use the general Note Range, mic input):
- Play By Staff Location
- Play By Note Name
- Play By Sound

**Row 2 — Identify modes:**
- Identify Note By Staff Location
- Identify Note By Sound

**Start** button (green) launches the selected mode.

The selected mode is remembered for the duration of the application session (`App._last_mode`); returning to the menu after a lesson restores the last-used selection. This state is not persisted across restarts.

Each mode maintains independent note stats; switching modes does not affect other modes' history.

### Play List
A section below Mode Selection that lets the user queue multiple lessons to run back-to-back.

**Fixed lesson order** (regardless of which lessons are selected):
1. Identify Note By Staff Location
2. Play By Staff Location
3. Play By Note Name
4. Play By Sound
5. Identify Note By Sound

**Controls:**
- **Five checkboxes** — one per lesson in the fixed order, arranged in a 3+2 grid. Checked lessons are included in the playlist; unchecked lessons are skipped.
- **Repetitions** spinbox (1–20, step 1, default 1) — how many times each selected lesson runs before advancing to the next. A value of 2 means each checked lesson plays twice consecutively before moving on.
- **Start Playlist** button (dark blue) — builds the step list and launches the first lesson.

**Persistence:** Both the checkbox states (`playlist_selected`) and the repetitions value (`playlist_reps`) are saved to `config.json` immediately whenever they change, and restored on the next application launch.

**Playlist execution:**
1. The step list is the ordered sequence of selected modes, each repeated `reps` times: e.g. two selected modes with reps=2 produces four steps.
2. Each step launches the appropriate lesson class using the same note pool and duration as a manually started lesson.
3. When a lesson finishes, the full **Completion Screen** is shown (see below). The button row contains both "← Menu" and a dark-blue **"Next: {next lesson name} →"** button (or **"Finish →"** on the last step).
4. Clicking "← Menu" at any point (during a lesson or on the completion screen) exits the playlist and returns to the main menu.
5. After all steps complete, the application returns to the main menu automatically.

### Debug Selection
- Radio buttons: **Note on scale** / **sharp location** / **flat location** / **notes above scale** / **notes below scale**
- **Start Debug** button (orange) launches the selected debug screen

------

## Time-Based Lesson Flow

All lesson modes share the same time-based progression system managed by `BasLesson`.

### Sequence pre-generation
At lesson start, a note sequence is generated with `max(200, lesson_duration_s × 2)` entries — enough buffer to ensure the sequence is never exhausted before the timer fires, even at the fastest possible play speed.

### Pre-lesson countdown
Before every lesson, `BasLesson._begin(duration_s)` is called instead of starting the lesson directly. If `startup_delay > 0`, a large countdown number is displayed as a full-screen overlay on the lesson background. The overlay counts down one second per tick and is destroyed when it reaches zero, at which point `_draw_next()` and `_start_lesson_timer()` are called. Setting `startup_delay` to 0 skips the overlay entirely.

### Lesson timer
- `_start_lesson_timer(duration_s)` records the start time (offset by any pending pause accumulated during the countdown phase) and begins a 500 ms repeating tick.
- Each tick computes `elapsed = max(0.0, now − lesson_start_time)` and updates the progress bar value to `elapsed` (maximum = `lesson_duration_s`).
- When `elapsed >= lesson_duration_s`, the lesson ends and the completion screen is shown.

### Time refunds on correct answers
When a note is answered correctly, `BasLesson._add_time(seconds)` is called, which extends `_lesson_duration_s` and updates `_prog['maximum']`. The progress bar's endpoint visibly extends, rewarding the player with extra time. Two sources of refund are applied on every correct answer:

| Refund | Amount | Applies to |
|--------|--------|-----------|
| Green flash | 0.4 s | All lesson modes |
| Note hold | `note_duration` s | Play By Staff Location, Play By Note Name, Play By Sound only |

Identify modes (Identify Note By Staff Location, Identify Note By Sound) receive only the flash refund because button presses are instantaneous — no hold time was spent. This is controlled by the class attribute `_note_hold_refund` (`True` on `BasLesson`, overridden to `False` on both identify lesson classes).

### Timer pause during auto-play tones
In **Play By Sound** and **Identify Note By Sound**, when a new note's tone plays automatically at the start of each question, the lesson timer is paused for `tone_duration` seconds so that time spent listening does not count against the lesson. Pressing **Replay** does not pause the timer.

Implementation: `BasLesson._pause_for_tone()` shifts `_lesson_start_time` forward by `tone_duration`. Because `elapsed` is clamped to `max(0.0, …)`, no negative values reach the progress bar. `_lesson_duration_s` and `_prog['maximum']` are not modified, so the lesson always ends at exactly the configured duration of active play time.

For the first note, `_pause_for_tone()` is called before `_start_lesson_timer()` has run. The shift amount is stored in `_pending_pause` and applied when `_start_lesson_timer()` sets `_lesson_start_time`.

### Early termination guard
Every callback that could fire after lesson end (`_poll`, `_hit`, `_advance`) checks a `_lesson_ended` flag and returns immediately if set, preventing double-completion or UI corruption.

------

## Play By Staff Location Mode

### Layout
- Time-based progress bar across the top (fills left-to-right as the lesson time elapses)
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
- On a correct note, elapsed time is recorded, the note's adaptive stats are updated, `_notes_completed` is incremented, and time is refunded (flash + hold duration)
- The lesson ends when the time limit expires; the completion screen is shown

------

## Play By Note Name Mode

Identical flow to Play By Staff Location but displays the note name as large bold text (font size 80) instead of a staff image. Has its own independent note stats.

------

## Play By Sound Mode

### Layout
- Time-based progress bar across the top
- Large `?` label (font size 80, grey) filling the centre — nothing is shown that reveals the note identity
- **Replay** button to replay the current tone
- "← Menu" button at the bottom

### Flow
1. When a new question begins, the lesson timer is paused for `tone_duration` seconds, then the synthesized tone plays via `AudioEngine.play_tone`
2. Listening for the correct pitch begins immediately alongside playback (the user may play along or after the tone ends)
3. Detection and progression are identical to Play By Staff Location (mic threshold, hold duration, flash, stats update, time refunds)
4. **Replay** replays the tone at any time; it interrupts any currently playing tone but does **not** pause the lesson timer
5. Uses the **Sound Range** note pool

------

## Identify Note By Staff Location Mode

### Layout
- Time-based progress bar across the top
- Staff canvas (same rendering as Play By Staff Location, responsive)
- Two rows of answer buttons:
  - **Top row:** note name buttons — one per chromatic pitch present in the active pool, labelled with enharmonic pairs where applicable (e.g. `C#/Db`), ordered C → B
  - **Bottom row:** octave buttons — one per octave present in the active pool, labelled `0`–`9`
- "← Menu" button at the bottom

### Button filtering
Only note names and octave numbers actually present in the active pool are shown. For example, a pool of C5–D5 produces three name buttons (`C`, `C#/Db`, `D`) and one octave button (`5`). Fewer buttons means each button is wider.

### Single-octave optimisation
When the active pool spans exactly one octave, the octave row is hidden entirely and the octave is auto-selected at the start of each note. A correct answer then requires only **one click** (the note name). When the pool spans multiple octaves the octave row is shown as normal.

### Interaction
- No audio listening; progression is entirely button-driven
- Clicking a **wrong** button turns it red; the button remains red and other buttons may still be clicked
- Clicking the **correct** button turns it green
- Once both the correct name and octave are confirmed (either by click or auto-selection), all buttons are disabled and the correct-note flash/advance sequence fires (identical to mic modes)
- On a correct answer, time is refunded (flash only; no hold duration)
- Stats are tracked identically to mic modes

------

## Identify Note By Sound Mode

### Layout
- Time-based progress bar across the top
- Large `?` label (font size 80, grey)
- Control row: **Replay** button and **Reference: C4** button side by side
- Two rows of answer buttons (same filtering logic as Identify Note By Staff Location)
- "← Menu" button at the bottom

### Flow
1. When a new question begins, the lesson timer is paused for `tone_duration` seconds, then the synthesized tone plays
2. The user clicks the matching note name and octave buttons
3. Button interaction is identical to Identify Note By Staff Location (wrong = red, correct = green, both correct = advance); the single-octave optimisation applies here too
4. On a correct answer, time is refunded (flash only; no hold duration)
5. **Replay** replays the current question tone, interrupting any in-progress playback; does **not** pause the timer
6. **Reference: C4** always plays a C4 tone at the current tone volume and duration, giving the user a pitch anchor; this button is never disabled
7. Uses the **Sound Range** note pool

------

## Completion Screen

Shown automatically when the lesson timer expires (or, as a safety net, if the pre-generated sequence is exhausted).

### Summary stats
- **"Lesson Complete!"** heading (font size 36, green)
- **"Avg notes/min: X"** — the average notes completed per minute for this session, rounded to one decimal place

### Historical performance graph
A Matplotlib line graph (with filled area) embedded via `FigureCanvasTkAgg` showing past session performance for the current mode, drawn from `note_stats.json`. Four toggle buttons control the view:

| Toggle | X-axis | Data shown |
|--------|--------|------------|
| **Current** | Session timestamp (date + HH:MM) | Last 10 individual sessions, unaveraged |
| **Week** | Day of week (e.g. "Mon 21") | Daily average over the past 7 calendar days; all 7 days shown (zero if no data) |
| **Month** | Week label (e.g. "Apr W2") | Weekly average over the past 4 weeks |
| **Year** | Month label (e.g. "Jan 25") | Monthly average over the past 12 calendar months; all 12 months shown (zero if no data) |

All views are filtered to the current lesson mode so each mode has its own independent history.

### Navigation buttons
The button row at the bottom of the completion screen contains:

- **"← Menu"** — always present; returns to the main menu (and exits the playlist if one is running)
- **"Next: {lesson name} →"** (dark blue) — present only when this lesson was launched as part of a playlist and there are more steps remaining; advances to the next playlist step
- **"Finish →"** (dark blue) — present only when this lesson was the last step in a playlist; returns to the main menu

------

## Lesson Session Statistics

Each completed lesson appends one record to `note_stats.json` (created on first use, stored alongside the script).

### Record format
```json
{
  "date": "2026-04-22",
  "time": "14:30:00",
  "mode": "Play By Staff Location",
  "avg_notes_per_min": 12.5
}
```

| Field | Description |
|-------|-------------|
| `date` | ISO date of the lesson (YYYY-MM-DD) |
| `time` | Local time the lesson ended (HH:MM:SS) |
| `mode` | Lesson mode name string (matches the radio button label) |
| `avg_notes_per_min` | Average notes per minute for the session, rounded to 1 decimal place (see calculation below) |

### Avg notes per minute calculation
`avg_notes_per_min` is derived from the individual **response times** recorded for each correct answer during the lesson — not from the total lesson duration.

**Response time per note** = wall-clock seconds from when the note was displayed to when the correct answer was registered, **minus** `tone_duration` for modes that auto-play a tone (Play By Sound, Identify Note By Sound). This isolates the player's reaction/thinking time, excluding time spent passively listening to the tone. Response time is floored at 0.1 s.

**Session avg:** `avg_notes_per_min = 60 ÷ mean(response_times)`

If no notes were completed the value is 0.0.

Records are append-only; existing entries are never modified or deleted. Playlist lessons each append their own record independently.

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
Let `response_time` = wall-clock seconds from note display to correct answer, minus `tone_duration` for sound modes (same value used for `avg_notes_per_min`; floored at 0.1 s).

1. **Cap:** `capped = min(response_time, 5.0)`
2. **Classify:**
   - If `capped > avg_time` (slower — loss): reset `win_streak` to 0; increment `loss_streak` (max 3); `adjusted = avg_time + (capped − avg_time) × (loss_streak / 3)`
   - If `capped ≤ avg_time` (faster — win): reset `loss_streak` to 0; increment `win_streak` (max 3); `adjusted = avg_time − (avg_time − capped) × (win_streak / 3)`
3. **Running average:** `avg_time = (avg_time × count + adjusted) / (count + 1)`; `count += 1`
4. Config is saved after each update (async file write; see Config section).

------

## Audio Engine

### Microphone input
- PyAudio input stream: float32, 44100 Hz, 4096-sample chunks, non-blocking callback
- **Channel count:** determined at stream-open time by querying the selected device's `maxInputChannels`; the stream opens with 1 channel if supported, otherwise 2. If the device's reported channel count is unusable, the engine falls back through all available input devices until one succeeds.
- **Multi-channel mix-down:** if the stream opens with more than one channel, the callback averages all channels to produce a mono signal before pitch/volume processing.
- **Graceful startup failure:** if no input device can be opened, the app logs a warning and continues without mic functionality instead of crashing. The user can select a working device via the Mic Device dropdown in the main menu.
- **Volume:** RMS of each (mono) chunk
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
progress_report.py              — BasLesson (shared loop, timer, completion screen, stats graph),
                                  build_sequence, update_note_stats
debug_menus.py                  — DebugMenus: all five calibration screens
config.json                     — persistent settings (auto-created)
note_stats.json                 — lesson session history: date, time, mode, avg_notes_per_min (auto-created)
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
| `music_lessons.py` | Constants (`NOTE_NAMES`, `SHARP_TO_FLAT`, `NOTE_STATS_FILE`, `CANVAS_W/H`, …), utility functions (`parse_note`, `note_to_midi`, `staff_pos`, `same_midi`, …), `load_config` / `save_config` (async write) / `save_lesson_stats(mode, avg_per_min)`, `AudioEngine` (multi-channel with device fallback), `App` |
| `menu.py` | `MainMenu` — builds the main menu; mic bar; range/mode/duration selectors; Play List section; delegates lesson, playlist, and debug launch |
| `play_by_staff_location.py` | `StaffLesson(BasLesson)` — scales and renders the treble clef staff, note head, ledger lines, and accidentals |
| `play_by_note_name.py` | `LettersLesson(BasLesson)` — displays the note name as large bold text |
| `play_by_sound.py` | `SoundLesson(BasLesson)` — pauses timer, plays a synthesized tone, and listens for the matching pitch |
| `identify_by_staff_location.py` | `IdentifyStaffLesson(BasLesson)` — renders staff; presents filtered note-name and octave buttons; `_note_hold_refund = False` |
| `identify_by_sound.py` | `IdentifySoundLesson(BasLesson)` — pauses timer, plays a synthesized tone; presents filtered buttons; Reference C4 button; `_note_hold_refund = False` |
| `progress_report.py` | `BasLesson` — countdown (`_begin`, `_countdown_tick`), lesson timer (`_start_lesson_timer`, `_time_tick`, `_add_time`, `_pause_for_tone`), correct-note flow (`_hit`), completion screen with playlist-aware button row (`_complete`, `_draw_stats_graph`); `build_sequence`; `update_note_stats` |
| `debug_menus.py` | `DebugMenus` — five debug/calibration screens |

### Key `BasLesson` attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `_note_hold_refund` | class bool | `True` for play modes; `False` for identify modes — controls whether `note_duration` is refunded on correct answers |
| `_playlist_callback` | callable or None | Set by the playlist runner before `show()`; called by `_complete()` to advance to the next step |
| `_playlist_next_label` | str or None | Mode name of the next playlist step; used to label the Next button on the completion screen |
| `_pending_pause` | float | Accumulated pause time to apply when the lesson timer starts (used when `_pause_for_tone` is called before `_start_lesson_timer`) |
| `_note_times` | list[float] | Response time (seconds) recorded for each correct answer in the current lesson; used to compute `avg_notes_per_min` at completion |
| `_note_tone_duration` | float | Tone duration to subtract from elapsed time in `_hit()`; set by `_pause_for_tone()` and reset to 0.0 after each hit |
| `_original_lesson_duration_s` | float | The configured lesson duration at start time; preserved even as `_lesson_duration_s` grows from time refunds |

### Import strategy

`music_lessons.py` uses **lazy imports** (inside methods) when loading sub-modules, so each sub-module can safely do top-level `from music_lessons import …` without circular-import issues. Sub-modules never import from each other.

------

## Dependencies

```
python >= 3.9
pyaudio
numpy
Pillow
matplotlib
```

# Music Lessons

An interactive note recognition trainer for musicians. Practice reading staff notation, identifying notes by ear, and playing notes on command — all timed, adaptive, and tracked over time.

## Modes

| Mode | Input | Description |
|------|-------|-------------|
| **Play By Staff Location** | Microphone | A note is shown on a treble clef staff; play the matching pitch |
| **Play By Note Name** | Microphone | A note name is shown in large text; play the matching pitch |
| **Play By Sound** | Microphone | A tone plays; play back the matching pitch |
| **Identify Note By Staff Location** | Buttons | A note is shown on staff; click the matching name and octave buttons |
| **Identify Note By Sound** | Buttons | A tone plays; click the matching name and octave buttons |

All modes are time-based. Correct answers refund time, keeping the lesson going as long as you're playing well. Performance is tracked per-mode and displayed as a graph on the completion screen.

## Requirements

- Python 3.9+
- A microphone (for the three Play modes)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running

```bash
python music_lessons.py
```

## Settings

All settings are available in the main menu and saved automatically to `config.json`.

| Setting | Description |
|---------|-------------|
| Note Range | Lower/upper bounds for staff and name modes |
| Sound Range | Lower/upper bounds for sound-based modes |
| Lesson Duration | How long each lesson runs (minutes) |
| Hold Duration | How long a note must be held to count (mic modes) |
| Tone Duration | How long the synthesized tone plays |
| Tone Volume | Volume of the synthesized tone |
| Start Delay | Countdown seconds before each lesson |
| Mic Device | Select which input device to use |
| Mic Threshold | Minimum volume to register a note |

## Play List

Select multiple modes and a repetition count to run lessons back-to-back automatically. Each completed lesson shows its results before advancing to the next.

## Adaptive Difficulty

Each note is tracked independently per mode. Notes you find harder (slower average response time) appear more frequently. Performance is measured as your average response time per note, excluding any time spent listening to auto-played tones.

## Progress Graphs

The completion screen shows your average notes/min history for the current mode across four views: last 10 sessions, past 7 days, past 4 weeks, and past 12 months.

## File Layout

```
music_lessons.py                — entry point and audio engine
menu.py                         — main menu
play_by_staff_location.py       — Play By Staff Location mode
play_by_note_name.py            — Play By Note Name mode
play_by_sound.py                — Play By Sound mode
identify_by_staff_location.py   — Identify Note By Staff Location mode
identify_by_sound.py            — Identify Note By Sound mode
progress_report.py              — shared lesson logic, timer, completion screen
debug_menus.py                  — staff calibration screens
images/                         — staff, note, accidental, and ledger line images
config.json                     — saved settings (auto-created)
note_stats.json                 — lesson history (auto-created, gitignored)
```

# JFDI - Just Fucking Do It

```
     _ _____ ____ ___
    | |  ___|  _ \_ _|
 _  | | |_  | | | | |
| |_| |  _| | |_| | |
 \___/|_|   |____/___|

 JUST FUCKING DO IT.
```

A CLI fitness tracker that pushes you to hit your daily exercise goals with Shia LaBeouf energy.

**Problem:** You get hooked up in work, forget to exercise, and when you do remember you can't recall how many reps you've done across sets.

**Solution:** JFDI tracks your sets throughout the day, shows your progress, and yells "DO IT!" at you via desktop notifications until you hit your goals.

## Features

- Track daily pushups, crunches, and any custom exercise toward configurable goals
- Log reps in sets throughout the day (`jfdi p 20` -- you just did 20 pushups)
- Background daemon sends macOS desktop notifications at configurable intervals
- Smart escalation: friendly in the morning, full Shia mode by evening if you're behind
- Configurable quiet hours (no 3am notifications)
- Streak tracking across days
- Custom notification messages and sounds
- "DO IT!" sound clip plays with notifications (Shia LaBeouf approved)
- Export history to CSV/JSON
- Built with a clean service layer -- GUI can be added without refactoring

## Installation

### pipx (recommended)

[pipx](https://pipx.pypa.io/) installs CLI tools in isolated environments so they don't pollute your system Python:

```bash
# From PyPI (once published)
pipx install jfdi

# Or directly from GitHub
pipx install git+https://github.com/Solarden/just-fucking-do-it.git
```

### Homebrew

```bash
brew tap Solarden/jfdi
brew install jfdi
```

## Quick Start

```bash
# Enable tab completion (recommended)
jfdi --install-completion

# Log some reps
jfdi log pushups 20
jfdi p 15           # shorthand alias
jfdi c 25           # 'c' = crunches

# Check progress
jfdi status

# Start the reminder daemon
jfdi daemon start
```

## Commands

### Logging

```bash
jfdi log pushups 20       # log 20 pushups
jfdi p 20                 # same thing (alias)
jfdi c 30                 # log 30 crunches
jfdi undo                 # undo last entry (typo protection)
```

### Progress

```bash
jfdi status               # today's progress with progress bars
jfdi history              # last 7 days
jfdi history --days 30    # last 30 days
jfdi streak               # current and best streaks
jfdi export               # export to CSV
jfdi export --format json # export to JSON
```

### Configuration

```bash
jfdi config show                   # view all settings
jfdi config interval 15            # notify every 15 minutes
jfdi config hours 9-21             # only notify 9am-9pm
jfdi config sound off              # mute sounds
jfdi config add burpees 100        # add a new exercise
jfdi config remove burpees         # remove an exercise
jfdi config alias burpees b        # set shorthand 'b' for burpees
```

### Messages

```bash
jfdi message list                  # see all notification messages
jfdi message list --category nudge # filter by category
jfdi message add nudge "Get off your ass!"
jfdi message add quote "Pain is temporary, glory is forever"
jfdi message remove 5              # remove message by ID
```

Categories: `nudge` (reminder), `quote` (motivational), `completion` (goal hit).

### Sounds

```bash
jfdi sound list                    # see available sounds
jfdi sound add airhorn ~/sounds/airhorn.mp3
jfdi sound use airhorn             # switch active sound
jfdi sound remove 2                # remove by ID
```

### Daemon

```bash
jfdi daemon start                  # start background notifications
jfdi daemon stop                   # stop notifications
jfdi daemon status                 # check if running
```

## Setting Up the "DO IT!" Sound

The app plays a sound with notifications. To set up the iconic Shia LaBeouf clip:

**Option 1 -- Manual download:**
Download any short MP3 clip and place it at `assets/do_it.mp3` in the project directory.

**Option 2 -- Using yt-dlp:**
```bash
pip install yt-dlp
yt-dlp -x --audio-format mp3 -o 'do_it.%(ext)s' \
  --download-sections '*0:00-0:03' \
  'https://www.youtube.com/watch?v=ZXsQAXx_ao0'
mv do_it.mp3 assets/do_it.mp3
```

**Option 3 -- Custom sound:**
```bash
jfdi sound add mysound ~/path/to/any/sound.mp3
jfdi sound use mysound
```

## Smart Escalation

The daemon adapts its tone based on your progress vs. time of day:

| Time of day | Your progress | Daemon tone |
|------------|---------------|-------------|
| Morning | On track | Friendly nudge + motivational quote |
| Afternoon | Falling behind | Urgent reminder + nudge message |
| Evening | Barely started | **FULL SHIA MODE** -- aggressive notifications + DO IT! sound |

## Architecture

The app uses a layered architecture for easy extensibility:

```
cli.py (presentation)  -->  service.py (business logic)  -->  db.py (SQLite)
                                    |
                              models.py (dataclasses)
```

- `models.py` -- Pure dataclasses, zero dependencies
- `service.py` -- All logic, returns model objects
- `cli.py` -- Thin layer that calls service and formats with Rich

A future GUI just imports `service.py` and renders the same data differently.

## Data Storage

All data lives in `~/.jfdi/`:
- `jfdi.db` -- SQLite database (exercises, logs, config, messages, sounds)
- `sounds/` -- User-added custom sound files
- `exports/` -- Exported CSV/JSON files

## Requirements

- Python 3.10+
- macOS (for desktop notifications via osascript and sound via afplay)

## Media Disclaimer

This project does **not** distribute, bundle, or include any copyrighted audio or video files. The `assets/` directory ships empty. The application provides functionality for users to configure their own sound files for notifications -- any media content that users download or add is obtained at their own discretion and responsibility. See `LICENSE` for full details.

## License

MIT -- see [LICENSE](LICENSE) for full text.

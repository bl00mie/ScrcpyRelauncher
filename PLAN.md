# ScrcpyRelauncher — Design Plan

## Overview
A Python tkinter GUI that wraps the `scrcpy` CLI tool. It provides dropdown selectors, text inputs, and checkboxes for common scrcpy options, persists settings in a JSON config file, and manages a scrcpy subprocess with launch/relaunch/close controls and optional auto-relaunch on termination.

## Architecture

```
ScrcpyRelauncher/
├── PLAN.md              # This file
├── config.json          # Persisted user settings (auto-created on first run)
└── scrcpy_relauncher.py # Single-file tkinter application
```

**Single-file approach** — the app is small enough to live in one module. Config is loaded/saved via `json`.

## Config File (`config.json`)

```json
{
  "serial": "",
  "window_title": "",
  "max_size": "0",
  "max_fps": "60",
  "video_bit_rate": "8M",
  "video_codec": "h264",
  "video_source": "display",
  "camera_id": "",
  "camera_facing": "",
  "camera_size": "",
  "camera_fps": "",
  "audio_source": "output",
  "no_audio": false,
  "no_control": false,
  "turn_screen_off": false,
  "stay_awake": false,
  "always_on_top": false,
  "fullscreen": false,
  "borderless": false,
  "show_touches": false,
  "power_off_on_close": false,
  "crop": "",
  "display_orientation": "0",
  "record_file": "",
  "record_format": "",
  "verbosity": "info",
  "extra_args": "",
  "relaunch_on_termination": false
}
```

## GUI Layout

### Device & Window Section
| Control | Type | scrcpy flag |
|---|---|---|
| Device serial / ID | Text entry | `--serial` |
| Window title | Text entry | `--window-title` |

### Video Section
| Control | Type | scrcpy flag |
|---|---|---|
| Max resolution | Dropdown (0, 480, 720, 1080, 1440, 2160 + custom) | `--max-size` |
| Max FPS | Dropdown (15, 24, 30, 60, 120 + custom) | `--max-fps` |
| Video bit rate | Dropdown (2M, 4M, 8M, 16M, 32M + custom) | `--video-bit-rate` |
| Video codec | Dropdown (h264, h265, av1) | `--video-codec` |
| Video source | Dropdown (display, camera) | `--video-source` |
| Display orientation | Dropdown (0, 90, 180, 270) | `--display-orientation` |

### Camera Section (enabled when video_source == "camera")
| Control | Type | scrcpy flag |
|---|---|---|
| Camera ID | Text entry | `--camera-id` |
| Camera facing | Dropdown (front, back, external) | `--camera-facing` |
| Camera size | Text entry (WxH) | `--camera-size` |
| Camera FPS | Text entry | `--camera-fps` |

### Audio Section
| Control | Type | scrcpy flag |
|---|---|---|
| Audio source | Dropdown (output, playback, mic, …) | `--audio-source` |
| No audio | Checkbox | `--no-audio` |

### Behavior Section
| Control | Type | scrcpy flag |
|---|---|---|
| No control (read-only) | Checkbox | `--no-control` |
| Turn screen off | Checkbox | `--turn-screen-off` |
| Stay awake | Checkbox | `--stay-awake` |
| Always on top | Checkbox | `--always-on-top` |
| Fullscreen | Checkbox | `--fullscreen` |
| Borderless | Checkbox | `--window-borderless` |
| Show touches | Checkbox | `--show-touches` |
| Power off on close | Checkbox | `--power-off-on-close` |

### Recording Section
| Control | Type | scrcpy flag |
|---|---|---|
| Record file | Text entry | `--record` |
| Record format | Dropdown (mp4, mkv, m4a, mka) | `--record-format` |

### Advanced Section
| Control | Type | scrcpy flag |
|---|---|---|
| Crop (W:H:X:Y) | Text entry | `--crop` |
| Verbosity | Dropdown (verbose, debug, info, warn, error) | `--verbosity` |
| Extra CLI args | Text entry (free-form) | appended raw |

### Process Control Section
| Control | Type | Purpose |
|---|---|---|
| **Launch** | Button | Start scrcpy subprocess |
| **Relaunch** | Button | Kill current + start new |
| **Close** | Button | Kill current subprocess |
| Relaunch on termination | Checkbox | Auto-restart if process exits |
| Status indicator | Label | Shows Running / Stopped / Restarting |

## Process Management

- `subprocess.Popen` to launch scrcpy with constructed argument list.
- A background thread polls `process.poll()` every 500 ms; when the process exits and "relaunch on termination" is checked, it re-launches automatically.
- Launch/Relaunch/Close update the status label.
- On app close (`WM_DELETE_WINDOW`), kill the scrcpy process if running.

## Config Persistence

- On startup: load `config.json` if it exists, populate GUI widgets.
- On Launch/Relaunch: save current widget values to `config.json`.
- Default values hardcoded for first run.

## Command Construction

Build a list from config values, skipping empty/default entries:
```python
cmd = ["scrcpy"]
if serial:  cmd += ["--serial", serial]
if window_title:  cmd += ["--window-title", window_title]
if max_size != "0":  cmd += ["--max-size", max_size]
# ... etc
for checkbox, flag in checkboxes:
    if checkbox.get():  cmd.append(flag)
if extra_args:  cmd += shlex.split(extra_args)
```

## Implementation Steps
1. Create `config.json` with defaults
2. Implement `scrcpy_relauncher.py`:
   - Config load/save
   - GUI construction with all sections
   - Command builder
   - Process management (launch/relaunch/close/auto-relaunch)
   - Status polling thread

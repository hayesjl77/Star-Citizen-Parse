# Star Citizen Parse

> **The only true transparent in-game overlay for Star Citizen combat events.**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-Overlay-41CD52?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)

SC Parse sits on top of your game as a sleek, transparent overlay — showing kills, deaths, vehicle destructions, quantum jumps, and session stats in real time. No alt-tabbing, no second monitor required.

---

## Features

- **True Transparent Overlay** — frameless, always-on-top, translucent window you can see through while playing
- **Auto-Detect** — finds your Star Citizen install and Game.log automatically (LIVE, PTU, EPTU)
- **Smart Event Parser** — structured regex parsing for combat, vehicles, jumps, disconnects, and more
- **PvP / PvE / NPC Detection** — distinguishes player kills from NPC kills with intelligent pattern matching
- **Live Session Stats** — kills, deaths, PvE count, and K/D ratio updated in real time
- **Color-Coded Feed** — red for PvP kills, green for PvE, orange for deaths, cyan for jumps, etc.
- **Drag & Resize** — move and resize the overlay window to fit your setup
- **Lock Mode** — lock position to prevent accidental moves during combat (`Ctrl+L`)
- **Click-Through Mode** — overlay passes mouse input to the game underneath (`Ctrl+P` / `Shift+F2`)
- **12 Keyboard Shortcuts** — quick-adjust opacity, font, toggle settings, clear feed — all without opening menus
- **Configurable Filters** — toggle which event types to show (kills, deaths, jumps, corpses, etc.)
- **Settings Dialog** — adjust opacity, font size, player name, and filters without editing files
- **Global Hotkey** — press `Shift+F1` to toggle the overlay on/off in-game
- **Config Persistence** — saves your settings (position, size, opacity, filters) to JSON
- **Cross-Platform** — works on Windows and Linux (including Wine/Proton SC installs)

## Screenshots

_Coming soon — overlay shown on top of Star Citizen in-game._

## Quick Start

### Requirements

- Python 3.10+
- Star Citizen installed (LIVE, PTU, or EPTU)

### Install

```bash
git clone https://github.com/hayesjl77/Star-Citizen-Parse.git
cd Star-Citizen-Parse
pip install -r requirements.txt
```

### Run

```bash
python main.py
```

The overlay will auto-detect your Game.log and start showing events. Right-click the overlay for options.

### CLI Options

```
python main.py                  # Auto-detect log, launch overlay
python main.py --log PATH       # Use a specific Game.log file
python main.py --player NAME    # Set your player name
python main.py --reset          # Reset config to defaults
```

## Architecture

```
Star-Citizen-Parse/
├── main.py              # Entry point with CLI
├── requirements.txt     # Dependencies
├── src/
│   ├── config.py        # Config dataclass + JSON persistence
│   ├── log_detector.py  # Auto-detect Game.log across drives
│   ├── event_parser.py  # Regex-based structured event parser
│   ├── log_monitor.py   # Qt-based file polling monitor
│   └── overlay.py       # Transparent overlay UI
└── main_old.py          # Original monolithic version (archived)
```

### Event Types

| Event             | Color      | Icon | Description                  |
| ----------------- | ---------- | ---- | ---------------------------- |
| PvP Kill          | 🔴 Red     | ⚔    | Player killed another player |
| PvE Kill          | 🟢 Green   | 🎯   | Player killed an NPC         |
| Death             | 🟠 Orange  | ☠    | You were killed              |
| Vehicle Destroyed | 🔴 Red     | 💥   | Ship/vehicle blown up        |
| Suicide           | 🟣 Magenta | 🔄   | Self-inflicted death         |
| Quantum Jump      | 🔵 Cyan    | 🚀   | Jump drive state change      |
| Corpse            | ⚫ Gray    | ⚰    | Body detected                |
| Disconnect        | 🔴 Red     | 📡   | Connection lost              |

## Settings

Right-click the overlay → **Settings** to configure:

- **Player Name** — your SC handle (for kill attribution)
- **Opacity** — overlay transparency (10–100%)
- **Font Size** — feed text size (9–24px)
- **Toggle Hotkey** — keybind to show/hide overlay
- **Event Filters** — choose which event types appear in the feed

Settings are saved to `sc_parse_config.json` automatically.

## Keyboard Shortcuts

All in-app shortcuts work without root access. Global hotkeys (Shift+F1/F2) require the `keyboard` module and root on Linux.

| Shortcut | Action |
|----------|--------|
| `Shift+F1` | Toggle overlay visibility (global) |
| `Shift+F2` | Toggle click-through mode (global) |
| `Ctrl+,` | Open settings dialog |
| `Ctrl+O` | Open log file |
| `Ctrl+L` | Lock/unlock overlay position |
| `Ctrl+P` | Toggle click-through mode |
| `Ctrl+K` | Clear feed |
| `Ctrl+R` | Reprocess log from beginning |
| `Ctrl+H` | Show keyboard shortcuts |
| `Ctrl+↑/↓` | Adjust opacity |
| `Ctrl+Shift+↑/↓` | Adjust font size |
| `Escape` | Minimize overlay |
| Right-click | Context menu |

### Click-Through Mode

Press `Ctrl+P` or `Shift+F2` to enable click-through — the overlay becomes transparent to mouse input so you can interact with the game underneath while still seeing the feed. Use `Shift+F2` (global hotkey) to toggle it back since in-app shortcuts won't fire in click-through mode.

### Lock Mode

Press `Ctrl+L` to lock the overlay position — prevents accidental drag/resize during combat.

## Why This Exists

Every other Star Citizen log parser is a desktop app or web dashboard — you have to alt-tab out of the game to check it. SC Parse is the **only true transparent overlay** that sits on top of the game while you play.

## Author

Built by [hayesjl77](https://github.com/hayesjl77) — part of the [SquigAI](https://squig-ai.com) project family.

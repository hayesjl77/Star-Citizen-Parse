#!/usr/bin/env python3
"""
Star Citizen Parse — Transparent In-Game Overlay
================================================
The only true transparent overlay for Star Citizen kill/death feed.
Runs on top of the game, auto-detects your log file, and shows
combat events in real time.

Usage:
    python main.py              # Normal launch (auto-detects log)
    python main.py --help       # Show help
    python main.py --log PATH   # Specify a Game.log path
    python main.py --reset      # Reset config to defaults

Author: github.com/hayesjl77
"""

import sys
import os
import argparse

# Ensure the project root is on the path so `src.*` imports work
# regardless of how the script is launched.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.overlay import main as overlay_main
from src.config import Config, CONFIG_FILE


def cli():
    parser = argparse.ArgumentParser(
        prog="sc-parse",
        description="Star Citizen Parse — Transparent overlay kill/death feed",
    )
    parser.add_argument(
        "--log", "-l",
        metavar="PATH",
        help="Path to a Star Citizen Game.log file",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset configuration to defaults",
    )
    parser.add_argument(
        "--player", "-p",
        metavar="NAME",
        help="Your Star Citizen player name / handle",
    )
    args = parser.parse_args()

    # Handle --reset
    if args.reset:
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            print("[SC Parse] Config reset to defaults.")
        else:
            print("[SC Parse] No config file to reset.")
        if not args.log:
            return

    # Apply CLI overrides to config before launching
    config = Config.load()
    changed = False

    if args.log:
        config.log_path = os.path.abspath(args.log)
        changed = True
    if args.player:
        config.player_name = args.player
        changed = True
    if changed:
        config.save()

    # Launch the overlay
    overlay_main()


if __name__ == "__main__":
    cli()

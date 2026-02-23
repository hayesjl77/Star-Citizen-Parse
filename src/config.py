"""
Configuration management for Star Citizen Parse.
Persists settings to JSON file alongside the executable.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sc_parse_config.json")

@dataclass
class OverlayConfig:
    """Overlay window configuration."""
    x: int = 20
    y: int = 20
    width: int = 420
    height: int = 600
    opacity: float = 0.85
    font_size: int = 13
    max_feed_items: int = 50
    compact_mode: bool = False

@dataclass
class Config:
    """Root application config."""
    # Log file
    log_path: Optional[str] = None
    auto_detect: bool = True

    # Player identity (for "you killed" / "killed you" detection)
    player_name: Optional[str] = None

    # Overlay
    overlay: OverlayConfig = field(default_factory=OverlayConfig)

    # Event filters (which event types to show)
    show_pvp_kills: bool = True
    show_pve_kills: bool = True
    show_deaths: bool = True
    show_vehicle_destroyed: bool = True
    show_jumps: bool = True
    show_corpses: bool = False
    show_disconnects: bool = True
    show_suicides: bool = True

    # Hotkey
    toggle_hotkey: str = "shift+f1"

    # Sound
    play_death_sound: bool = False

    @classmethod
    def load(cls) -> "Config":
        """Load config from disk, or return defaults."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                overlay_data = data.pop("overlay", {})
                overlay = OverlayConfig(**overlay_data)
                return cls(overlay=overlay, **data)
            except Exception as e:
                print(f"[Config] Failed to load config: {e}, using defaults")
        return cls()

    def save(self):
        """Persist config to disk."""
        try:
            data = asdict(self)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Config] Failed to save config: {e}")

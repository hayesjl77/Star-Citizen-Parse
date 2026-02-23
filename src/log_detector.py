"""
Auto-detect Star Citizen Game.log across all drives and common install paths.
Supports LIVE, PTU, EPTU environments.
"""

import os
import platform
import glob
from typing import List, Tuple, Optional


# Known SC relative paths under an install root
SC_SUBDIRS = [
    os.path.join("Roberts Space Industries", "StarCitizen", "LIVE"),
    os.path.join("Roberts Space Industries", "StarCitizen", "PTU"),
    os.path.join("Roberts Space Industries", "StarCitizen", "EPTU"),
    # Steam installs
    os.path.join("steamapps", "common", "Star Citizen", "LIVE"),
    os.path.join("steamapps", "common", "Star Citizen", "PTU"),
]

# Common base directories to check on each drive
COMMON_BASES = [
    "",          # Drive root
    "Games",
    "Program Files",
    "Program Files (x86)",
]

# Wine/Proton paths for Linux
LINUX_WINE_PATHS = [
    os.path.expanduser("~/.wine/drive_c"),
    os.path.expanduser("~/Games/star-citizen/drive_c"),
]


def get_drives() -> List[str]:
    """Get all mounted drive roots for the current OS."""
    system = platform.system()

    if system == "Windows":
        drives = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
        return drives

    elif system == "Linux":
        # Check /mnt, /media, /home, and Wine prefixes
        paths = ["/"]
        for mount_base in ["/mnt", "/media"]:
            if os.path.isdir(mount_base):
                for entry in os.listdir(mount_base):
                    full = os.path.join(mount_base, entry)
                    if os.path.isdir(full):
                        paths.append(full)
        # Add Wine/Proton paths
        paths.extend([p for p in LINUX_WINE_PATHS if os.path.isdir(p)])
        return paths

    elif system == "Darwin":
        paths = ["/"]
        volumes = "/Volumes"
        if os.path.isdir(volumes):
            for entry in os.listdir(volumes):
                paths.append(os.path.join(volumes, entry))
        return paths

    return ["/"]


def find_game_logs() -> List[Tuple[str, str, str]]:
    """
    Scan all drives for Star Citizen Game.log files.

    Returns list of (version_label, log_path, install_dir) tuples,
    sorted by modification time (newest first).
    """
    found = []
    seen_paths = set()

    drives = get_drives()

    for drive in drives:
        for base in COMMON_BASES:
            for subdir in SC_SUBDIRS:
                candidate = os.path.join(drive, base, subdir)
                log_file = os.path.join(candidate, "Game.log")

                if os.path.isfile(log_file) and log_file not in seen_paths:
                    seen_paths.add(log_file)
                    # Determine version label from path
                    version = "LIVE"
                    path_upper = candidate.upper()
                    if "EPTU" in path_upper:
                        version = "EPTU"
                    elif "PTU" in path_upper:
                        version = "PTU"

                    found.append((version, log_file, candidate))

    # Sort by file modification time, newest first
    found.sort(key=lambda x: os.path.getmtime(x[1]) if os.path.exists(x[1]) else 0, reverse=True)

    return found


def find_most_recent_log() -> Optional[str]:
    """Find the most recently modified Game.log. Returns path or None."""
    logs = find_game_logs()
    if logs:
        return logs[0][1]
    return None


def extract_player_name(log_path: str) -> Optional[str]:
    """
    Try to extract the player's handle from the log file.
    SC logs often contain the player's name in AccountLoginCharacterStatus or similar lines.
    """
    if not os.path.isfile(log_path):
        return None

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            # Only read first 5000 lines to find login info
            for i, line in enumerate(f):
                if i > 5000:
                    break
                # Pattern: <AccountLoginCharacterStatus> ... Character: PlayerName ...
                if "m_loginId=" in line and "m_characterName=" in line:
                    # Try to extract character name
                    import re
                    match = re.search(r'm_characterName=(\S+)', line)
                    if match:
                        return match.group(1)
                # Alternative: "Login - Character:" pattern
                if "SetNickname" in line:
                    import re
                    match = re.search(r'SetNickname\s+(\S+)', line)
                    if match:
                        return match.group(1)
    except Exception as e:
        print(f"[Detector] Error extracting player name: {e}")

    return None

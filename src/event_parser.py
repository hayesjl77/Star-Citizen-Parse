# Copyright (c) 2026 Squig-AI (squig-ai.com) — MIT License
# See LICENSE file for details.
"""
Star Citizen Game.log event parser.
Extracts structured combat events from raw log lines using regex patterns.
Inspired by StarLogs event_parser.py patterns, adapted for overlay use.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List


class EventType(Enum):
    PVP_KILL = "pvp_kill"          # You killed a player
    PVE_KILL = "pve_kill"          # You killed an NPC
    DEATH = "death"                # You died
    DEATH_OTHER = "death_other"    # Someone else died (spectating)
    VEHICLE_DESTROYED = "vehicle"  # Ship/vehicle destruction
    SUICIDE = "suicide"            # Self-kill
    CORPSE = "corpse"              # Corpse confirmation
    JUMP = "jump"                  # Quantum jump state
    DISCONNECT = "disconnect"      # Network disconnect
    ACTOR_STALL = "stall"          # Game freeze
    FPS_KILL = "fps_kill"          # On-foot kill
    FPS_DEATH = "fps_death"        # On-foot death
    UNKNOWN = "unknown"


@dataclass
class GameEvent:
    """A parsed game event."""
    event_type: EventType
    timestamp: str
    raw_line: str

    # Combat fields
    killer: Optional[str] = None
    victim: Optional[str] = None
    weapon: Optional[str] = None
    damage_type: Optional[str] = None
    ship: Optional[str] = None
    location: Optional[str] = None
    direction: Optional[str] = None

    # Vehicle fields
    vehicle_name: Optional[str] = None
    destruction_level: Optional[str] = None  # "soft" or "full"

    # Jump fields
    jump_state: Optional[str] = None

    # Context
    is_player_involved: bool = False  # True if the configured player is killer or victim


# Known NPC name patterns (NPCs contain these substrings)
NPC_PATTERNS = [
    "NPC_", "npc_", "PU_", "pu_", "Kopion", "Pirate", "Criminal", "Guard",
    "Security", "UEE_", "Vanduul", "XenoThreat", "Nine_Tails", "ninetails",
    "jpt_", "crim_", "hostage", "civilian", "pilot_", "_AI_", "outlaw",
    "bounty_", "mission_", "merc_", "Turret", "turret",
]

# Vehicle ID to friendly name lookup (common ships)
VEHICLE_NAMES = {
    "ORIG": "Origin", "ANVL": "Anvil", "AEGS": "Aegis", "DRAK": "Drake",
    "MISC": "MISC", "RSI": "RSI", "CNOU": "C.O.", "ARGO": "Argo",
    "BANU": "Banu", "XIAN": "Xi'an", "GAMA": "Gatac", "KRIG": "Kruger",
    "TMBL": "Tumbril", "VNCL": "Vanduul", "CRUS": "Crusader",
}

SHIP_LOOKUP = {
    "Gladius": "Gladius", "Arrow": "Arrow", "Hornet": "Hornet",
    "Sabre": "Sabre", "Vanguard": "Vanguard", "Eclipse": "Eclipse",
    "Retaliator": "Retaliator", "Hammerhead": "Hammerhead",
    "Carrack": "Carrack", "Cutlass": "Cutlass", "Freelancer": "Freelancer",
    "Caterpillar": "Caterpillar", "Herald": "Herald", "Buccaneer": "Buccaneer",
    "Constellation": "Constellation", "Valkyrie": "Valkyrie",
    "Reclaimer": "Reclaimer", "Starfarer": "Starfarer", "890": "890 Jump",
    "Avenger": "Avenger", "Titan": "Titan", "Stalker": "Stalker",
    "Warlock": "Warlock", "Mustang": "Mustang", "Aurora": "Aurora",
    "Pisces": "Pisces", "Mercury": "Mercury Star Runner",
    "Terrapin": "Terrapin", "Prospector": "Prospector", "Mole": "MOLE",
    "Vulture": "Vulture", "Spirit": "Spirit", "Scorpius": "Scorpius",
    "Redeemer": "Redeemer", "Paladin": "Paladin", "Zeus": "Zeus",
}


def is_npc(name: str) -> bool:
    """Check if a name looks like an NPC."""
    if not name:
        return False
    for pattern in NPC_PATTERNS:
        if pattern.lower() in name.lower():
            return True
    # Names with underscores and numbers are often NPCs
    if re.match(r'^[A-Za-z]+_[A-Za-z]+_\d+', name):
        return True
    return False


def extract_ship_name(zone_or_id: str) -> Optional[str]:
    """Extract a friendly ship name from a zone string or vehicle ID."""
    if not zone_or_id:
        return None
    for key, name in SHIP_LOOKUP.items():
        if key.lower() in zone_or_id.lower():
            return name
    # Try manufacturer prefix
    for prefix, mfr in VEHICLE_NAMES.items():
        if zone_or_id.startswith(prefix + "_"):
            remainder = zone_or_id.split("_")[1] if "_" in zone_or_id else ""
            return f"{mfr} {remainder}".strip()
    return None


def extract_timestamp(line: str) -> str:
    """Extract timestamp from log line, or return current time."""
    # SC log format: <2025-12-01T14:30:22.123Z> ...
    match = re.match(r'<(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
    if match:
        try:
            dt = datetime.fromisoformat(match.group(1))
            return dt.strftime("%H:%M:%S")
        except ValueError:
            pass
    return datetime.now().strftime("%H:%M:%S")


# ─── Regex patterns for Star Citizen Game.log ──────────────────────────────

# Actor Death: the main kill/death event
# Format: <Actor Death> CActor::Kill: 'VictimName' [vehicleID] in zone 'ZoneName' killed by 'KillerName' [vehicleID] with damage type 'DamageType' ...
RE_ACTOR_DEATH = re.compile(
    r"<Actor Death>.*?CActor::Kill:\s*'([^']+)'.*?killed by\s*'([^']+)'"
    r"(?:.*?with\s+damage\s+type\s*'([^']*)')?"
    r"(?:.*?in\s+zone\s*'([^']*)')?"
    , re.IGNORECASE
)

# Alternative actor death format
RE_ACTOR_DEATH_ALT = re.compile(
    r"<Actor Death>.*?'([^']+)'\s+killed\s+by\s+'([^']+)'"
    r"(?:.*?damage[_ ]type[=:]\s*'?([^'\s,]+))?"
    , re.IGNORECASE
)

# Corpse events
RE_CORPSE = re.compile(
    r"<Corpse>.*?'([^']+)'"
    , re.IGNORECASE
)

# Jump Drive state changes
RE_JUMP = re.compile(
    r"<Jump Drive Changing State>.*?from\s+(\w+)\s+to\s+(\w+)"
    , re.IGNORECASE
)

# Vehicle destruction (soft death = disabled, full = exploded)
RE_VEHICLE_DESTROY = re.compile(
    r"<Vehicle Destruction>.*?'([^']+)'.*?level\s*(\d+)\s*(?:to|->)\s*(\d+)"
    , re.IGNORECASE
)

# Alternative vehicle pattern
RE_VEHICLE_DESTROY_ALT = re.compile(
    r"<Vehicle Destruction>.*?'([^']+)'"
    , re.IGNORECASE
)

# Disconnect
RE_DISCONNECT = re.compile(
    r"<Disconnect>|disconnect|CNetworkError|Server\s+disconnect"
    , re.IGNORECASE
)

# Actor stall (freeze)
RE_STALL = re.compile(
    r"<Actor Stall>|ActorStall"
    , re.IGNORECASE
)

# Weapon extraction from combat lines
RE_WEAPON = re.compile(
    r"weapon[=:]\s*'?([^'\s,;]+)"
    , re.IGNORECASE
)

# Direction extraction
RE_DIRECTION = re.compile(
    r"direction[=:]\s*\(?([^)]+)\)?"
    , re.IGNORECASE
)


def parse_line(line: str, player_name: Optional[str] = None) -> Optional[GameEvent]:
    """
    Parse a single log line and return a GameEvent if it matches a known pattern.
    Returns None for unrecognized lines.
    """
    if not line or len(line) < 10:
        return None

    timestamp = extract_timestamp(line)

    # ─── Actor Death ───
    match = RE_ACTOR_DEATH.search(line)
    if not match:
        match = RE_ACTOR_DEATH_ALT.search(line)

    if match:
        victim = match.group(1).strip()
        killer = match.group(2).strip()
        damage_type = match.group(3).strip() if match.lastindex >= 3 and match.group(3) else None
        zone = match.group(4).strip() if match.lastindex >= 4 and match.group(4) else None

        # Extract weapon if present
        weapon = None
        weapon_match = RE_WEAPON.search(line)
        if weapon_match:
            weapon = weapon_match.group(1)

        # Extract ship from zone
        ship = extract_ship_name(zone) if zone else None

        # Extract direction
        direction = None
        dir_match = RE_DIRECTION.search(line)
        if dir_match:
            direction = dir_match.group(1)

        # Determine event type
        player_lower = player_name.lower() if player_name else None

        # Suicide check
        if killer.lower() == victim.lower():
            return GameEvent(
                event_type=EventType.SUICIDE,
                timestamp=timestamp,
                raw_line=line,
                killer=killer,
                victim=victim,
                damage_type=damage_type,
                ship=ship,
                is_player_involved=(player_lower is not None and player_lower == killer.lower()),
            )

        # Determine kill type based on player involvement + NPC status
        is_killer_player_char = player_lower and killer.lower() == player_lower
        is_victim_player_char = player_lower and victim.lower() == player_lower

        if is_victim_player_char:
            # Player died
            event_type = EventType.DEATH
        elif is_killer_player_char:
            # Player got a kill
            event_type = EventType.PVE_KILL if is_npc(victim) else EventType.PVP_KILL
        else:
            # Someone else died — still show it
            if is_npc(victim):
                event_type = EventType.PVE_KILL
            elif is_npc(killer) and is_npc(victim):
                return None  # NPC vs NPC, skip
            else:
                event_type = EventType.DEATH_OTHER

        return GameEvent(
            event_type=event_type,
            timestamp=timestamp,
            raw_line=line,
            killer=killer,
            victim=victim,
            weapon=weapon,
            damage_type=damage_type,
            ship=ship,
            location=zone,
            direction=direction,
            is_player_involved=(is_killer_player_char or is_victim_player_char),
        )

    # ─── Vehicle Destruction ───
    match = RE_VEHICLE_DESTROY.search(line)
    if match:
        vehicle_id = match.group(1)
        level_from = match.group(2)
        level_to = match.group(3)

        vehicle_name = extract_ship_name(vehicle_id) or vehicle_id
        destruction = "full" if level_to == "2" else "soft"

        return GameEvent(
            event_type=EventType.VEHICLE_DESTROYED,
            timestamp=timestamp,
            raw_line=line,
            vehicle_name=vehicle_name,
            destruction_level=destruction,
        )

    match = RE_VEHICLE_DESTROY_ALT.search(line)
    if match and "<Vehicle Destruction>" in line:
        vehicle_id = match.group(1)
        vehicle_name = extract_ship_name(vehicle_id) or vehicle_id
        return GameEvent(
            event_type=EventType.VEHICLE_DESTROYED,
            timestamp=timestamp,
            raw_line=line,
            vehicle_name=vehicle_name,
            destruction_level="unknown",
        )

    # ─── Corpse ───
    match = RE_CORPSE.search(line)
    if match:
        name = match.group(1)
        return GameEvent(
            event_type=EventType.CORPSE,
            timestamp=timestamp,
            raw_line=line,
            victim=name,
            is_player_involved=(player_name and name.lower() == player_name.lower()),
        )

    # ─── Jump Drive ───
    match = RE_JUMP.search(line)
    if match:
        from_state = match.group(1)
        to_state = match.group(2)
        return GameEvent(
            event_type=EventType.JUMP,
            timestamp=timestamp,
            raw_line=line,
            jump_state=f"{from_state} → {to_state}",
        )

    # ─── Disconnect ───
    if RE_DISCONNECT.search(line):
        return GameEvent(
            event_type=EventType.DISCONNECT,
            timestamp=timestamp,
            raw_line=line,
        )

    # ─── Actor Stall ───
    if RE_STALL.search(line):
        return GameEvent(
            event_type=EventType.ACTOR_STALL,
            timestamp=timestamp,
            raw_line=line,
        )

    return None


def parse_lines(lines: List[str], player_name: Optional[str] = None) -> List[GameEvent]:
    """Parse multiple log lines. Returns list of events (no Nones)."""
    events = []
    for line in lines:
        event = parse_line(line.strip(), player_name)
        if event:
            events.append(event)
    return events

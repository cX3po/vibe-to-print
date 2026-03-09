"""
printer_profiles.py
-------------------
Backend logic for printer preset management.

- BUILTIN_PRESETS   : read-only factory defaults (never written to disk)
- printer_profiles.json : user-saved profiles that persist across sessions
  (stored next to this file; user profiles override built-ins with same name)

Key helpers
-----------
load_all_profiles()       -> dict[name, profile]
save_user_profile(...)    -> None
delete_user_profile(...)  -> bool
bed_center(profile)       -> (cx, cy)
gcode_start_snippet(...)  -> str   (homing + heat-up sequence, centred on bed)
"""

import json
from pathlib import Path

# ── File that persists user-added / edited profiles ──────────────────────────
_PROFILES_PATH = Path(__file__).parent / "printer_profiles.json"

# ── Factory presets ───────────────────────────────────────────────────────────
# Each entry: bed_x / bed_y / bed_z in mm, optional notes.
# Material temps live in MATERIAL_TEMPS (app.py) — printers share the same
# filament standards.  Override keys (hotend_override, bed_override) are
# supported for boutique printers with unusual requirements.
BUILTIN_PRESETS: dict[str, dict] = {
    # ── Creality ────────────────────────────────────────────────────────────
    "Ender 3": {
        "bed_x": 220, "bed_y": 220, "bed_z": 250,
        "notes": "Cartesian bed-slinger, 8-bit board",
    },
    "Ender 3 V2": {
        "bed_x": 235, "bed_y": 235, "bed_z": 250,
        "notes": "Cartesian bed-slinger, 32-bit silent board",
    },
    "Ender 3 S1": {
        "bed_x": 235, "bed_y": 235, "bed_z": 270,
        "notes": "Direct drive, CR Touch auto-levelling",
    },
    "Ender 3 S1 Pro": {
        "bed_x": 235, "bed_y": 235, "bed_z": 270,
        "notes": "Sprite extruder, 300 °C hotend, PEI sheet",
        "hotend_override": {"PLA": 210, "PETG": 235, "ABS": 250},
    },
    "Creality K1": {
        "bed_x": 220, "bed_y": 220, "bed_z": 250,
        "notes": "CoreXY, enclosed, 600 mm/s capable",
    },
    "Creality K1 Max": {
        "bed_x": 300, "bed_y": 300, "bed_z": 300,
        "notes": "CoreXY, enclosed, large format",
    },
    # ── Bambu Lab ───────────────────────────────────────────────────────────
    "Bambu Lab A1 Mini": {
        "bed_x": 180, "bed_y": 180, "bed_z": 180,
        "notes": "Cartesian, AMS Lite compatible",
    },
    "Bambu Lab P1P": {
        "bed_x": 256, "bed_y": 256, "bed_z": 256,
        "notes": "CoreXY, open frame",
    },
    "Bambu Lab P1S": {
        "bed_x": 256, "bed_y": 256, "bed_z": 256,
        "notes": "CoreXY, fully enclosed, AMS ready",
    },
    "Bambu Lab X1C": {
        "bed_x": 256, "bed_y": 256, "bed_z": 256,
        "notes": "CoreXY, enclosed, multi-material, LiDAR",
    },
    # ── Prusa ───────────────────────────────────────────────────────────────
    "Prusa Mini+": {
        "bed_x": 180, "bed_y": 180, "bed_z": 180,
        "notes": "MINI form factor, bowden drive",
    },
    "Prusa MK3S+": {
        "bed_x": 250, "bed_y": 210, "bed_z": 210,
        "notes": "Cartesian, direct drive, MMU3 compatible",
    },
    "Prusa MK4": {
        "bed_x": 250, "bed_y": 210, "bed_z": 220,
        "notes": "Input shaping, nextruder, load-cell levelling",
    },
    # ── Voron ───────────────────────────────────────────────────────────────
    "Voron Trident": {
        "bed_x": 250, "bed_y": 250, "bed_z": 250,
        "notes": "CoreXY, triple-Z levelling, enclosed",
        "hotend_override": {"PLA": 215, "PETG": 240, "ABS": 250},
        "bed_override":    {"PLA": 65,  "PETG": 90,  "ABS": 110},
    },
    "Voron 2.4": {
        "bed_x": 350, "bed_y": 350, "bed_z": 350,
        "notes": "CoreXY, flying gantry, enclosed, large format",
        "hotend_override": {"PLA": 215, "PETG": 240, "ABS": 250},
        "bed_override":    {"PLA": 65,  "PETG": 90,  "ABS": 110},
    },
    # ── Anycubic / Artillery ─────────────────────────────────────────────────
    "Anycubic Kobra 2": {
        "bed_x": 220, "bed_y": 220, "bed_z": 250,
        "notes": "Cartesian, LeviQ 2.0 auto-levelling",
    },
    "Artillery Sidewinder X2": {
        "bed_x": 300, "bed_y": 300, "bed_z": 400,
        "notes": "Cartesian, direct drive, large format",
    },
}


# ── Persistence helpers ───────────────────────────────────────────────────────

def _load_user_profiles() -> dict[str, dict]:
    """Return user profiles from disk; empty dict if file missing or corrupt."""
    if not _PROFILES_PATH.exists():
        return {}
    try:
        with _PROFILES_PATH.open() as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_user_profiles(user: dict[str, dict]) -> None:
    with _PROFILES_PATH.open("w") as fh:
        json.dump(user, fh, indent=2)


def load_all_profiles() -> dict[str, dict]:
    """
    Merge built-in presets with user-saved ones.
    User profiles take precedence (allow overriding a built-in).
    Each returned profile has a 'name' key injected for convenience.
    """
    merged = {}
    for name, data in {**BUILTIN_PRESETS, **_load_user_profiles()}.items():
        merged[name] = {"name": name, **data}
    return merged


def save_user_profile(name: str, bed_x: int, bed_y: int, bed_z: int,
                       notes: str = "",
                       hotend_override: dict | None = None,
                       bed_override: dict | None = None) -> None:
    """Persist a printer profile.  Overwrites if name already exists."""
    user = _load_user_profiles()
    entry: dict = {"bed_x": bed_x, "bed_y": bed_y, "bed_z": bed_z, "notes": notes}
    if hotend_override:
        entry["hotend_override"] = hotend_override
    if bed_override:
        entry["bed_override"] = bed_override
    user[name] = entry
    _write_user_profiles(user)


def delete_user_profile(name: str) -> bool:
    """Remove a user-saved profile.  Returns True if deleted, False if not found."""
    user = _load_user_profiles()
    if name not in user:
        return False
    del user[name]
    _write_user_profiles(user)
    return True


def is_user_profile(name: str) -> bool:
    """True if this profile was saved by the user (not a built-in)."""
    return name in _load_user_profiles()


# ── Geometry helpers ──────────────────────────────────────────────────────────

def bed_center(profile: dict) -> tuple[float, float]:
    """Return (center_x, center_y) of the build plate in mm."""
    return profile["bed_x"] / 2.0, profile["bed_y"] / 2.0


def resolve_temps(profile: dict, material: str,
                   material_temps: dict) -> dict[str, int]:
    """
    Return effective {hotend, bed} temps for this printer+material combo.
    Printer-specific overrides beat the global material_temps table.
    """
    base = material_temps.get(material, {"hotend": 210, "bed": 60})
    hotend = profile.get("hotend_override", {}).get(material, base["hotend"])
    bed    = profile.get("bed_override",    {}).get(material, base["bed"])
    return {"hotend": hotend, "bed": bed}


# ── G-code helpers ────────────────────────────────────────────────────────────

def gcode_start_snippet(profile: dict, material: str,
                          material_temps: dict) -> str:
    """
    Return a ready-to-paste G-code start sequence that:
      • homes all axes
      • heats hotend & bed to the correct temps for this printer + material
      • moves the nozzle to the geometric centre of the build plate
    """
    cx, cy = bed_center(profile)
    temps  = resolve_temps(profile, material, material_temps)
    name   = profile.get("name", "Unknown Printer")

    return (
        f"; =========================================================\n"
        f"; Printer      : {name}\n"
        f"; Build volume : {profile['bed_x']} x {profile['bed_y']} x {profile['bed_z']} mm\n"
        f"; Bed centre   : X={cx:.1f}  Y={cy:.1f}\n"
        f"; Material     : {material}\n"
        f"; Hotend       : {temps['hotend']} °C\n"
        f"; Bed          : {temps['bed']} °C\n"
        f"; Notes        : {profile.get('notes', '')}\n"
        f"; =========================================================\n"
        f"G28                          ; Home all axes\n"
        f"G1 Z5 F5000                  ; Lift nozzle\n"
        f"M104 S{temps['hotend']}      ; Set hotend temp (no wait)\n"
        f"M140 S{temps['bed']}         ; Set bed temp   (no wait)\n"
        f"M109 S{temps['hotend']}      ; Wait for hotend\n"
        f"M190 S{temps['bed']}         ; Wait for bed\n"
        f"G1 X{cx:.1f} Y{cy:.1f} Z0.3 F3000  ; Move to bed centre\n"
        f"G92 E0                       ; Reset extruder\n"
        f"; =========================================================\n"
    )


def centering_instruction(profile: dict) -> str:
    """
    Returns a plain-English centering constraint to inject into the
    Claude prompt, so the OpenSCAD model is translated to sit over
    the centre of this printer's bed.
    """
    cx, cy = bed_center(profile)
    return (
        f"The model MUST be centered at X={cx:.1f} mm, Y={cy:.1f} mm "
        f"(the geometric centre of the {profile['bed_x']} × {profile['bed_y']} mm build plate). "
        f"In OpenSCAD, use `translate([{cx:.1f}, {cy:.1f}, 0])` around the outermost module call, "
        f"or set `bed_center_x = {cx:.1f};` and `bed_center_y = {cy:.1f};` as top-level variables "
        f"and reference them in the translate."
    )

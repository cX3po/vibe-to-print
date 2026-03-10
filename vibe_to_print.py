"""
vibe_to_print.py
================
Single-file, zero-dependency Vibe-to-Print application.
Run with:  streamlit run vibe_to_print.py

All templates, AI logic, 3D viewer HTML, and slicer are embedded
directly — no external module imports required beyond the pip packages
listed in requirements.txt.
"""

from __future__ import annotations

import base64
import hashlib
import math
import re
import json
import shutil
import subprocess
import time
import tempfile
import urllib.parse
from pathlib import Path

import requests
import streamlit as st

# ══════════════════════════════════════════════════════════════════════════════
# INTERNAL TEMPLATES  (all 12 parametric OpenSCAD designs, embedded)
# ══════════════════════════════════════════════════════════════════════════════

INTERNAL_TEMPLATES: list[dict] = [

    # ── 1. Round Knob — D-Shaft ───────────────────────────────────────────────
    {
        "id":          "knob_d_shaft",
        "name":        "Round Knob (D-Shaft)",
        "category":    "Knobs & Controls",
        "tags":        ["knob", "dial", "control", "pot", "potentiometer",
                        "radio", "audio", "stove", "d-shaft", "replacement"],
        "description": "Classic cylindrical knob for a D-shaft pot or switch.",
        "dims": [
            {"id": "shaft_d",     "question": "Shaft outer diameter (mm)",           "default": 6.35, "unit": "mm"},
            {"id": "flat_cut",    "question": "D-flat depth — cut from centre (mm)", "default": 0.7,  "unit": "mm"},
            {"id": "shaft_depth", "question": "Depth of the shaft hole (mm)",        "default": 15,   "unit": "mm"},
            {"id": "knob_d",      "question": "Knob outer diameter (mm)",            "default": 30,   "unit": "mm"},
            {"id": "knob_h",      "question": "Knob total height (mm)",              "default": 22,   "unit": "mm"},
            {"id": "grip_ridges", "question": "Number of grip ridges (0 = smooth)",  "default": 12,   "unit": ""},
        ],
        "scad_modules": """\
module d_hole() {
    union() {
        cylinder(h = shaft_depth + 1, d = shaft_d, $fn = 64);
        translate([shaft_d/2 - flat_cut, -(shaft_d + 2)/2, -0.5])
            cube([flat_cut + 1.5, shaft_d + 2, shaft_depth + 2]);
    }
}
module knob_body() {
    union() {
        cylinder(h = knob_h, d = knob_d, $fn = 64);
        if (grip_ridges > 0) {
            for (i = [0 : grip_ridges - 1]) {
                rotate([0, 0, i * 360 / grip_ridges])
                    translate([knob_d/2, 0, knob_h * 0.15])
                        cylinder(h = knob_h * 0.7, d = 2.8, $fn = 16);
            }
        }
    }
}
module knob() {
    difference() {
        knob_body();
        translate([0, 0, -0.5]) d_hole();
        translate([0, 0, knob_h - 1.5])
            cylinder(h = 3, d1 = knob_d - 0.01, d2 = knob_d + 5, $fn = 64);
    }
}""",
        "scad_call": "knob()",
    },

    # ── 2. Round Knob — Round Shaft + Set-Screw ───────────────────────────────
    {
        "id":          "knob_round_shaft",
        "name":        "Round Knob (Round Shaft + Set-Screw)",
        "category":    "Knobs & Controls",
        "tags":        ["knob", "round shaft", "set screw", "dial", "control",
                        "replacement", "audio"],
        "description": "Knob with a round bore and a side set-screw hole for locking.",
        "dims": [
            {"id": "shaft_d",     "question": "Shaft outer diameter (mm)",          "default": 6.0,  "unit": "mm"},
            {"id": "shaft_depth", "question": "Depth of the shaft hole (mm)",       "default": 15,   "unit": "mm"},
            {"id": "set_screw_d", "question": "Set-screw hole diameter (M3 = 2.5)", "default": 2.5,  "unit": "mm"},
            {"id": "knob_d",      "question": "Knob outer diameter (mm)",           "default": 30,   "unit": "mm"},
            {"id": "knob_h",      "question": "Knob total height (mm)",             "default": 22,   "unit": "mm"},
            {"id": "grip_ridges", "question": "Number of grip ridges (0 = smooth)", "default": 12,   "unit": ""},
        ],
        "scad_modules": """\
module round_shaft_hole() {
    cylinder(h = shaft_depth + 1, d = shaft_d, $fn = 64);
}
module set_screw_channel() {
    translate([0, 0, 8])
        rotate([90, 0, 0])
            cylinder(h = knob_d, d = set_screw_d, center = true, $fn = 32);
}
module knob_body() {
    union() {
        cylinder(h = knob_h, d = knob_d, $fn = 64);
        if (grip_ridges > 0) {
            for (i = [0 : grip_ridges - 1]) {
                rotate([0, 0, i * 360 / grip_ridges])
                    translate([knob_d/2, 0, knob_h * 0.15])
                        cylinder(h = knob_h * 0.7, d = 2.8, $fn = 16);
            }
        }
    }
}
module knob() {
    difference() {
        knob_body();
        translate([0, 0, -0.5]) round_shaft_hole();
        set_screw_channel();
        translate([0, 0, knob_h - 1.5])
            cylinder(h = 3, d1 = knob_d - 0.01, d2 = knob_d + 5, $fn = 64);
    }
}""",
        "scad_call": "knob()",
    },

    # ── 3. Pointer Knob ───────────────────────────────────────────────────────
    {
        "id":          "knob_pointer",
        "name":        "Pointer Knob (D-Shaft, Indicator Line)",
        "category":    "Knobs & Controls",
        "tags":        ["knob", "pointer", "indicator", "dial", "audio",
                        "vintage", "radio", "d-shaft"],
        "description": "Flat-top knob with a raised pointer line and D-shaft bore.",
        "dims": [
            {"id": "shaft_d",     "question": "Shaft outer diameter (mm)",      "default": 6.35, "unit": "mm"},
            {"id": "flat_cut",    "question": "D-flat depth from centre (mm)",   "default": 0.7,  "unit": "mm"},
            {"id": "shaft_depth", "question": "Depth of the shaft hole (mm)",    "default": 15,   "unit": "mm"},
            {"id": "knob_d",      "question": "Knob outer diameter (mm)",        "default": 35,   "unit": "mm"},
            {"id": "knob_h",      "question": "Knob height (mm)",                "default": 18,   "unit": "mm"},
            {"id": "pointer_w",   "question": "Pointer line width (mm)",         "default": 3,    "unit": "mm"},
        ],
        "scad_modules": """\
module d_hole() {
    union() {
        cylinder(h = shaft_depth + 1, d = shaft_d, $fn = 64);
        translate([shaft_d/2 - flat_cut, -(shaft_d + 2)/2, -0.5])
            cube([flat_cut + 1.5, shaft_d + 2, shaft_depth + 2]);
    }
}
module pointer_line() {
    translate([-pointer_w/2, 0, knob_h - 1])
        cube([pointer_w, knob_d/2 - 1, 2]);
}
module knob() {
    difference() {
        union() {
            cylinder(h = knob_h, d = knob_d, $fn = 64);
            pointer_line();
        }
        translate([0, 0, -0.5]) d_hole();
    }
}""",
        "scad_call": "knob()",
    },

    # ── 4. Simple Box (Open Top) ──────────────────────────────────────────────
    {
        "id":          "box_open",
        "name":        "Simple Box (Open Top)",
        "category":    "Enclosures & Boxes",
        "tags":        ["box", "tray", "container", "organiser", "storage",
                        "open", "shelf"],
        "description": "Hollow rectangular box with no lid — useful as a tray or drawer organiser.",
        "dims": [
            {"id": "inner_w",  "question": "Inner width (mm)",      "default": 80,  "unit": "mm"},
            {"id": "inner_d",  "question": "Inner depth (mm)",       "default": 60,  "unit": "mm"},
            {"id": "inner_h",  "question": "Inner height (mm)",      "default": 40,  "unit": "mm"},
            {"id": "wall",     "question": "Wall thickness (mm)",    "default": 2.5, "unit": "mm"},
            {"id": "corner_r", "question": "Corner radius (mm)",     "default": 3,   "unit": "mm"},
        ],
        "scad_modules": """\
module rounded_box(w, d, h, r) {
    hull() {
        for (x = [r, w - r]) for (y = [r, d - r])
            translate([x, y, 0]) cylinder(h = h, r = r, $fn = 32);
    }
}
module box() {
    outer_w = inner_w + 2 * wall;
    outer_d = inner_d + 2 * wall;
    outer_h = inner_h + wall;
    difference() {
        rounded_box(outer_w, outer_d, outer_h, corner_r);
        translate([wall, wall, wall])
            rounded_box(inner_w, inner_d, outer_h, max(corner_r - wall, 0.5));
    }
}""",
        "scad_call": "box()",
    },

    # ── 5. Box with Press-Fit Lid ─────────────────────────────────────────────
    {
        "id":          "box_with_lid",
        "name":        "Box with Press-Fit Lid",
        "category":    "Enclosures & Boxes",
        "tags":        ["box", "lid", "enclosure", "case", "container",
                        "electronics", "project box"],
        "description": "Rectangular box with a matching press-fit lid. Prints as two parts.",
        "dims": [
            {"id": "inner_w",  "question": "Inner width (mm)",        "default": 80,  "unit": "mm"},
            {"id": "inner_d",  "question": "Inner depth (mm)",         "default": 60,  "unit": "mm"},
            {"id": "inner_h",  "question": "Box inner height (mm)",   "default": 30,  "unit": "mm"},
            {"id": "lid_h",    "question": "Lid height (mm)",          "default": 8,   "unit": "mm"},
            {"id": "wall",     "question": "Wall thickness (mm)",      "default": 2.5, "unit": "mm"},
            {"id": "fit_gap",  "question": "Lid press-fit gap (mm)",   "default": 0.3, "unit": "mm"},
        ],
        "scad_modules": """\
module box_body() {
    outer_w = inner_w + 2 * wall;
    outer_d = inner_d + 2 * wall;
    outer_h = inner_h + wall;
    difference() {
        cube([outer_w, outer_d, outer_h]);
        translate([wall, wall, wall]) cube([inner_w, inner_d, outer_h]);
    }
}
module lid() {
    outer_w = inner_w + 2 * wall;
    outer_d = inner_d + 2 * wall;
    rim_w   = inner_w - 2 * fit_gap;
    rim_d   = inner_d - 2 * fit_gap;
    union() {
        cube([outer_w, outer_d, wall]);
        translate([wall + fit_gap, wall + fit_gap, wall])
            cube([rim_w, rim_d, lid_h - wall]);
    }
}
module both_parts() {
    box_body();
    translate([inner_w + 2 * wall + 10, 0, 0]) lid();
}""",
        "scad_call": "both_parts()",
    },

    # ── 6. End Cap / Tube Plug ────────────────────────────────────────────────
    {
        "id":          "end_cap",
        "name":        "End Cap / Tube Plug",
        "category":    "Caps & Plugs",
        "tags":        ["cap", "plug", "end cap", "tube", "pipe", "cover",
                        "stopper", "fitting"],
        "description": "Cylindrical plug that inserts into a tube end, with a retention flange.",
        "dims": [
            {"id": "plug_d",   "question": "Plug diameter — fits INSIDE tube (mm)",    "default": 24.0, "unit": "mm"},
            {"id": "plug_h",   "question": "Plug insertion depth (mm)",                "default": 15,   "unit": "mm"},
            {"id": "flange_d", "question": "Flange diameter — sits outside tube (mm)", "default": 29,   "unit": "mm"},
            {"id": "flange_h", "question": "Flange thickness (mm)",                    "default": 3,    "unit": "mm"},
            {"id": "bore_d",   "question": "Centre bore diameter (0 = solid) (mm)",    "default": 0,    "unit": "mm"},
        ],
        "scad_modules": """\
module end_cap() {
    difference() {
        union() {
            cylinder(h = plug_h, d = plug_d, $fn = 64);
            cylinder(h = flange_h, d = flange_d, $fn = 64);
        }
        if (bore_d > 0) {
            translate([0, 0, -0.5])
                cylinder(h = plug_h + flange_h + 1, d = bore_d, $fn = 64);
        }
    }
}""",
        "scad_call": "end_cap()",
    },

    # ── 7. L-Bracket ─────────────────────────────────────────────────────────
    {
        "id":          "l_bracket",
        "name":        "L-Bracket (Right-Angle Mount)",
        "category":    "Brackets & Mounts",
        "tags":        ["bracket", "l bracket", "mount", "angle", "shelf",
                        "support", "right angle", "hardware"],
        "description": "Right-angle mounting bracket with a configurable hole pattern.",
        "dims": [
            {"id": "width",        "question": "Bracket width (into page) (mm)", "default": 30,  "unit": "mm"},
            {"id": "arm1_len",     "question": "Vertical arm length (mm)",        "default": 50,  "unit": "mm"},
            {"id": "arm2_len",     "question": "Horizontal arm length (mm)",      "default": 50,  "unit": "mm"},
            {"id": "thickness",    "question": "Material thickness (mm)",         "default": 4.5, "unit": "mm"},
            {"id": "hole_d",       "question": "Mounting hole diameter (mm)",     "default": 4.5, "unit": "mm"},
            {"id": "holes_per_arm","question": "Holes per arm (1 or 2)",          "default": 2,   "unit": ""},
        ],
        "scad_modules": """\
module arm(length) {
    cube([thickness, width, length]);
}
module hole_pattern(arm_length) {
    spacing = arm_length / (holes_per_arm + 1);
    for (i = [1 : holes_per_arm])
        translate([thickness/2, width/2, i * spacing])
            rotate([0, 90, 0])
                cylinder(h = thickness + 1, d = hole_d, center = true, $fn = 32);
}
module l_bracket() {
    difference() {
        union() {
            arm(arm1_len);
            rotate([0, -90, 0]) translate([-arm2_len, 0, 0]) arm(arm2_len);
        }
        hole_pattern(arm1_len);
        rotate([0, -90, 0]) translate([-arm2_len, 0, 0]) hole_pattern(arm2_len);
    }
}""",
        "scad_call": "l_bracket()",
    },

    # ── 8. Cable Clip ─────────────────────────────────────────────────────────
    {
        "id":          "cable_clip",
        "name":        "Snap-On Cable Clip",
        "category":    "Cable Management",
        "tags":        ["cable", "clip", "wire", "organiser", "holder",
                        "snap", "mount", "desk"],
        "description": "Snap-on clip to route cables along walls or desks.",
        "dims": [
            {"id": "cable_d", "question": "Cable outer diameter (mm)",                "default": 6,   "unit": "mm"},
            {"id": "clip_w",  "question": "Clip width (mm)",                          "default": 18,  "unit": "mm"},
            {"id": "wall_t",  "question": "Clip wall thickness (mm)",                 "default": 2.5, "unit": "mm"},
            {"id": "base_h",  "question": "Mounting base height (mm)",                "default": 8,   "unit": "mm"},
            {"id": "screw_d", "question": "Mounting screw hole diameter (mm)",        "default": 3.5, "unit": "mm"},
            {"id": "gap",     "question": "Snap-in gap opening (% of cable_d, 60–80)","default": 70,  "unit": "%"},
        ],
        "scad_modules": """\
module cable_clip() {
    r      = cable_d / 2 + wall_t;
    gap_mm = cable_d * gap / 100;
    difference() {
        union() {
            translate([-r, -r, 0]) cube([r * 2, r + wall_t, base_h]);
            translate([0, 0, base_h])
                difference() {
                    cylinder(h = clip_w, r = r, $fn = 64);
                    translate([0, 0, -0.5]) cylinder(h = clip_w + 1, r = cable_d / 2, $fn = 64);
                    translate([-gap_mm/2, -(r + 1), -0.5]) cube([gap_mm, r + 2, clip_w + 1]);
                }
        }
        translate([0, -r/2, -0.5]) cylinder(h = base_h + 1, d = screw_d, $fn = 32);
    }
}""",
        "scad_call": "cable_clip()",
    },

    # ── 9. Wall Hook ──────────────────────────────────────────────────────────
    {
        "id":          "wall_hook",
        "name":        "Wall Hook",
        "category":    "Hooks & Hangers",
        "tags":        ["hook", "wall", "hanger", "coat", "key", "mount",
                        "screw", "organiser"],
        "description": "Simple wall-mounted hook with screw holes in the backplate.",
        "dims": [
            {"id": "plate_w",    "question": "Backplate width (mm)",       "default": 40,  "unit": "mm"},
            {"id": "plate_h",    "question": "Backplate height (mm)",      "default": 60,  "unit": "mm"},
            {"id": "plate_t",    "question": "Backplate thickness (mm)",   "default": 5,   "unit": "mm"},
            {"id": "hook_reach", "question": "Hook reach from wall (mm)",  "default": 40,  "unit": "mm"},
            {"id": "hook_t",     "question": "Hook arm thickness (mm)",    "default": 6,   "unit": "mm"},
            {"id": "tip_h",      "question": "Hook tip height (mm)",       "default": 20,  "unit": "mm"},
            {"id": "screw_d",    "question": "Screw hole diameter (mm)",   "default": 4.5, "unit": "mm"},
        ],
        "scad_modules": """\
module backplate() { cube([plate_w, plate_t, plate_h]); }
module hook_arm() {
    translate([plate_w/2 - hook_t/2, 0, plate_h * 0.4])
        cube([hook_t, hook_reach, hook_t]);
    translate([plate_w/2 - hook_t/2, hook_reach - hook_t, plate_h * 0.4])
        cube([hook_t, hook_t, tip_h]);
}
module screw_holes() {
    for (z_off = [plate_h * 0.2, plate_h * 0.75])
        translate([plate_w/2, plate_t/2, z_off])
            rotate([90, 0, 0])
                cylinder(h = plate_t + 1, d = screw_d, center = true, $fn = 32);
}
module wall_hook() {
    difference() {
        union() { backplate(); hook_arm(); }
        screw_holes();
    }
}""",
        "scad_call": "wall_hook()",
    },

    # ── 10. Spacer / Washer ───────────────────────────────────────────────────
    {
        "id":          "spacer",
        "name":        "Spacer / Washer",
        "category":    "Fasteners & Hardware",
        "tags":        ["spacer", "washer", "standoff", "shim", "bushing",
                        "ring", "gap", "fastener"],
        "description": "Flat ring spacer — useful as a washer, standoff shim, or bearing sleeve.",
        "dims": [
            {"id": "outer_d", "question": "Outer diameter (mm)",              "default": 20, "unit": "mm"},
            {"id": "inner_d", "question": "Bore / hole diameter (mm)",        "default": 5,  "unit": "mm"},
            {"id": "height",  "question": "Spacer height / thickness (mm)",   "default": 5,  "unit": "mm"},
        ],
        "scad_modules": """\
module spacer() {
    difference() {
        cylinder(h = height, d = outer_d, $fn = 64);
        translate([0, 0, -0.5]) cylinder(h = height + 1, d = inner_d, $fn = 64);
    }
}""",
        "scad_call": "spacer()",
    },

    # ── 11. Drawer Pull / Handle ──────────────────────────────────────────────
    {
        "id":          "drawer_pull",
        "name":        "Drawer Pull / Handle",
        "category":    "Furniture & Handles",
        "tags":        ["handle", "drawer pull", "cabinet", "furniture",
                        "grip", "pull", "knob"],
        "description": "Horizontal bar handle with two screw mount points.",
        "dims": [
            {"id": "span",     "question": "Centre-to-centre hole spacing (mm)", "default": 96,  "unit": "mm"},
            {"id": "grip_len", "question": "Grip bar total length (mm)",          "default": 110, "unit": "mm"},
            {"id": "grip_w",   "question": "Grip bar width (mm)",                 "default": 18,  "unit": "mm"},
            {"id": "grip_h",   "question": "Grip bar height above surface (mm)",  "default": 25,  "unit": "mm"},
            {"id": "bar_d",    "question": "Grip bar diameter/thickness (mm)",    "default": 14,  "unit": "mm"},
            {"id": "screw_d",  "question": "Screw hole diameter (mm)",            "default": 4.5, "unit": "mm"},
        ],
        "scad_modules": """\
module end_post() { cylinder(h = grip_h, d = grip_w, $fn = 48); }
module grip_bar() {
    hull() {
        translate([0, 0, grip_h - bar_d/2])
            rotate([0, 90, 0]) cylinder(h = grip_len, d = bar_d, $fn = 48);
    }
}
module drawer_pull() {
    offset_x = (grip_len - span) / 2;
    difference() {
        union() {
            translate([offset_x, 0, 0]) end_post();
            translate([offset_x + span, 0, 0]) end_post();
            translate([offset_x, -grip_len/2 + grip_w/2, 0])
                rotate([90, 0, 0]) grip_bar();
        }
        translate([offset_x, 0, -0.5]) cylinder(h = grip_h + 1, d = screw_d, $fn = 32);
        translate([offset_x + span, 0, -0.5]) cylinder(h = grip_h + 1, d = screw_d, $fn = 32);
    }
}""",
        "scad_call": "drawer_pull()",
    },

    # ── 12. Button / Switch Cap ───────────────────────────────────────────────
    {
        "id":          "button_cap",
        "name":        "Button / Switch Cap",
        "category":    "Caps & Plugs",
        "tags":        ["button", "cap", "switch", "electronics", "keyboard",
                        "push button", "replacement", "stem"],
        "description": "Replacement push-button cap that slides over a square or round stem.",
        "dims": [
            {"id": "cap_d",    "question": "Cap outer diameter (mm)",               "default": 14,  "unit": "mm"},
            {"id": "cap_h",    "question": "Cap dome height (mm)",                  "default": 7,   "unit": "mm"},
            {"id": "skirt_h",  "question": "Skirt height around base (mm)",         "default": 3,   "unit": "mm"},
            {"id": "stem_w",   "question": "Stem socket width (mm) — square stem",  "default": 4,   "unit": "mm"},
            {"id": "stem_h",   "question": "Stem socket depth (mm)",                "default": 5,   "unit": "mm"},
            {"id": "stem_gap", "question": "Socket clearance (mm, ~0.2–0.4)",       "default": 0.2, "unit": "mm"},
        ],
        "scad_modules": """\
module button_cap() {
    socket_w = stem_w + 2 * stem_gap;
    total_h  = cap_h + skirt_h;
    difference() {
        union() {
            difference() {
                cylinder(h = skirt_h, d = cap_d + 2, $fn = 64);
                translate([0, 0, -0.5]) cylinder(h = skirt_h + 1, d = cap_d - 2, $fn = 64);
            }
            translate([0, 0, skirt_h]) cylinder(h = cap_h, d = cap_d, $fn = 64);
        }
        translate([-socket_w/2, -socket_w/2, -0.5]) cube([socket_w, socket_w, stem_h + 0.5]);
    }
}""",
        "scad_call": "button_cap()",
    },
]

# ── Template helpers ──────────────────────────────────────────────────────────

_TMPL_BY_ID: dict[str, dict] = {t["id"]: t for t in INTERNAL_TEMPLATES}
TMPL_CATEGORIES: list[str] = sorted({t["category"] for t in INTERNAL_TEMPLATES})


def tmpl_get(tid: str) -> dict | None:
    return _TMPL_BY_ID.get(tid)


def tmpl_search(query: str = "", category: str = "") -> list[dict]:
    q = query.strip().lower()
    results = []
    for t in INTERNAL_TEMPLATES:
        if category and category != "All" and t["category"] != category:
            continue
        if not q:
            results.append((0, t))
            continue
        score = 0
        if q in t["name"].lower():        score += 3
        if q in t["description"].lower(): score += 2
        for tag in t["tags"]:
            if q in tag:                  score += 1
        if score:
            results.append((score, t))
    results.sort(key=lambda x: -x[0])
    return [t for _, t in results]


def tmpl_generate_scad(template: dict, dim_values: dict[str, str],
                        bed_cx: float = 117.5, bed_cy: float = 117.5) -> str:
    def _parse_num(raw: str, default: float) -> str:
        raw = raw.strip()
        if not raw:
            return str(default)
        part = raw.split()[0]
        try:
            float(part); return part
        except ValueError:
            return str(default)

    lines = [
        "// Vibe-to-Print — Single-File Edition",
        f"// Template : {template['name']}",
        f"// Generated: {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "// ── Dimensions ─────────────────────────────────────────────",
    ]
    for dim in template["dims"]:
        val  = _parse_num(dim_values.get(dim["id"], ""), dim["default"])
        unit = f" // {dim['unit']}" if dim["unit"] else ""
        lines.append(f"{dim['id']} = {val};{unit}  // {dim['question']}")
    lines += [
        "",
        "// ── Modules ──────────────────────────────────────────────────",
        "",
        template["scad_modules"].strip(),
        "",
        "// ── Place on bed ─────────────────────────────────────────────",
        f"translate([{bed_cx:.2f}, {bed_cy:.2f}, 0])",
        f"  {template['scad_call']};",
    ]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG & CSS
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Vibe-to-Print",
    page_icon="🖨️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
footer { display: none !important; }
header[data-testid="stHeader"] { height: 2rem !important; min-height: 2rem !important; }
#MainMenu { visibility: hidden; }
.main .block-container {
    padding-top: 0 !important;
    padding-bottom: 0.5rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
    max-width: 100% !important;
}
html, body, [class*="css"] { font-size: 15px !important; }
h1, h2, h3 { margin-top: 0.1rem !important; margin-bottom: 0.2rem !important; }
div.stButton > button {
    min-height: 44px !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    width: 100%;
    padding: 4px 10px !important;
}
div.stButton > button[kind="primary"] {
    min-height: 56px !important;
    font-size: 18px !important;
    border-radius: 12px !important;
}
/* Subtle back / start-over button */
div[data-testid="stButton"].start-over-btn > button {
    min-height: 28px !important;
    font-size: 12px !important;
    font-weight: 400 !important;
    padding: 2px 10px !important;
    border-radius: 6px !important;
    background: transparent !important;
    border: 1px solid #4a7fa5 !important;
    color: #7a9ab8 !important;
    width: auto !important;
}
/* Small outline style for Back / Forward nav buttons */
div[data-testid="stButton"]:has(> button[data-testid="stBaseButton-secondary"][key="nav_back"]),
div[data-testid="stButton"]:has(> button[data-testid="stBaseButton-secondary"][key="nav_fwd"]) {
    /* target by key attribute on the button itself */
}
button[data-testid="stBaseButton-secondary"][key="nav_back"],
button[data-testid="stBaseButton-secondary"][key="nav_fwd"] {
    min-height: 32px !important;
    font-size: 12px !important;
    font-weight: 400 !important;
    padding: 2px 10px !important;
    border-radius: 6px !important;
    background: transparent !important;
    border: 1px solid #4a7fa5 !important;
    color: #7a9ab8 !important;
}
/* Pointer cursor on expander headers */
div[data-testid="stExpander"] summary {
    cursor: pointer !important;
}
/* Pointer cursor on selectbox/dropdown */
div[data-testid="stSelectbox"] > div {
    cursor: pointer !important;
}
/* Pointer cursor on all Streamlit buttons */
button[kind="secondary"], button[kind="primary"] {
    cursor: pointer !important;
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE DEFAULTS
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULTS: dict = {
    "wizard_step":        "welcome",   # welcome | identify | dimensions | cad | slice
    "captured_images":    [],
    "camera_counter":     0,
    "last_cam_hash":      "",
    "image_bytes":        None,
    "image_name":         "",
    "image_media_type":   "image/jpeg",
    "vibe_description":   "",
    "identify_result":    None,        # dict from identify pipeline
    "selected_template":  None,        # template dict
    "dim_values":         {},          # {dim_id: str}
    "scad_code":          "",
    "api_key":            "",          # HF / Claude / OpenAI token
    "ai_provider":        "hf",        # hf (default) | claude | openai | none
    "camera_enabled":     False,       # camera only starts after explicit click
    "show_refinement":      False,       # toggle refinement panel in results step
    "show_buy_links":       False,       # toggle buy-links panel in results step
    "market_result":        None,        # dict from _market_search()
    "buy_search_query":     "",          # editable query in the buy panel
    "reanalyse_triggered":  False,       # triggers deep AI re-analysis
    "enhance_diagram_triggered": False,  # triggers AI SVG enhancement
    "enhanced_svg":         "",          # AI-enhanced blueprint SVG
    "nav_confirm_home":     False,       # show "go home?" confirmation on Step 1 back
    "api_key_status":       "",          # "" | "active:{prov}" | "cleared"
    "_api_key_committed":   "",          # last saved/entered key value (for Enter detection)
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Force HF as provider — migrate any old session values
if st.session_state.ai_provider in ("none", "ollama", ""):
    st.session_state.ai_provider = "hf"


def _go(step: str) -> None:
    st.session_state.wizard_step = step
    st.rerun()


_WIZARD_STEPS = [
    ("identify",   "📸 Identify"),
    ("results",    "🔍 Review"),
    ("dimensions", "📦 Export"),
]

def _step_indicator(current_step: str) -> None:
    """Render a horizontal step-progress bar for the 3 wizard steps."""
    total  = len(_WIZARD_STEPS)
    index  = next((i for i, (s, _) in enumerate(_WIZARD_STEPS) if s == current_step), 0)
    number = index + 1

    circles = ""
    for i, (_, label) in enumerate(_WIZARD_STEPS):
        if i < index:                      # completed
            dot_bg, dot_color, dot_border = "#4caf50", "#fff", "#4caf50"
            symbol = "✓"
        elif i == index:                   # current
            dot_bg, dot_color, dot_border = "#1a6fa8", "#fff", "#1a6fa8"
            symbol = str(i + 1)
        else:                              # future
            dot_bg, dot_color, dot_border = "transparent", "#7a9ab8", "#4a7fa5"
            symbol = str(i + 1)

        label_weight = "700" if i == index else "400"
        label_color  = "#e0f0ff" if i == index else "#7a9ab8"

        # Connector line before each step except the first
        connector = (
            f'<div style="flex:1;height:2px;background:'
            f'{"#4caf50" if i <= index else "#2a4a6a"};'
            f'margin:0 4px;align-self:center;min-width:12px"></div>'
            if i > 0 else ""
        )

        circles += (
            f'{connector}'
            f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px">'
            f'  <div style="width:28px;height:28px;border-radius:50%;'
            f'background:{dot_bg};border:2px solid {dot_border};'
            f'display:flex;align-items:center;justify-content:center;'
            f'font-size:12px;font-weight:700;color:{dot_color}">{symbol}</div>'
            f'  <div style="font-size:11px;font-weight:{label_weight};'
            f'color:{label_color};white-space:nowrap">{label}</div>'
            f'</div>'
        )

    st.markdown(
        f'<div style="display:flex;align-items:flex-start;justify-content:center;'
        f'padding:8px 0 4px 0;margin-bottom:4px">{circles}</div>'
        f'<div style="text-align:center;font-size:11px;color:#7a9ab8;'
        f'margin-bottom:8px">Step {number} of {total}</div>',
        unsafe_allow_html=True,
    )


# ── Back / step indicator / Forward — shown on every non-welcome step ─────────
if st.session_state.wizard_step != "welcome":
    _step_order  = [s for s, _ in _WIZARD_STEPS]   # ["identify","results","dimensions"]
    _cur_step    = st.session_state.wizard_step
    _cur_idx     = _step_order.index(_cur_step) if _cur_step in _step_order else 0
    _has_result  = st.session_state.identify_result is not None
    _is_last     = _cur_idx >= len(_step_order) - 1
    _fwd_enabled = _has_result and not _is_last

    _back_col, _ind_col, _fwd_col = st.columns([1, 5, 1])

    with _back_col:
        if st.button("← Back", key="nav_back", use_container_width=True):
            if _cur_idx == 0:
                # Step 1 → ask before returning to welcome
                st.session_state.nav_confirm_home = True
                st.rerun()
            else:
                st.session_state.nav_confirm_home = False
                _go(_step_order[_cur_idx - 1])

    with _ind_col:
        _step_indicator(_cur_step)

    with _fwd_col:
        if not _is_last:
            if st.button("Forward →", key="nav_fwd", use_container_width=True,
                         disabled=not _fwd_enabled,
                         help="" if _fwd_enabled else "Complete analysis first"):
                _go(_step_order[_cur_idx + 1])

    # Confirmation dialog — only shown when Back is pressed on Step 1
    if st.session_state.get("nav_confirm_home"):
        st.warning(
            "Go back to the home screen? Your current progress will be cleared."
        )
        _yes_col, _cancel_col, _ = st.columns([1, 1, 4])
        with _yes_col:
            if st.button("Yes, go home", key="nav_confirm_yes", type="primary"):
                for _k in list(st.session_state.keys()):
                    del st.session_state[_k]
                st.rerun()
        with _cancel_col:
            if st.button("Cancel", key="nav_confirm_cancel"):
                st.session_state.nav_confirm_home = False
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 0 — WELCOME
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.wizard_step == "welcome":
    st.markdown("""
<div style="
    display:flex; flex-direction:column; align-items:center;
    justify-content:center; min-height:80vh; text-align:center;
    padding: 2rem 1rem;
">
  <div style="font-size:64px; margin-bottom:16px">🖨️</div>
  <h1 style="
    font-size:clamp(26px,6vw,42px); font-weight:900;
    color:#a8dadc; margin-bottom:12px; line-height:1.15;
  ">Vibe-to-Print</h1>
  <p style="
    font-size:clamp(15px,3vw,20px); color:#cdd8e0;
    max-width:520px; line-height:1.6; margin-bottom:32px;
  ">
    Snap. Describe. Print.<br>
    Your AI-powered shortcut from a photo of a broken part
    to a printable 3D design — no CAD experience needed.
  </p>
</div>
""", unsafe_allow_html=True)

    # Centre the button with spacer columns
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        if st.button("🚀 Get Started", type="primary", use_container_width=True):
            _go("identify")

    # ── How it works ──────────────────────────────────────────────────────────
    st.markdown(
        '<div style="text-align:center;margin-top:1.5rem;font-size:0.9rem;'
        'color:#7eb8d4">How it works ↓</div>',
        unsafe_allow_html=True,
    )
    with st.expander(""):
        st.markdown("""
**Step 1 — Snap or upload a photo**

Take a photo of the broken or missing part, or upload one from your device. You can submit multiple photos for better accuracy.

---

**Step 2 — Describe what you need**

Type a short description of what the part does or what you're trying to replace. For example: "the knob that fell off my oven dial."

---

**Step 3 — AI analyses your part**

The app identifies the part, its measurements, and generates a 3D-printable design file automatically — no CAD skills needed.

---

**Step 4 — Print it or buy it**

Download the design file to 3D print the part yourself, or use the search links to find and buy the original part online.
""")

    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# AI ANALYSIS ENGINE  (embedded — no external module imports)
# ══════════════════════════════════════════════════════════════════════════════

# ── Hugging Face model config ─────────────────────────────────────────────────
# Token is read from Streamlit Cloud secrets (Settings → Secrets → HF_TOKEN).
# For local dev, set the environment variable: export HF_TOKEN=hf_...
import os as _os
_HF_TOKEN_DEFAULT = _os.environ.get("HF_TOKEN", "")

_BLIP_URL     = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
_HF_TEXT_MODEL = "HuggingFaceH4/zephyr-7b-beta"   # primary text model
_BLIP_TIMEOUT = 35
_HF_TIMEOUT   = 60


def _effective_hf_token() -> str:
    """Return the best available HF token: session key → hardcoded default."""
    return st.session_state.get("api_key", "") or _HF_TOKEN_DEFAULT


def _blip_caption(image_bytes: bytes) -> str:
    """
    Send image to Salesforce/blip-image-captioning-large on HF Inference API.
    Uses _effective_hf_token() automatically. Returns '' on failure.
    """
    token   = _effective_hf_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = requests.post(_BLIP_URL, headers=headers,
                          data=image_bytes, timeout=_BLIP_TIMEOUT)
        if r.status_code == 503:
            # Model warming up — wait and retry once
            time.sleep(12)
            r = requests.post(_BLIP_URL, headers=headers,
                              data=image_bytes, timeout=_BLIP_TIMEOUT)
        if r.ok:
            data = r.json()
            if isinstance(data, list) and data:
                return data[0].get("generated_text", "").strip()
    except Exception:
        pass
    return ""


def _hf_chat(prompt: str, max_tokens: int = 512) -> str:
    """
    Single-turn chat via HuggingFaceH4/zephyr-7b-beta on HF Inference API.
    Falls back to mistralai/Mistral-7B-Instruct-v0.2 if the primary model errors.
    """
    token = _effective_hf_token()
    for model in (_HF_TEXT_MODEL, "mistralai/Mistral-7B-Instruct-v0.2"):
        try:
            from huggingface_hub import InferenceClient
            client = InferenceClient(token=token or None)
            resp   = client.chat_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
        except Exception:
            continue
    return ""


# ── Keyword fallback: creation idea ──────────────────────────────────────────

_KEYWORD_MAP = [
    (["knob", "dial", "control", "pot", "rotary", "stove"],
     "Replacing a missing or broken control knob."),
    (["hinge", "door", "lid", "flap"],
     "Replacing a broken hinge or pivot."),
    (["bracket", "mount", "holder", "clip", "clamp", "shelf"],
     "Fabricating a custom mounting bracket or holder."),
    (["gear", "cog", "wheel", "sprocket"],
     "Replacing a broken gear or drive wheel."),
    (["hook", "hang", "wall"],
     "Making a wall-mount hook or hanger."),
    (["box", "enclosure", "case", "tray", "container"],
     "Building a custom enclosure or storage box."),
    (["handle", "grip", "pull", "lever"],
     "Replacing a handle or grip."),
    (["cap", "plug", "cover", "stopper", "end cap"],
     "Making a protective cap or tube plug."),
    (["spacer", "washer", "shim", "standoff"],
     "Fabricating a precision spacer or washer."),
    (["cable", "wire", "cord"],
     "Making a cable management clip."),
    (["button", "switch", "key"],
     "Replacing a push-button or switch cap."),
    (["drawer", "cabinet", "furniture"],
     "Replacing a drawer pull or cabinet handle."),
]

_KEYWORD_TEMPLATE_MAP = [
    (["knob", "dial", "stove", "d-shaft", "d shaft", "potentiometer", "pot"],
     "knob_d_shaft"),
    (["set screw", "round shaft", "round bore"],
     "knob_round_shaft"),
    (["pointer", "indicator"],
     "knob_pointer"),
    (["box", "tray", "container", "open top", "organiser"],
     "box_open"),
    (["lid", "enclosure", "case", "project box"],
     "box_with_lid"),
    (["cap", "plug", "tube", "pipe", "end cap", "stopper"],
     "end_cap"),
    (["bracket", "l bracket", "angle", "mount", "shelf support"],
     "l_bracket"),
    (["cable", "wire", "clip", "snap"],
     "cable_clip"),
    (["hook", "wall hook", "hanger", "coat"],
     "wall_hook"),
    (["spacer", "washer", "shim", "standoff", "bushing"],
     "spacer"),
    (["drawer", "handle", "pull", "cabinet", "furniture"],
     "drawer_pull"),
    (["button", "switch cap", "key cap", "push button"],
     "button_cap"),
]


def _keyword_template(caption: str, description: str) -> str | None:
    text = f"{caption} {description}".lower()
    for keywords, tid in _KEYWORD_TEMPLATE_MAP:
        if any(kw in text for kw in keywords):
            return tid
    return None


def _keyword_description(caption: str, description: str, template: dict | None) -> str:
    if template:
        return f"Replacing or replicating a {template['name'].lower()}. {template['description']}"
    text = f"{caption} {description}".lower()
    for keywords, idea in _KEYWORD_MAP:
        if any(kw in text for kw in keywords):
            return idea
    return (f"Creating a custom 3D-printed replacement part based on "
            f"{'the photo' if caption else 'your description'}.")


def _default_dims(template: dict) -> dict[str, str]:
    return {d["id"]: str(d["default"]) for d in template["dims"]}


# ── Vision AI (Claude / OpenAI) ───────────────────────────────────────────────

_VISION_SYSTEM_PROMPT = """\
System Role: You are a mechanical engineering assistant specialized in \
"Right to Repair" and 3D modeling.

Task: Analyze the uploaded image of a broken or missing part.

Visual Forensic Description: Describe the part's material (e.g., ABS plastic, \
brushed aluminum), color, texture, and the specific nature of any damage or wear.

Part Identification: Identify exactly what this part is (e.g., "GE Washing Machine \
Timer Knob, Model X") and its functional category.

Replacement Search Terms: Provide 3-5 specific keyword strings a user should use \
to find an OEM replacement.

Technical Schematic Data: Provide the critical dimensions required for a 3D-printed \
replacement. Use millimetres. Match dimension IDs to the selected template_id below.

SVG Diagram Code: Generate a clean, high-contrast SVG technical drawing of the part. \
Style it as a professional blueprint: dark navy background (#0d1b2a), white/cyan \
construction lines (#00e5ff), red dimension annotations (#ff1744). \
Use viewBox="0 0 400 300". No external references, no filters, no clipPath. \
Label the most important dimensions directly on the drawing.

Available template IDs (choose the closest match):
  knob_d_shaft, knob_round_shaft, knob_pointer,
  box_open, box_with_lid, end_cap, l_bracket,
  cable_clip, wall_hook, spacer, drawer_pull, button_cap

Part Description: Write 2-3 plain-English sentences describing exactly what this part \
is and what it does functionally (e.g. "A D-shaft rotary knob used to control a \
potentiometer or selector switch. The flat side of the shaft ensures the knob locks \
in position without slipping.").

Device Context: Describe the likely appliance or device this part comes from, in one \
sentence (e.g. "This part is commonly found on kitchen appliances, audio equipment, \
or HVAC controls.").

Constraint: Output ONLY a valid JSON object — no markdown, no prose, nothing else.
JSON structure:
{
  "visual_description": "...",
  "part_description": "2-3 sentences describing what the part is and does",
  "device_context": "one sentence describing the likely device/appliance",
  "part_name": "...",
  "part_model": "...",
  "category": "...",
  "search_terms": ["...", "...", "..."],
  "dimensions": {"dim_id": numeric_value},
  "template_id": "...",
  "svg_code": "<svg ...>...</svg>",
  "creation_idea": "one sentence describing what to 3D-print"
}"""

_TEMPLATE_IDS = {t["id"] for t in INTERNAL_TEMPLATES}


def _vision_ai_analyze(
    image_bytes: bytes,
    description: str,
    provider: str,
    api_key: str,
) -> dict | None:
    """
    Send image to Claude or OpenAI vision model using the engineering system prompt.
    Returns parsed JSON dict, or a dict with key "_error" on failure.
    Returns None if provider is unsupported.
    """
    img_b64   = base64.b64encode(image_bytes).decode()
    user_text = (f"User description: {description}" if description
                 else "Please analyse this part.")

    raw: str | None = None

    if provider == "claude":
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp   = client.messages.create(
                model      = "claude-opus-4-5",
                max_tokens = 2048,
                system     = _VISION_SYSTEM_PROMPT,
                messages   = [{
                    "role": "user",
                    "content": [
                        {"type": "image",
                         "source": {"type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": img_b64}},
                        {"type": "text", "text": user_text},
                    ],
                }],
            )
            raw = resp.content[0].text
        except Exception as exc:
            return {"_error": str(exc)}

    elif provider == "openai":
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp   = client.chat.completions.create(
                model      = "gpt-4o",
                max_tokens = 2048,
                messages   = [
                    {"role": "system", "content": _VISION_SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                        {"type": "text", "text": user_text},
                    ]},
                ],
            )
            raw = resp.choices[0].message.content
        except Exception as exc:
            return {"_error": str(exc)}

    elif provider == "gemini":
        try:
            _url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-1.5-flash:generateContent?key={api_key}"
            )
            _payload = {
                "system_instruction": {"parts": [{"text": _VISION_SYSTEM_PROMPT}]},
                "contents": [{"parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                    {"text": user_text},
                ]}],
                "generationConfig": {"maxOutputTokens": 2048},
            }
            _r = requests.post(_url, json=_payload, timeout=40)
            _r.raise_for_status()
            raw = _r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            return {"_error": str(exc)}

    else:
        return None

    if not raw:
        return {"_error": "Vision AI returned empty response."}

    # Strip markdown code fences if the model wrapped the JSON
    raw = raw.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw).strip()

    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {"_error": "Could not parse AI response as JSON.", "_raw": raw[:400]}


# ── Master analysis function ──────────────────────────────────────────────────

def analyze_input(
    image_bytes:  bytes | None,
    description:  str,
    hf_token:     str = "",
    ai_provider:  str = "none",
) -> dict:
    """
    Full pipeline: vision AI → BLIP caption → template match → result.

    Returns a dict with at minimum:
      caption, project_description, template_id, template_name,
      object_type, suggested_dims, method, warning,
      part_name, part_model, search_terms, ai_svg
    """
    caption = ""
    warning = ""
    method  = "keyword"

    # ── Path A: Vision AI (Claude / OpenAI / Gemini) — richest result ─────────
    if ai_provider in ("claude", "openai", "gemini") and image_bytes and hf_token:
        vision = _vision_ai_analyze(image_bytes, description, ai_provider, hf_token)
        if vision and "_error" not in vision:
            tid  = vision.get("template_id", "")
            tmpl = tmpl_get(tid) if tid in _TEMPLATE_IDS else None
            if not tmpl:
                # Template ID the model chose isn't valid — fall back to keyword
                matches = tmpl_search(
                    f"{vision.get('part_name','')} {vision.get('category','')}"
                )
                tmpl = matches[0] if matches else INTERNAL_TEMPLATES[0]
            dims = _default_dims(tmpl)
            for did, val in (vision.get("dimensions") or {}).items():
                if did in dims:
                    dims[did] = str(val)
            return {
                "caption":             vision.get("visual_description", ""),
                "project_description": vision.get("creation_idea", ""),
                "template_id":         tmpl["id"],
                "template_name":       tmpl["name"],
                "object_type":         tmpl["category"],
                "suggested_dims":      dims,
                "method":              f"{ai_provider}_vision",
                "warning":             "",
                "part_name":           vision.get("part_name", ""),
                "part_model":          vision.get("part_model", ""),
                "search_terms":        vision.get("search_terms", []),
                "ai_svg":              vision.get("svg_code", ""),
                "part_description":    vision.get("part_description", ""),
                "device_description":  vision.get("device_context", ""),
            }
        elif vision and "_error" in vision:
            warning = "Deep analysis unavailable right now — using standard identification instead."

    # ── Path B: BLIP caption + HF text model ─────────────────────────────────
    if image_bytes:
        caption = _blip_caption(image_bytes)
        if not caption:
            warning = warning or ("⏳ Getting things ready — the AI is starting up and may take up to 30 seconds on first use. Hang tight!")

    combined = f"{caption} {description}".strip()
    ai_json: dict | None = None

    if combined and ai_provider in ("hf", "none"):
        tmpl_list = "\n".join(
            f"  {t['id']}: {t['name']} — {t['description']}"
            for t in INTERNAL_TEMPLATES
        )
        prompt = (
            f"You are a 3D printing expert. Analyse this request and respond "
            f"with ONLY a JSON object — no other text.\n\n"
            f"Image caption: {caption or '(no image)'}\n"
            f"User request: {description or '(no description)'}\n\n"
            f"Available templates:\n{tmpl_list}\n\n"
            f"Respond with this exact JSON structure:\n"
            f'{{\n'
            f'  "project_description": "one or two sentences describing the task",\n'
            f'  "template_id": "exact id from the list above",\n'
            f'  "suggested_dims": {{"dim_id": numeric_value, ...}}\n'
            f'}}'
        )
        raw = _hf_chat(prompt)

        if raw:
            try:
                clean = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")
                m = re.search(r"\{.*\}", clean, re.DOTALL)
                if m:
                    ai_json = json.loads(m.group())
                    method  = ai_provider
            except Exception:
                ai_json = None

    # ── Path C: Keyword fallback ──────────────────────────────────────────────
    if ai_json:
        tid      = ai_json.get("template_id", "")
        template = tmpl_get(tid)
        if not template:
            ai_json = None

    if not ai_json:
        tid  = _keyword_template(caption, description)
        if not tid:
            matches = tmpl_search(combined)
            tid     = matches[0]["id"] if matches else INTERNAL_TEMPLATES[0]["id"]
        template = tmpl_get(tid)
        method   = "keyword"

    template = template or INTERNAL_TEMPLATES[0]

    if ai_json:
        proj_desc = ai_json.get("project_description", "")
        dims      = _default_dims(template)
        for did, val in (ai_json.get("suggested_dims") or {}).items():
            if did in dims:
                dims[did] = str(val)
    else:
        proj_desc = _keyword_description(caption, description, template)
        dims      = _default_dims(template)

    return {
        "caption":             caption,
        "project_description": proj_desc or _keyword_description(caption, description, template),
        "template_id":         template["id"],
        "template_name":       template["name"],
        "object_type":         template["category"],
        "suggested_dims":      dims,
        "method":              method,
        "warning":             warning,
        "part_name":           "",
        "part_model":          "",
        "search_terms":        [],
        "ai_svg":              "",
        "part_description":    "",
        "device_description":  "",
    }


# ══════════════════════════════════════════════════════════════════════════════
# PART IMAGE SEARCH  — fetch thumbnail URLs via DDG Instant Answers
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_part_images(part_name: str, max_images: int = 3) -> list[str]:
    """
    Try to retrieve image URLs for a part using the DuckDuckGo Instant Answer
    API (no key required).  Returns a list of up to max_images URLs.
    Fails silently and returns [] on any error.
    """
    if not part_name:
        return []
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q":             part_name,
                "format":        "json",
                "no_html":       "1",
                "skip_disambig": "1",
            },
            timeout=6,
        )
        r.raise_for_status()
        data = r.json()

        urls: list[str] = []

        # Primary image from the Instant Answer
        primary = data.get("Image") or data.get("Thumbnail") or ""
        if primary and primary.startswith("http"):
            urls.append(primary)

        # Related-topic images
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict):
                icon = topic.get("Icon", {})
                url  = (icon.get("URL") or "").strip()
                if url and url.startswith("http") and url not in urls:
                    urls.append(url)
            if len(urls) >= max_images:
                break

        return urls[:max_images]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# AI DIAGRAM ENHANCEMENT  — ask AI to generate a richer annotated SVG
# ══════════════════════════════════════════════════════════════════════════════

def _enhance_diagram_with_ai(
    part_name:        str,
    part_description: str,
    template_name:    str,
    dim_values:       dict,
    provider:         str,
    api_key:          str,
) -> str:
    """
    Ask the selected AI model (text-only) to produce a detailed annotated
    SVG blueprint.  Returns the SVG string or "" on any failure.
    """
    dims_text = ", ".join(f"{k}={v}mm" for k, v in dim_values.items()) or "unknown"
    prompt = (
        f"Generate a clean, detailed technical SVG blueprint for this 3D-printable part.\n\n"
        f"Part: {part_name or template_name}\n"
        f"Description: {part_description or template_name}\n"
        f"Key dimensions: {dims_text}\n\n"
        f"Requirements:\n"
        f"- Dark navy background (#0d1b2a), viewBox=\"0 0 400 300\"\n"
        f"- White/cyan construction lines (#00e5ff)\n"
        f"- Red dimension annotation lines and text (#ff1744)\n"
        f"- Label ALL key dimensions with arrows and mm values\n"
        f"- Include both a top view and a side/front view\n"
        f"- No external references, no filters, no clipPath\n\n"
        f"Output ONLY the raw SVG code — no markdown, no prose."
    )
    raw = ""
    try:
        if provider == "claude":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp   = client.messages.create(
                model="claude-opus-4-5", max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text
        elif provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp   = client.chat.completions.create(
                model="gpt-4o", max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.choices[0].message.content
        elif provider == "gemini":
            _url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-1.5-flash:generateContent?key={api_key}"
            )
            _r = requests.post(
                _url,
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": 2048}},
                timeout=40,
            )
            _r.raise_for_status()
            raw = _r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return ""

    if not raw:
        return ""
    raw = raw.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw).strip()
    m = re.search(r"<svg[\s\S]*?</svg>", raw, re.IGNORECASE)
    return m.group() if m else ""


# ══════════════════════════════════════════════════════════════════════════════
# MARKET RESEARCH  — Buy vs. Print price comparison
# ══════════════════════════════════════════════════════════════════════════════

# Estimated filament use and cost at ~$20/kg PLA (≈ $0.02/g)
_PRINT_COST: dict[str, tuple[str, str]] = {
    "Knobs & Controls":     ("12–18 g",  "$0.24–$0.36"),
    "Enclosures & Boxes":   ("40–80 g",  "$0.80–$1.60"),
    "Caps & Plugs":         ("4–8 g",    "$0.08–$0.16"),
    "Brackets & Mounts":    ("15–25 g",  "$0.30–$0.50"),
    "Cable Management":     ("6–10 g",   "$0.12–$0.20"),
    "Hooks & Hangers":      ("12–20 g",  "$0.24–$0.40"),
    "Fasteners & Hardware": ("2–5 g",    "$0.04–$0.10"),
    "Furniture & Handles":  ("20–35 g",  "$0.40–$0.70"),
}
_PRINT_COST_DEFAULT = ("10–20 g", "< $0.50")

_PRICE_RE = re.compile(
    r'(?:[$£€])\s*\d{1,4}(?:\.\d{2})?'
    r'|\d{1,4}(?:\.\d{2})?\s*(?:USD|GBP|EUR|dollars?)',
    re.IGNORECASE,
)


def _market_search(part_name: str, category: str = "") -> dict:
    """
    Query DuckDuckGo Instant Answers for retail pricing on a part.

    Returns:
        abstract     : str        — DDG text (may be empty)
        prices       : list[str]  — price strings found in abstract
        buy_links    : list[dict] — [{site, url}, ...]
        print_weight : str
        print_cost   : str
        error        : str        — non-fatal; empty on success
    """
    result: dict = {
        "abstract":     "",
        "prices":       [],
        "buy_links":    [],
        "print_weight": _PRINT_COST_DEFAULT[0],
        "print_cost":   _PRINT_COST_DEFAULT[1],
        "error":        "",
    }

    if category in _PRINT_COST:
        result["print_weight"], result["print_cost"] = _PRINT_COST[category]

    # ── DuckDuckGo Instant Answers ─────────────────────────────────────────
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q":             f"{part_name} replacement part buy price",
                "format":        "json",
                "no_html":       "1",
                "skip_disambig": "1",
            },
            timeout=8,
        )
        r.raise_for_status()
        ddg = r.json()
        blob = (ddg.get("Abstract") or ddg.get("Answer") or "").strip()
        for topic in ddg.get("RelatedTopics", [])[:6]:
            if isinstance(topic, dict) and topic.get("Text"):
                blob += " " + topic["Text"]
        result["abstract"] = blob[:600]
        found = _PRICE_RE.findall(blob)
        result["prices"] = list(dict.fromkeys(found))[:4]
    except requests.Timeout:
        result["error"] = "Price search took too long — showing search links only."
    except Exception as exc:
        result["error"] = "Couldn't fetch prices right now — showing search links instead."

    # ── Pre-formed shopping search URLs (no API key required) ─────────────
    q = urllib.parse.quote_plus(part_name)
    result["buy_links"] = [
        {"site": "Amazon",
         "url":  f"https://www.amazon.com/s?k={q}"},
        {"site": "eBay",
         "url":  f"https://www.ebay.com/sch/i.html?_nkw={q}"},
        {"site": "RepairClinic",
         "url":  f"https://www.repairclinic.com/Search?q={q}"},
        {"site": "ApplianceParts",
         "url":  f"https://www.appliancepartspros.com/search?q={q}"},
    ]
    return result


def _vibe_message(prices: list[str], print_cost: str) -> str:
    """Return the context-aware 'should I print?' nudge."""
    if not prices:
        return (
            f"Original parts can cost $10–$50+ and take days to ship. "
            f"Print a custom version right now for {print_cost} in filament."
        )
    raw = prices[0]
    digits = re.sub(r"[^0-9.]", "", raw.split()[0])
    try:
        val = float(digits)
    except ValueError:
        return f"Print a custom fit for just {print_cost} instead of waiting for a delivery."
    if val < 5:
        return (
            f"The original part is only **{raw}** — printing may save time more than money, "
            f"but you'll get a perfect custom fit either way."
        )
    if val < 25:
        return (
            f"The original part runs **{raw}** and likely takes days to ship. "
            f"Print a custom version right now for {print_cost} in filament."
        )
    return (
        f"At **{raw}** for the original (plus shipping), printing your own saves serious cash "
        f"— and you get an exact fit, not a generic replacement."
    )


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — INPUT  (photo + description → AI analysis)
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.wizard_step == "identify":

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        '<h2 style="color:#a8dadc;margin-bottom:4px">📸 Step 1 — Show us the part</h2>'
        '<p style="color:#7a9ab8;font-size:13px;margin-bottom:16px">'
        'Snap a photo and describe what you need — the AI does the rest.</p>',
        unsafe_allow_html=True,
    )

    # ── Photo input — camera OR upload ────────────────────────────────────────
    tab_cam, tab_upload = st.tabs(["📷 Take Photo", "🖼️ Upload Photos"])

    # Helper: set of hashes already in the list (prevents duplicates)
    def _known_hashes() -> set:
        return {img["hash"] for img in st.session_state.captured_images}

    with tab_cam:
        if not st.session_state.camera_enabled:
            st.markdown(
                '<div style="border:2px dashed #4a7fa5;border-radius:12px;'
                'padding:40px 20px;text-align:center;background:#0d1b2a;'
                'margin:8px 0">'
                '<div style="font-size:52px;margin-bottom:12px">📷</div>'
                '<div style="color:#a8dadc;font-size:14px;margin-bottom:16px">'
                'Camera is off — tap below to start</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button("Enable Camera", use_container_width=True, type="primary"):
                st.session_state.camera_enabled = True
                st.rerun()
        else:
            cam_key   = f"cam_{st.session_state.camera_counter}"
            cam_photo = st.camera_input("Take a photo of the part", key=cam_key,
                                        label_visibility="collapsed")
            st.caption("💡 Tip: Centre the part in the frame with good lighting for best results.")
            if cam_photo is not None:
                _bytes = cam_photo.getvalue()
                _hash  = hashlib.md5(_bytes).hexdigest()
                if _hash not in _known_hashes():
                    st.session_state.captured_images.append({
                        "bytes": _bytes,
                        "name":  f"photo_{st.session_state.camera_counter}.jpg",
                        "mime":  "image/jpeg",
                        "hash":  _hash,
                    })
                    st.session_state.camera_counter += 1
                    st.rerun()
            if st.button("Turn Off Camera", use_container_width=True):
                st.session_state.camera_enabled = False
                st.rerun()

    with tab_upload:
        uploaded_files = st.file_uploader(
            "Choose one or more photos from your device",
            type=["jpg", "jpeg", "png", "webp", "heic"],
            accept_multiple_files=True,
            key="photo_uploader",
            label_visibility="collapsed",
        )
        if uploaded_files:
            _known = _known_hashes()
            _added = 0
            for uf in uploaded_files:
                _bytes = uf.read()
                _hash  = hashlib.md5(_bytes).hexdigest()
                if _hash not in _known:
                    st.session_state.captured_images.append({
                        "bytes": _bytes,
                        "name":  uf.name,
                        "mime":  uf.type or "image/jpeg",
                        "hash":  _hash,
                    })
                    _known.add(_hash)
                    _added += 1
            if _added:
                st.rerun()

    # ── Photo gallery ─────────────────────────────────────────────────────────
    imgs = st.session_state.captured_images
    if imgs:
        # Keep image_bytes pointing at the first photo for the AI pipeline
        st.session_state.image_bytes      = imgs[0]["bytes"]
        st.session_state.image_media_type = imgs[0]["mime"]
        st.session_state.image_name       = imgs[0]["name"]

        n = len(imgs)
        st.caption(
            f"{'📌 ' if n == 1 else f'📌 {n} photos — '}"
            f"{'first photo used for AI analysis' if n > 1 else 'ready'}"
        )

        cols = st.columns(3)
        _remove_idx = None
        for i, img in enumerate(imgs):
            with cols[i % 3]:
                st.image(img["bytes"], caption=img["name"][:18],
                         use_container_width=True)
                if st.button("✕", key=f"rm_{img['hash']}",
                             use_container_width=True, help="Remove"):
                    _remove_idx = i

        if _remove_idx is not None:
            st.session_state.captured_images.pop(_remove_idx)
            if not st.session_state.captured_images:
                st.session_state.image_bytes = None
            st.rerun()

        if n > 1 and st.button("🗑️ Clear all photos", use_container_width=True):
            st.session_state.captured_images = []
            st.session_state.image_bytes     = None
            st.session_state.camera_counter += 1
            st.rerun()
    else:
        st.session_state.image_bytes = None

    # ── Description ───────────────────────────────────────────────────────────
    description = st.text_input(
        "What do you need?",
        value=st.session_state.vibe_description,
        placeholder="e.g., replace knobs that are missing.",
        label_visibility="visible",
    )
    st.session_state.vibe_description = description
    st.caption("Describe the repair or replacement you need — e.g., a broken drawer knob, a cracked bracket.")

    st.divider()

    # ── Analyse button ────────────────────────────────────────────────────────
    has_input = bool(st.session_state.captured_images or description.strip())

    if not has_input:
        st.markdown(
            '<div style="background:#fff3cd;border:1px solid #f0c040;'
            'border-radius:8px;padding:10px 14px;font-size:14px;color:#5d4037;'
            'margin-bottom:8px">⚠️ '
            'Add a <strong>photo</strong> and/or a <strong>description</strong> '
            'to continue.</div>',
            unsafe_allow_html=True,
        )

    if st.button("✨ Analyse My Part",
                 type="primary",
                 use_container_width=True):

        if not has_input:
            st.error("⚠️ Please add a photo or enter a description first.",
                     icon="📸")
            st.stop()

        with st.spinner("⏳ Getting things ready — the AI is starting up and may take up to 30 seconds on first use. Hang tight!"):
            _result = analyze_input(
                image_bytes  = st.session_state.image_bytes,
                description  = description,
                hf_token     = st.session_state.api_key,
                ai_provider  = st.session_state.ai_provider,
            )

        with st.spinner("🔎 Searching for prices online…"):
            _mq = _result.get("template_name") or description or "replacement part"
            st.session_state.market_result = _market_search(
                _mq, _result.get("object_type", "")
            )

        st.session_state.identify_result         = _result
        st.session_state.selected_template       = tmpl_get(_result["template_id"])
        st.session_state.dim_values              = _result["suggested_dims"]
        st.session_state.show_buy_links          = False
        st.session_state.buy_search_query        = ""
        st.session_state.reanalyse_triggered     = False
        st.session_state.enhance_diagram_triggered = False
        st.session_state.enhanced_svg            = ""
        _go("results")

    # ── Power-user upgrade panel (hidden by default) ──────────────────────────
    with st.expander("⚙️ AI Settings (optional)"):

        # ── Persistent status badge ────────────────────────────────────────────
        _ks = st.session_state.api_key_status
        if _ks.startswith("active:"):
            _active_prov = _ks.split(":", 1)[1]
            _prov_label  = {"claude": "Anthropic Claude",
                            "openai": "GPT-4o",
                            "gemini": "Google Gemini"}.get(_active_prov, _active_prov)
            st.success(f"✅ {_prov_label} key is active — enhanced analysis enabled.")
        elif _ks == "cleared":
            st.info("AI key removed — using default Hugging Face analysis.")

        st.caption("AI analysis works automatically out of the box. "
                   "Add a Claude, GPT-4o, or Gemini key for deeper, more detailed part identification.")

        _providers = [
            "hf — Hugging Face (active)",
            "claude — Anthropic Claude ✨",
            "openai — GPT-4o ✨",
            "gemini — Google Gemini ✨ (Free)",
        ]
        _pkeys = ["hf", "claude", "openai", "gemini"]
        _cur   = st.session_state.ai_provider
        _idx   = _pkeys.index(_cur) if _cur in _pkeys else 0
        _provider = st.selectbox("AI brain", _providers, index=_idx,
                                 key="_provider_sel")
        st.session_state.ai_provider = _provider.split()[0]
        _prov = st.session_state.ai_provider

        def _commit_key(key_value: str, provider: str) -> None:
            """Save the key and update the status badge."""
            st.session_state.api_key            = key_value
            st.session_state._api_key_committed = key_value
            st.session_state.api_key_status     = (
                f"active:{provider}" if key_value else "cleared"
            )

        if _prov in ("claude", "openai", "gemini"):
            _labels       = {"claude": "Anthropic API key",
                             "openai": "OpenAI API key",
                             "gemini": "Google API key"}
            _placeholders = {"claude": "sk-ant-…", "openai": "sk-…", "gemini": "AIza…"}

            _tok = st.text_input(
                _labels[_prov], type="password",
                value=st.session_state.api_key,
                placeholder=_placeholders[_prov],
            )
            # Detect Enter (value changed since last commit)
            if _tok != st.session_state._api_key_committed:
                _commit_key(_tok, _prov)
            else:
                st.session_state.api_key = _tok

            st.caption("Paste your key above, then click **Save Key** or press Enter to activate.")

            if st.button("💾 Save Key", key="_save_key_btn"):
                _commit_key(_tok, _prov)
                st.rerun()

            _instructions = {
                "claude": """
**How to get your Anthropic API key:**
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in or create a free account
3. Click **"API Keys"** in the left sidebar
4. Click **"Create Key"**, give it a name, and copy it
5. Paste the key above
""",
                "openai": """
**How to get your OpenAI API key:**
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Sign in or create an account
3. Click **"Create new secret key"**
4. Copy the key immediately (you won't see it again)
5. Paste the key above
""",
                "gemini": """
**How to get your free Google Gemini API key:**
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Sign in with your Google account
3. Click **"Get API key"** in the top left
4. Click **"Create API key"**
5. Copy the key and paste it above
""",
            }
            st.markdown(_instructions[_prov])

    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# SVG SCHEMATIC DIAGRAMS  (one per template, embedded inline)
# ══════════════════════════════════════════════════════════════════════════════

_SC  = "#1a6fa8"   # part stroke
_SF  = "#daeeff"   # part fill
_SD  = "#e63946"   # dimension colour
_ST  = "#222222"   # general text

_SVG_W, _SVG_H = 320, 200


def _svg_wrap(inner: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_SVG_W} {_SVG_H}" '
        'style="width:100%;max-width:420px;border:1px solid #cde;'
        'border-radius:8px;background:#fafcff">'
        + inner + "</svg>"
    )


def _hline(x1: float, y: float, x2: float, lbl: str,
           above: bool = True, col: str = _SD) -> str:
    tk = 5
    yo = y - 14 if above else y + 14
    mx = (x1 + x2) / 2
    return (
        f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" '
        f'stroke="{col}" stroke-width="1.2"/>'
        f'<line x1="{x1:.1f}" y1="{y-tk:.1f}" x2="{x1:.1f}" y2="{y+tk:.1f}" '
        f'stroke="{col}" stroke-width="1.2"/>'
        f'<line x1="{x2:.1f}" y1="{y-tk:.1f}" x2="{x2:.1f}" y2="{y+tk:.1f}" '
        f'stroke="{col}" stroke-width="1.2"/>'
        f'<text x="{mx:.1f}" y="{yo:.1f}" text-anchor="middle" '
        f'font-size="10" fill="{col}" font-family="sans-serif">{lbl}</text>'
    )


def _vline(x: float, y1: float, y2: float, lbl: str,
           right: bool = True, col: str = _SD) -> str:
    tk = 5
    xo = x + 16 if right else x - 16
    my = (y1 + y2) / 2
    return (
        f'<line x1="{x:.1f}" y1="{y1:.1f}" x2="{x:.1f}" y2="{y2:.1f}" '
        f'stroke="{col}" stroke-width="1.2"/>'
        f'<line x1="{x-tk:.1f}" y1="{y1:.1f}" x2="{x+tk:.1f}" y2="{y1:.1f}" '
        f'stroke="{col}" stroke-width="1.2"/>'
        f'<line x1="{x-tk:.1f}" y1="{y2:.1f}" x2="{x+tk:.1f}" y2="{y2:.1f}" '
        f'stroke="{col}" stroke-width="1.2"/>'
        f'<text x="{xo:.1f}" y="{my:.1f}" text-anchor="middle" '
        f'font-size="10" fill="{col}" font-family="sans-serif" '
        f'transform="rotate(-90 {xo:.1f} {my:.1f})">{lbl}</text>'
    )


def _svg_knob(dv: dict) -> str:
    kd  = float(dv.get("knob_d", 30))
    kh  = float(dv.get("knob_h", 22))
    sd  = float(dv.get("shaft_d", 6.35))
    sdp = float(dv.get("shaft_depth", 15))
    sc  = min(140 / max(kd, 1), 120 / max(kh, 1))
    pw, ph = kd * sc, kh * sc
    cx, cy = 150, 105
    bx, by = cx - pw / 2, cy - ph / 2
    shw = sd * sc
    shh = min(sdp * sc, ph * 0.65)
    sx  = cx - shw / 2
    sy  = by + ph - shh
    els = [
        f'<rect x="{bx:.1f}" y="{by:.1f}" width="{pw:.1f}" height="{ph:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2.5" rx="6"/>',
        f'<rect x="{sx:.1f}" y="{sy:.1f}" width="{shw:.1f}" height="{shh:.1f}" '
        f'fill="#b0cfe8" stroke="{_SC}" stroke-width="1.5"/>',
        _hline(bx, by - 12, bx + pw, f"{kd:.1f} mm", above=True),
        _vline(bx + pw + 5, by, by + ph, f"{kh:.1f} mm", right=True),
        _hline(sx, by + ph + 18, sx + shw, f"⌀{sd:.2f}", above=False),
    ]
    return _svg_wrap("".join(els))


def _svg_box(dv: dict) -> str:
    iw   = float(dv.get("inner_w", 80))
    ih   = float(dv.get("inner_h", 40))
    wall = float(dv.get("wall", 2.5))
    sc   = min(180 / max(iw + 2 * wall, 1), 130 / max(ih + wall, 1))
    ow   = (iw + 2 * wall) * sc
    oh   = (ih + wall) * sc
    wsc  = wall * sc
    cx, cy = 150, 100
    ox, oy = cx - ow / 2, cy - oh / 2
    els = [
        f'<rect x="{ox:.1f}" y="{oy:.1f}" width="{ow:.1f}" height="{oh:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2"/>',
        f'<rect x="{ox+wsc:.1f}" y="{oy+wsc:.1f}" '
        f'width="{iw*sc:.1f}" height="{ih*sc:.1f}" '
        f'fill="#f0f8ff" stroke="{_SC}" stroke-width="1" stroke-dasharray="4 2"/>',
        _hline(ox + wsc, oy - 14, ox + wsc + iw * sc, f"{iw:.0f} mm inner", above=True),
        _hline(ox, oy + oh + 18, ox + ow, f"{iw + 2*wall:.0f} mm outer", above=False),
        _vline(ox + ow + 5, oy, oy + oh, f"{ih + wall:.0f} mm", right=True),
        _vline(ox - 5, oy + wsc, oy + oh, f"{ih:.0f} mm", right=False),
    ]
    return _svg_wrap("".join(els))


def _svg_end_cap(dv: dict) -> str:
    pd  = float(dv.get("plug_d", 24))
    ph  = float(dv.get("plug_h", 15))
    fd  = float(dv.get("flange_d", 29))
    fh  = float(dv.get("flange_h", 3))
    sc  = min(150 / max(fd, 1), 110 / max(ph + fh, 1))
    pcx = 150
    by  = 160
    pw_half = pd / 2 * sc
    fw_half = fd / 2 * sc
    phsc    = ph * sc
    fhsc    = fh * sc
    els = [
        f'<rect x="{pcx-fw_half:.1f}" y="{by-fhsc:.1f}" '
        f'width="{fw_half*2:.1f}" height="{fhsc:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2"/>',
        f'<rect x="{pcx-pw_half:.1f}" y="{by-fhsc-phsc:.1f}" '
        f'width="{pw_half*2:.1f}" height="{phsc:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2"/>',
        f'<line x1="{pcx:.1f}" y1="{by-fhsc-phsc-5:.1f}" '
        f'x2="{pcx:.1f}" y2="{by+5:.1f}" '
        f'stroke="#aaa" stroke-width="1" stroke-dasharray="6 3"/>',
        _hline(pcx - pw_half, by - fhsc - phsc - 12,
               pcx + pw_half, f"⌀{pd:.1f} plug", above=True),
        _hline(pcx - fw_half, by + 16, pcx + fw_half, f"⌀{fd:.1f} flange", above=False),
        _vline(pcx + fw_half + 5, by - fhsc - phsc, by, f"{ph+fh:.1f} mm", right=True),
    ]
    return _svg_wrap("".join(els))


def _svg_l_bracket(dv: dict) -> str:
    a1  = float(dv.get("arm1_len", 50))
    a2  = float(dv.get("arm2_len", 50))
    t   = float(dv.get("thickness", 4.5))
    sc  = min(110 / max(a1, 1), 140 / max(a2, 1))
    a1s, a2s, ts = a1 * sc, a2 * sc, max(t * sc, 5)
    ox, oy = 80, 155
    els = [
        f'<rect x="{ox:.1f}" y="{oy-a1s:.1f}" width="{ts:.1f}" height="{a1s:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2"/>',
        f'<rect x="{ox:.1f}" y="{oy-ts:.1f}" width="{a2s:.1f}" height="{ts:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2"/>',
        _vline(ox - 5, oy - a1s, oy, f"{a1:.0f} mm", right=False),
        _hline(ox, oy + 16, ox + a2s, f"{a2:.0f} mm", above=False),
        f'<text x="{ox+a2s+12:.1f}" y="{oy-ts/2+4:.1f}" font-size="10" '
        f'fill="{_SD}" font-family="sans-serif">t={t:.1f}</text>',
    ]
    return _svg_wrap("".join(els))


def _svg_cable_clip(dv: dict) -> str:
    cd  = float(dv.get("cable_d", 6))
    wt  = float(dv.get("wall_t", 2.5))
    bh  = float(dv.get("base_h", 8))
    r_out = cd / 2 + wt
    sc  = min(80 / max(r_out * 2, 1), 80 / max(bh + r_out * 2, 1))
    cx, cy = 150, 100
    ros = r_out * sc
    ris = (cd / 2) * sc
    bhs = bh * sc
    els = [
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{ros:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2"/>',
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{ris:.1f}" '
        f'fill="#f0f8ff" stroke="{_SC}" stroke-width="1.2"/>',
        f'<rect x="{cx-ros:.1f}" y="{cy+ros:.1f}" '
        f'width="{ros*2:.1f}" height="{bhs:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2"/>',
        _hline(cx - ris, cy - ros - 12, cx + ris, f"⌀{cd:.1f} cable", above=True),
        _hline(cx - ros, cy + ros + bhs + 14, cx + ros,
               f"⌀{r_out*2:.1f} OD", above=False),
        _vline(cx + ros + 5, cy + ros, cy + ros + bhs, f"{bh:.1f} mm", right=True),
    ]
    return _svg_wrap("".join(els))


def _svg_wall_hook(dv: dict) -> str:
    pht = float(dv.get("plate_h", 60))
    pt  = float(dv.get("plate_t", 5))
    hr  = float(dv.get("hook_reach", 40))
    ht  = float(dv.get("hook_t", 6))
    tip = float(dv.get("tip_h", 20))
    sc  = min(60 / max(hr + pt, 1), 120 / max(pht, 1))
    ox, oy = 65, 30
    ps  = max(pt * sc, 5)
    hs  = pht * sc
    hrs = hr * sc
    hts = max(ht * sc, 5)
    tips = tip * sc
    arm_y = oy + hs * 0.4
    els = [
        f'<rect x="{ox:.1f}" y="{oy:.1f}" width="{ps:.1f}" height="{hs:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2"/>',
        f'<rect x="{ox:.1f}" y="{arm_y:.1f}" width="{hrs:.1f}" height="{hts:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2"/>',
        f'<rect x="{ox+hrs-hts:.1f}" y="{arm_y-tips:.1f}" '
        f'width="{hts:.1f}" height="{tips:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2"/>',
        _vline(ox - 5, oy, oy + hs, f"{pht:.0f} mm", right=False),
        _hline(ox + ps, arm_y + hts + 14, ox + hrs, f"{hr:.0f} mm", above=False),
        _vline(ox + hrs + 5, arm_y - tips, arm_y, f"{tip:.0f} mm", right=True),
    ]
    return _svg_wrap("".join(els))


def _svg_spacer(dv: dict) -> str:
    od  = float(dv.get("outer_d", 20))
    iid = float(dv.get("inner_d", 5))
    h   = float(dv.get("height", 5))
    sc  = min(140 / max(od, 1), 80 / max(h * 4, 1))
    cx  = 150
    ty  = 65
    ods = od * sc
    ids = iid * sc
    hs  = h * sc
    els = [
        f'<rect x="{cx-ods/2:.1f}" y="{ty:.1f}" width="{ods:.1f}" height="{hs:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2"/>',
        f'<rect x="{cx-ids/2:.1f}" y="{ty-1:.1f}" '
        f'width="{ids:.1f}" height="{hs+2:.1f}" '
        f'fill="white" stroke="{_SC}" stroke-width="1.2"/>',
        f'<line x1="{cx:.1f}" y1="{ty-8:.1f}" x2="{cx:.1f}" y2="{ty+hs+8:.1f}" '
        f'stroke="#aaa" stroke-width="1" stroke-dasharray="4 2"/>',
        _hline(cx - ods/2, ty - 14, cx + ods/2, f"⌀{od:.1f} OD", above=True),
        _hline(cx - ids/2, ty + hs + 16, cx + ids/2, f"⌀{iid:.1f} bore", above=False),
        _vline(cx + ods/2 + 5, ty, ty + hs, f"{h:.1f} mm", right=True),
    ]
    return _svg_wrap("".join(els))


def _svg_drawer_pull(dv: dict) -> str:
    sp  = float(dv.get("span", 96))
    gl  = float(dv.get("grip_len", 110))
    gw  = float(dv.get("grip_w", 18))
    gh  = float(dv.get("grip_h", 25))
    sc  = min(220 / max(gl, 1), 90 / max(gh + gw, 1))
    cls = gl * sc
    sps = sp * sc
    ghs = gh * sc
    gws = gw * sc
    cx  = 160
    by  = 145
    off = (gl - sp) / 2 * sc
    lx  = cx - cls / 2
    els = [
        f'<rect x="{lx:.1f}" y="{by-ghs:.1f}" width="{gws:.1f}" height="{ghs:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2" rx="3"/>',
        f'<rect x="{lx+cls-gws:.1f}" y="{by-ghs:.1f}" '
        f'width="{gws:.1f}" height="{ghs:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2" rx="3"/>',
        f'<rect x="{lx:.1f}" y="{by-ghs-gws*0.4:.1f}" '
        f'width="{cls:.1f}" height="{gws*0.4:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2" rx="4"/>',
        _hline(lx + off, by + 14, lx + off + sps, f"{sp:.0f} mm span", above=False),
        _hline(lx, by - ghs - 16, lx + cls, f"{gl:.0f} mm total", above=True),
        _vline(lx - 5, by - ghs, by, f"{gh:.0f} mm", right=False),
    ]
    return _svg_wrap("".join(els))


def _svg_button_cap(dv: dict) -> str:
    cd  = float(dv.get("cap_d", 14))
    ch  = float(dv.get("cap_h", 7))
    sh  = float(dv.get("skirt_h", 3))
    sw  = float(dv.get("stem_w", 4))
    sdp = float(dv.get("stem_h", 5))
    sc  = min(140 / max(cd, 1), 100 / max(ch + sh, 1))
    cds = cd * sc
    chs = ch * sc
    shs = sh * sc
    sws = sw * sc
    sdps = min(sdp * sc, chs * 0.7)
    cx  = 150
    ty  = 45
    els = [
        f'<rect x="{cx-cds/2-2:.1f}" y="{ty:.1f}" '
        f'width="{cds+4:.1f}" height="{shs:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2"/>',
        f'<rect x="{cx-cds/2:.1f}" y="{ty+shs:.1f}" '
        f'width="{cds:.1f}" height="{chs:.1f}" '
        f'fill="{_SF}" stroke="{_SC}" stroke-width="2" rx="6"/>',
        f'<rect x="{cx-sws/2:.1f}" y="{ty+shs:.1f}" '
        f'width="{sws:.1f}" height="{sdps:.1f}" '
        f'fill="white" stroke="{_SC}" stroke-width="1.2" stroke-dasharray="3 2"/>',
        _hline(cx - cds/2, ty + shs + chs + 16, cx + cds/2, f"⌀{cd:.1f} mm", above=False),
        _vline(cx + cds/2 + 5, ty, ty + shs + chs, f"{ch+sh:.1f} mm", right=True),
        _hline(cx - sws/2, ty - 12, cx + sws/2, f"{sw:.1f} stem", above=True),
    ]
    return _svg_wrap("".join(els))


_SVG_DISPATCH: dict = {
    "knob_d_shaft":     _svg_knob,
    "knob_round_shaft": _svg_knob,
    "knob_pointer":     _svg_knob,
    "box_open":         _svg_box,
    "box_with_lid":     _svg_box,
    "end_cap":          _svg_end_cap,
    "l_bracket":        _svg_l_bracket,
    "cable_clip":       _svg_cable_clip,
    "wall_hook":        _svg_wall_hook,
    "spacer":           _svg_spacer,
    "drawer_pull":      _svg_drawer_pull,
    "button_cap":       _svg_button_cap,
}


def part_svg(template_id: str, dim_values: dict) -> str:
    fn = _SVG_DISPATCH.get(template_id)
    if fn is None:
        return _svg_wrap(
            f'<text x="160" y="100" text-anchor="middle" '
            f'font-size="14" fill="{_ST}">No diagram available</text>'
        )
    return fn(dim_values)


# ── Caliper measurement tips per template ─────────────────────────────────────

_CALIPER_TIPS: dict[str, list[str]] = {
    "knob_d_shaft": [
        "**Shaft diameter:** Use inside jaws around the shaft.",
        "**Flat depth:** Measure full shaft diameter, then measure from flat to opposite edge. flat_cut = (diameter/2) − that reading.",
        "**Shaft depth:** Push depth probe into the bore.",
        "**Knob diameter:** Outside jaws on the original knob or use a ruler.",
    ],
    "knob_round_shaft": [
        "**Shaft diameter:** Inside jaws around the shaft.",
        "**Knob diameter:** Outside jaws on widest part of old knob.",
        "**Set-screw hole:** Usually M3 thread → 2.5 mm drill size.",
    ],
    "knob_pointer": [
        "**Shaft diameter:** Inside jaws on the D-shaft.",
        "**Knob diameter:** Outside jaws on original knob.",
        "**Pointer width:** Decide — 2–4 mm is typical.",
    ],
    "box_open": [
        "**Inner width/depth:** Measure the contents that must fit inside.",
        "**Inner height:** Measure from base to intended top edge.",
        "**Wall thickness:** 2–3 mm for light objects, 3–5 mm for heavier loads.",
    ],
    "box_with_lid": [
        "**Inner dimensions:** Measure the contents to contain.",
        "**Lid height:** The rim that overlaps the box — typically 6–10 mm.",
        "**Press-fit gap:** 0.2 mm = snug, 0.3 mm = standard, 0.4 mm = easy.",
    ],
    "end_cap": [
        "**Plug diameter:** Measure INSIDE the tube with inside jaws.",
        "**Flange diameter:** Should be slightly larger than tube outer diameter.",
        "**Plug depth:** Use depth probe inside the tube.",
    ],
    "l_bracket": [
        "**Arm lengths:** Span from corner to mounting hole centre, plus margin.",
        "**Thickness:** 3–5 mm light loads, 6–8 mm heavy shelves.",
        "**Hole diameter:** Measure screw shank, not thread diameter.",
    ],
    "cable_clip": [
        "**Cable diameter:** Wrap paper around cable, mark overlap, measure strip ÷ 3.14.",
        "**Clip width:** How far along cable the clip grips — 15–25 mm typical.",
        "**Gap %:** 60% = hard snap, 70% = normal, 80% = easy-open.",
    ],
    "wall_hook": [
        "**Plate height:** Measure wall section available for mounting.",
        "**Hook reach:** Distance from wall to item + 10 mm clearance.",
        "**Tip height:** Must exceed the item height to prevent it falling off.",
        "**Screw hole:** Match your wall plugs (4 mm for most standard plugs).",
    ],
    "spacer": [
        "**Outer diameter:** Measure the recess or step that accepts the spacer.",
        "**Bore diameter:** Measure the bolt or shaft the spacer fits onto.",
        "**Height:** Use depth probe to measure the gap to fill.",
    ],
    "drawer_pull": [
        "**Span (c-c):** Measure centre-to-centre between the two screw holes.",
        "**Grip length:** Usually span + 10–20 mm for the end caps.",
        "**Grip height:** How far the handle stands off the drawer face.",
    ],
    "button_cap": [
        "**Cap diameter:** Measure the recess or housing where the button lives.",
        "**Stem socket:** Measure button stem — square PCB stems common.",
        "**Stem depth:** How deep the socket grips for secure clicking.",
    ],
}

_CALIPER_TIPS_DEFAULT = [
    "Use **outside jaws** for external measurements.",
    "Use **inside jaws** for holes and bores.",
    "Use the **depth probe** for pocket and slot depths.",
    "Always measure twice and print a test piece first.",
]


def _caliper_tips_html(template_id: str) -> str:
    tips = _CALIPER_TIPS.get(template_id, _CALIPER_TIPS_DEFAULT)
    items = "".join(
        f"<li style='margin-bottom:6px'>{t}</li>" for t in tips
    )
    return (
        f"<ul style='padding-left:18px;margin:0;font-size:14px'>"
        f"{items}</ul>"
    )

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — VALIDATE & REFINE  (wizard_step == "results")
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.wizard_step == "results":

    res = st.session_state.identify_result
    if not res:
        _go("identify")

    tmpl = tmpl_get(res.get("template_id", ""))
    if not tmpl:
        tmpl = INTERNAL_TEMPLATES[0]

    # ── AI Interpretation Card ────────────────────────────────────────────────
    st.markdown("### 🔍 What we found")

    c_info, c_badge = st.columns([2, 1])
    with c_info:
        # Part identification (vision AI)
        if res.get("part_name"):
            pmodel = f" — *{res['part_model']}*" if res.get("part_model") else ""
            st.markdown(f"**Part:** {res['part_name']}{pmodel}")
        elif res.get("caption"):
            st.markdown(f"**Photo:** {res['caption']}")

        # Part description (2-3 sentences about what it is and does)
        part_desc = res.get("part_description", "")
        if part_desc:
            st.markdown(part_desc)

        desc = res.get("project_description") or tmpl["description"]
        st.markdown(f"**Plan:** {desc}")
        st.markdown(f"**Template:** {tmpl['name']}")
        st.caption(f"Method: {res.get('method', 'keyword')}")
        if res.get("warning"):
            st.warning(res["warning"])

        # Search terms chips (vision AI only)
        terms = res.get("search_terms") or []
        if terms:
            chips = "".join(
                f'<span style="display:inline-block;background:#e3f2fd;'
                f'border:1px solid #90caf9;border-radius:12px;'
                f'padding:2px 10px;margin:2px;font-size:11px;color:#1565c0">'
                f'{t}</span>'
                for t in terms
            )
            st.markdown(
                f'<div style="margin-top:6px"><span style="font-size:12px;'
                f'color:#888">🔎 Search: </span>{chips}</div>',
                unsafe_allow_html=True,
            )

    with c_badge:
        is_vision  = "vision" in res.get("method", "")
        badge_bg   = "#e8f4f8" if not is_vision else "#e8f5e9"
        badge_ico  = "🖨️" if not is_vision else "🤖"
        vision_tag = (
            '<div style="font-size:10px;color:#388e3c;margin-top:4px">AI Vision ✨</div>'
            if is_vision else ""
        )
        st.markdown(
            f'<div style="background:{badge_bg};border-radius:10px;padding:14px;'
            f'text-align:center;margin-top:4px">'
            f'<div style="font-size:32px">{badge_ico}</div>'
            f'<div style="font-weight:700;font-size:13px;margin-top:4px">'
            f'{tmpl["category"]}</div>'
            f'{vision_tag}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── About this device ─────────────────────────────────────────────────────
    device_desc = res.get("device_description", "")
    if device_desc:
        st.markdown(
            f'<div style="background:#1a2a3a;border-left:3px solid #4a7fa5;'
            f'border-radius:0 8px 8px 0;padding:10px 14px;margin:8px 0 4px 0;'
            f'font-size:0.88rem;color:#b0c4d8">'
            f'<span style="font-weight:700;color:#7eb8d4">About this device</span>'
            f'<br>{device_desc}</div>',
            unsafe_allow_html=True,
        )

    # ── Reference images ──────────────────────────────────────────────────────
    _img_query = res.get("part_name") or res.get("template_name") or ""
    if _img_query:
        _img_urls = _fetch_part_images(_img_query)
        if _img_urls:
            st.caption("📷 Reference images")
            _img_cols = st.columns(len(_img_urls))
            for _col, _url in zip(_img_cols, _img_urls):
                try:
                    _r = requests.get(_url, timeout=5)
                    if _r.ok and _r.headers.get("content-type", "").startswith("image"):
                        _col.image(_r.content, width=150)
                except Exception:
                    pass

    st.markdown("---")

    # ── Buy vs. Print comparison ──────────────────────────────────────────────
    mr = st.session_state.get("market_result")
    if mr:
        part_label      = res.get("template_name") or tmpl["name"]
        price_display   = mr["prices"][0] if mr["prices"] else "Search online"
        pw              = mr["print_weight"]
        pc              = mr["print_cost"]
        vibe_msg        = _vibe_message(mr["prices"], pc)
        links_html      = " &nbsp;·&nbsp; ".join(
            f'<a href="{lk["url"]}" target="_blank" '
            f'style="color:#1565c0;font-size:11px">{lk["site"]}</a>'
            for lk in mr["buy_links"]
        )

        st.markdown(
            f"""
<div style="background:linear-gradient(135deg,#fffde7,#fff8e1);
     border:2px solid #f9a825;border-radius:14px;padding:16px;margin:4px 0 12px 0">
  <div style="font-size:15px;font-weight:800;margin-bottom:10px">
    🛒 Buy vs. 🖨️ Print
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px">
    <div style="background:#fff;border-radius:10px;padding:12px;
                border:1px solid #f9a825;text-align:center">
      <div style="font-size:10px;color:#999;letter-spacing:1px">🛒 ORIGINAL PART</div>
      <div style="font-weight:700;font-size:13px;margin:4px 0">{part_label}</div>
      <div style="font-size:22px;font-weight:900;color:#c62828">{price_display}</div>
      <div style="font-size:10px;color:#888;margin-top:2px">+ shipping &amp; wait time</div>
      <div style="margin-top:8px">{links_html}</div>
    </div>
    <div style="background:#e8f5e9;border-radius:10px;padding:12px;
                border:1px solid #66bb6a;text-align:center">
      <div style="font-size:10px;color:#388e3c;letter-spacing:1px">🖨️ PRINT IT NOW</div>
      <div style="font-weight:700;font-size:13px;margin:4px 0">Custom 3D Print</div>
      <div style="font-size:22px;font-weight:900;color:#2e7d32">{pc}</div>
      <div style="font-size:10px;color:#555;margin-top:2px">{pw} filament · ~1 hr print</div>
    </div>
  </div>
  <div style="background:#fffde7;border-radius:8px;padding:10px;
              font-size:13px;color:#4e342e;border:1px solid #ffe082">
    💡 <strong>The Vibe:</strong> {vibe_msg}
  </div>
</div>""",
            unsafe_allow_html=True,
        )

        # Decision row
        d_print, d_buy, d_ai = st.columns(3)
        with d_print:
            if st.button("🖨️ Print it — let's go!",
                         use_container_width=True, type="primary"):
                st.session_state.selected_template = tmpl
                st.session_state.show_buy_links    = False
                _go("dimensions")
        with d_buy:
            if st.button("🛒 I'll buy the original",
                         use_container_width=True):
                st.session_state.show_buy_links    = True
                st.session_state.reanalyse_triggered = False
                st.rerun()
        with d_ai:
            if st.button("🤖 Reanalyse with AI",
                         use_container_width=True,
                         help="Get a deeper blueprint using Claude, GPT-4o, or Gemini"):
                st.session_state.show_buy_links      = False
                st.session_state.reanalyse_triggered = True
                st.rerun()

        # ── Reanalyse panel ───────────────────────────────────────────────────
        if st.session_state.get("reanalyse_triggered"):
            _prov = st.session_state.ai_provider
            _key  = st.session_state.api_key
            if _prov not in ("claude", "openai", "gemini") or not _key:
                st.warning(
                    "To use this feature, expand **⚙️ AI Settings** above "
                    "and add a Claude, GPT-4o, or free Gemini API key."
                )
                if st.button("⚙️ Go to AI Settings", key="_go_ai_settings"):
                    st.session_state.reanalyse_triggered = False
                    _go("identify")
            else:
                with st.spinner("🤖 Running deep AI analysis — this may take up to 30 seconds…"):
                    _new_result = analyze_input(
                        image_bytes = st.session_state.image_bytes,
                        description = st.session_state.vibe_description,
                        hf_token    = _key,
                        ai_provider = _prov,
                    )
                st.session_state.identify_result   = _new_result
                st.session_state.selected_template = tmpl_get(_new_result["template_id"])
                st.session_state.dim_values        = _new_result["suggested_dims"]
                st.session_state.reanalyse_triggered = False
                st.session_state.enhanced_svg      = ""
                st.rerun()

        if st.session_state.get("show_buy_links"):
            st.markdown("#### 🛒 Search for the original part")

            # ── Editable search query ─────────────────────────────────────────
            _default_q = (
                res.get("part_name")
                or res.get("template_name")
                or tmpl["name"]
            )
            if not st.session_state.buy_search_query:
                st.session_state.buy_search_query = _default_q

            _search_q = st.text_input(
                "Refine your search:",
                value=st.session_state.buy_search_query,
                key="_buy_search_input",
            )
            st.session_state.buy_search_query = _search_q
            _q_enc = urllib.parse.quote_plus(_search_q or _default_q)

            # ── Part description card ─────────────────────────────────────────
            _part_desc = (
                res.get("part_description")
                or res.get("project_description")
                or tmpl.get("description", "")
            )
            if _part_desc:
                st.info(f"**What you're looking for:** {_part_desc}")

            # ── Inline image preview ──────────────────────────────────────────
            _preview_urls = _fetch_part_images(_search_q or _default_q, max_images=1)
            if _preview_urls:
                try:
                    _ir = requests.get(_preview_urls[0], timeout=5)
                    if _ir.ok and _ir.headers.get("content-type", "").startswith("image"):
                        _, _ic, _ = st.columns([1, 2, 1])
                        _ic.image(_ir.content, caption=_search_q or _default_q,
                                  use_column_width=True)
                except Exception:
                    pass

            # ── Retailer links as styled buttons ─────────────────────────────
            _SITE_META = {
                "Amazon":        ("📦", f"https://www.amazon.com/s?k={_q_enc}"),
                "eBay":          ("🛒", f"https://www.ebay.com/sch/i.html?_nkw={_q_enc}"),
                "RepairClinic":  ("🔧", f"https://www.repairclinic.com/Search?q={_q_enc}"),
                "ApplianceParts":("⚙️", f"https://www.appliancepartspros.com/search?q={_q_enc}"),
            }
            _btn_cols = st.columns(len(_SITE_META))
            for _col, (site, (icon, url)) in zip(_btn_cols, _SITE_META.items()):
                _col.link_button(f"{icon} Search {site}", url,
                                 use_container_width=True)

            if mr.get("abstract"):
                with st.expander("ℹ️ What we found online"):
                    st.write(mr["abstract"])

            st.caption(
                "Changed your mind? Use the **🖨️ Print it** button above "
                "or scroll down to continue with the template."
            )

        st.markdown("---")

        if mr.get("error"):
            st.caption(f"ℹ️ {mr['error']}")

    # ── Initialise dim_values from template defaults + AI suggestions ─────────
    if not st.session_state.dim_values:
        suggested = res.get("suggested_dims", {})
        st.session_state.dim_values = {}
        for dim in tmpl["dims"]:
            raw = suggested.get(dim["id"])
            st.session_state.dim_values[dim["id"]] = (
                str(raw) if raw is not None else str(dim["default"])
            )

    # ── Measurement diagram ───────────────────────────────────────────────────
    st.markdown("#### 📐 Measurement diagram")

    # Run AI enhancement if triggered
    if st.session_state.get("enhance_diagram_triggered"):
        _eprov = st.session_state.ai_provider
        _ekey  = st.session_state.api_key
        if _eprov not in ("claude", "openai", "gemini") or not _ekey:
            st.warning(
                "To enhance the diagram, expand **⚙️ AI Settings** above "
                "and add a Claude, GPT-4o, or free Gemini API key."
            )
            st.session_state.enhance_diagram_triggered = False
        else:
            with st.spinner("✨ Generating enhanced blueprint…"):
                _esvg = _enhance_diagram_with_ai(
                    part_name        = res.get("part_name", ""),
                    part_description = res.get("part_description", "") or res.get("project_description", ""),
                    template_name    = tmpl["name"],
                    dim_values       = st.session_state.dim_values,
                    provider         = _eprov,
                    api_key          = _ekey,
                )
            st.session_state.enhanced_svg = _esvg
            st.session_state.enhance_diagram_triggered = False
            st.rerun()

    # Display: prefer enhanced → AI vision → template fallback
    _display_svg = (
        st.session_state.get("enhanced_svg")
        or res.get("ai_svg", "")
    )
    if _display_svg and _display_svg.strip().startswith("<svg"):
        _caption = (
            "✨ Enhanced blueprint generated by AI."
            if st.session_state.get("enhanced_svg")
            else "Blueprint generated by AI vision analysis."
        )
        st.markdown(
            f'<div style="text-align:center;margin:8px 0;'
            f'border-radius:10px;overflow:hidden">{_display_svg}</div>',
            unsafe_allow_html=True,
        )
        st.caption(_caption)
    else:
        svg_html = part_svg(tmpl["id"], st.session_state.dim_values)
        st.markdown(
            f'<div style="text-align:center;margin:8px 0">{svg_html}</div>',
            unsafe_allow_html=True,
        )

    # Enhance button
    _enh_col, _ = st.columns([1, 2])
    with _enh_col:
        if st.button("✨ Enhance diagram with AI", use_container_width=True,
                     help="Generate a more detailed annotated blueprint using AI"):
            st.session_state.enhance_diagram_triggered = True
            st.rerun()

    # ── Confirmation buttons ──────────────────────────────────────────────────
    st.markdown("**Does this look right?**")
    btn_yes, btn_no = st.columns(2)
    with btn_yes:
        if st.button("✅ Yes — looks good!", use_container_width=True, type="primary"):
            st.session_state.selected_template = tmpl
            _go("dimensions")
    with btn_no:
        if st.button("✏️ No — let me adjust", use_container_width=True):
            st.session_state.show_refinement = True
            st.rerun()

    # ── Refinement panel ─────────────────────────────────────────────────────
    if st.session_state.show_refinement:

        st.markdown("---")
        st.markdown("#### ✏️ Adjust measurements")

        dims = tmpl["dims"]
        updated_dims: dict[str, str] = {}
        pairs = [dims[i: i + 2] for i in range(0, len(dims), 2)]
        for pair in pairs:
            cols = st.columns(len(pair))
            for col, dim in zip(cols, pair):
                with col:
                    current = float(
                        st.session_state.dim_values.get(dim["id"], dim["default"])
                    )
                    val = st.number_input(
                        dim["question"],
                        value=current,
                        step=0.5 if dim["unit"] == "mm" else 1.0,
                        format="%.1f" if dim["unit"] in ("mm", "") else "%.0f",
                        key=f"dim_{dim['id']}",
                    )
                    updated_dims[dim["id"]] = str(val)

        # Live-updating diagram
        st.markdown("**Live preview:**")
        live_svg = part_svg(tmpl["id"], updated_dims)
        st.markdown(
            f'<div style="text-align:center;margin:8px 0">{live_svg}</div>',
            unsafe_allow_html=True,
        )

        # Caliper guide
        with st.expander("📏 How to measure — Caliper guide"):
            st.markdown(_caliper_tips_html(tmpl["id"]), unsafe_allow_html=True)
            st.markdown(
                "**No caliper?** A ruler works for external dims; "
                "wrap paper around cylinders to measure diameter."
            )

        # Re-analyse
        st.markdown("---")
        re_desc = st.text_area(
            "Refine your description and re-analyse:",
            value=st.session_state.vibe_description,
            key="re_analyse_desc",
            height=80,
        )
        if st.button("🔍 Re-analyse with updated description"):
            st.session_state.vibe_description = re_desc
            with st.spinner("⏳ Re-analysing your part — this may take a moment…"):
                st.session_state.identify_result = analyze_input(
                    st.session_state.image_bytes,
                    re_desc,
                    hf_token=st.session_state.api_key,
                    ai_provider=st.session_state.ai_provider,
                )
            st.session_state.dim_values = {}
            st.session_state.show_refinement = False
            st.rerun()

        st.markdown("---")
        if st.button("✅ Finalize Measurements",
                     use_container_width=True, type="primary"):
            st.session_state.dim_values = updated_dims
            st.session_state.selected_template = tmpl
            st.session_state.show_refinement = False
            _go("dimensions")

    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — FINALIZE & EXPORT  (wizard_step == "dimensions")
# ══════════════════════════════════════════════════════════════════════════════

# ── Tool-detection helpers ────────────────────────────────────────────────────

def _find_openscad() -> str | None:
    """Return path to OpenSCAD executable, or None if not found."""
    if p := shutil.which("openscad"):
        return p
    candidates = [
        r"C:\Program Files\OpenSCAD\openscad.exe",
        r"C:\Program Files (x86)\OpenSCAD\openscad.exe",
        "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
        "/usr/bin/openscad",
        "/usr/local/bin/openscad",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def _find_slicer() -> tuple[str, str] | None:
    """Return (slicer_name, path) for PrusaSlicer or Cura, or None."""
    prusa_candidates = [
        shutil.which("prusa-slicer-console"),
        shutil.which("prusa-slicer"),
        shutil.which("PrusaSlicer"),
        r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe",
        r"C:\Program Files\PrusaSlicer\prusa-slicer-console.exe",
        "/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer",
        "/usr/bin/prusa-slicer",
    ]
    for p in prusa_candidates:
        if p and Path(p).exists():
            return ("PrusaSlicer", p)
    cura_candidates = [
        shutil.which("CuraEngine"),
        r"C:\Program Files\Ultimaker Cura\CuraEngine.exe",
        r"C:\Program Files\UltiMaker Cura\CuraEngine.exe",
        "/usr/bin/CuraEngine",
    ]
    for p in cura_candidates:
        if p and Path(p).exists():
            return ("CuraEngine", p)
    return None


# ── Compile / slice helpers ───────────────────────────────────────────────────

def _compile_stl(scad_code: str, openscad_path: str) -> tuple[bytes | None, str]:
    """
    Run OpenSCAD in headless mode to produce an STL.
    Returns (stl_bytes, error_message).  error_message is '' on success.
    """
    with tempfile.TemporaryDirectory() as td:
        scad_file = Path(td) / "part.scad"
        stl_file  = Path(td) / "part.stl"
        scad_file.write_text(scad_code, encoding="utf-8")
        try:
            result = subprocess.run(
                [openscad_path, "-o", str(stl_file), str(scad_file)],
                capture_output=True, text=True, timeout=120,
            )
            if stl_file.exists() and stl_file.stat().st_size > 0:
                return stl_file.read_bytes(), ""
            stderr = (result.stderr or "").strip()
            return None, stderr or "OpenSCAD produced no output — check your parameters."
        except subprocess.TimeoutExpired:
            return None, "OpenSCAD timed out (>120 s). Simplify the model or lower $fn."
        except FileNotFoundError:
            return None, f"OpenSCAD not found at: {openscad_path}"
        except Exception as exc:
            return None, str(exc)


def _slice_stl(stl_bytes: bytes, slicer_name: str,
               slicer_path: str) -> tuple[bytes | None, str]:
    """
    Slice an STL with PrusaSlicer CLI.
    Returns (gcode_bytes, error_message).
    """
    if slicer_name != "PrusaSlicer":
        return None, (
            f"{slicer_name} CLI slicing is not yet supported here. "
            "Open the STL in your slicer manually."
        )
    with tempfile.TemporaryDirectory() as td:
        stl_file   = Path(td) / "part.stl"
        gcode_file = Path(td) / "part.gcode"
        stl_file.write_bytes(stl_bytes)
        try:
            result = subprocess.run(
                [slicer_path, "--export-gcode",
                 "--output", str(gcode_file), str(stl_file)],
                capture_output=True, text=True, timeout=300,
            )
            if gcode_file.exists() and gcode_file.stat().st_size > 0:
                return gcode_file.read_bytes(), ""
            stderr = (result.stderr or "").strip()
            return None, stderr or "PrusaSlicer produced no G-code output."
        except subprocess.TimeoutExpired:
            return None, "PrusaSlicer timed out. Try slicing manually."
        except Exception as exc:
            return None, str(exc)


# ── Project save / load ───────────────────────────────────────────────────────

def _project_to_json() -> str:
    """Serialise current project to a JSON string."""
    img_b64 = ""
    if st.session_state.image_bytes:
        img_b64 = base64.b64encode(st.session_state.image_bytes).decode()
    tmpl = st.session_state.selected_template or {}
    res  = st.session_state.identify_result  or {}
    return json.dumps({
        "vtp_version":         "1.0",
        "saved_at":            time.strftime("%Y-%m-%dT%H:%M:%S"),
        "template_id":         tmpl.get("id", ""),
        "vibe_description":    st.session_state.vibe_description,
        "project_description": res.get("project_description", ""),
        "dim_values":          st.session_state.dim_values,
        "image_b64":           img_b64,
        "image_media_type":    st.session_state.image_media_type,
    }, indent=2)


def _load_project_json(raw: bytes) -> str:
    """
    Populate st.session_state from a .vtp.json file.
    Returns an error string, or '' on success.
    """
    try:
        data = json.loads(raw)
    except Exception:
        return "File is not valid JSON."
    if data.get("vtp_version") != "1.0":
        return "Unrecognised project format (expected vtp_version 1.0)."
    tid  = data.get("template_id", "")
    tmpl = tmpl_get(tid)
    if not tmpl:
        return f"Template '{tid}' not found in this version of the app."

    st.session_state.selected_template  = tmpl
    st.session_state.vibe_description   = data.get("vibe_description", "")
    st.session_state.dim_values         = data.get("dim_values", {})
    st.session_state.image_media_type   = data.get("image_media_type", "image/jpeg")
    img_b64 = data.get("image_b64", "")
    if img_b64:
        try:
            st.session_state.image_bytes = base64.b64decode(img_b64)
        except Exception:
            st.session_state.image_bytes = None
    else:
        st.session_state.image_bytes = None

    # Reconstruct a minimal identify_result so Step 2 can display context
    st.session_state.identify_result = {
        "project_description": data.get("project_description", ""),
        "template_id":         tid,
        "template_name":       tmpl["name"],
        "suggested_dims":      data.get("dim_values", {}),
        "method":              "loaded from file",
        "warning":             "",
        "caption":             "",
    }
    st.session_state.show_refinement = False
    return ""


# ── Wizard Step 3 ─────────────────────────────────────────────────────────────

if st.session_state.wizard_step == "dimensions":

    tmpl = st.session_state.selected_template
    if not tmpl:
        _go("identify")

    dim_values = st.session_state.dim_values or {
        d["id"]: str(d["default"]) for d in tmpl["dims"]
    }

    scad_code = tmpl_generate_scad(tmpl, dim_values)
    st.session_state.scad_code = scad_code
    filename_base = tmpl["id"]

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown(f"### ✅ Ready to print: {tmpl['name']}")
    st.caption("Review the code, export, and save your project.")

    # ── OpenSCAD code block ───────────────────────────────────────────────────
    with st.expander("📄 OpenSCAD code", expanded=True):
        st.code(scad_code, language="cpp")

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown("#### 📦 Export")
    col_scad, col_stl = st.columns(2)

    with col_scad:
        st.download_button(
            "⬇️ Download .SCAD",
            data=scad_code.encode("utf-8"),
            file_name=f"{filename_base}.scad",
            mime="text/plain",
            use_container_width=True,
            type="primary",
        )

    with col_stl:
        openscad_path = _find_openscad()
        if openscad_path:
            if st.button("⚙️ Compile to STL", use_container_width=True):
                with st.spinner("Compiling with OpenSCAD — this may take a moment…"):
                    stl_bytes, err = _compile_stl(scad_code, openscad_path)
                if err:
                    st.error(f"Compile error: {err}")
                else:
                    st.session_state["_stl_bytes"] = stl_bytes
                    st.session_state["_gcode_bytes"] = None
                    st.rerun()

            if st.session_state.get("_stl_bytes"):
                st.download_button(
                    "⬇️ Download STL",
                    data=st.session_state["_stl_bytes"],
                    file_name=f"{filename_base}.stl",
                    mime="model/stl",
                    use_container_width=True,
                )
        else:
            st.info(
                "**OpenSCAD not installed.**\n\n"
                "1. Download from [openscad.org](https://openscad.org/downloads.html)\n"
                "2. Open the `.scad` file above\n"
                "3. Press **F6** to render, then **File → Export → Export as STL**",
                icon="ℹ️",
            )

    # Slice section (shown below the two-column row when an STL is ready)
    if st.session_state.get("_stl_bytes"):
        slicer = _find_slicer()
        if slicer:
            slicer_name, slicer_path = slicer
            st.markdown("---")
            col_slice, col_gcode = st.columns(2)
            with col_slice:
                if st.button(
                    f"🔪 Slice with {slicer_name}",
                    use_container_width=True,
                ):
                    with st.spinner(f"Slicing with {slicer_name}…"):
                        gcode_bytes, err2 = _slice_stl(
                            st.session_state["_stl_bytes"],
                            slicer_name, slicer_path,
                        )
                    if err2:
                        st.error(f"Slice error: {err2}")
                    else:
                        st.session_state["_gcode_bytes"] = gcode_bytes
                        st.rerun()
            with col_gcode:
                if st.session_state.get("_gcode_bytes"):
                    st.download_button(
                        "⬇️ Download G-code",
                        data=st.session_state["_gcode_bytes"],
                        file_name=f"{filename_base}.gcode",
                        mime="text/plain",
                        use_container_width=True,
                        type="primary",
                    )
        else:
            st.caption(
                "No slicer found on this machine. "
                "Open the STL in PrusaSlicer, Cura, or OrcaSlicer to generate G-code."
            )

    # ── Project management ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 💾 Project")
    col_save, col_load = st.columns(2)

    with col_save:
        st.download_button(
            "💾 Save Project (.vtp.json)",
            data=_project_to_json().encode("utf-8"),
            file_name=f"{filename_base}.vtp.json",
            mime="application/json",
            use_container_width=True,
        )

    with col_load:
        uploaded = st.file_uploader(
            "Load existing project",
            type=["json"],
            key="project_uploader",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            err = _load_project_json(uploaded.read())
            if err:
                st.error(err)
            else:
                st.success("Project loaded — returning to measurement step.")
                time.sleep(0.8)
                _go("results")

    # ── Navigation ────────────────────────────────────────────────────────────
    st.markdown("---")
    col_back, col_new = st.columns(2)
    with col_back:
        if st.button("← Back to measurements", use_container_width=True):
            st.session_state["_stl_bytes"]   = None
            st.session_state["_gcode_bytes"] = None
            _go("results")
    with col_new:
        if st.button("🔄 Start New Project", use_container_width=True):
            for _k in list(st.session_state.keys()):
                del st.session_state[_k]
            st.rerun()

    st.stop()

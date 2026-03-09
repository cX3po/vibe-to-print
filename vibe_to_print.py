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
    "ai_provider":        "none",      # none | hf | claude | openai | ollama
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _go(step: str) -> None:
    st.session_state.wizard_step = step
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
    Snap. Measure. Print.<br>
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

    st.stop()

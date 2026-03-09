"""
basic_slicer.py — Pure-Python FDM slicer using numpy-stl + shapely.

Produces printable G-code without requiring PrusaSlicer or CuraEngine.
Quality is functional (perimeters + simple rectilinear infill) rather than
production-optimal — ideal for the zero-install path.

Public API:
    slice_stl(stl_path, profile, material, material_temps, output_dir)
    → (ok: bool, log: str, gcode_path: Path | None)
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np

try:
    from stl import mesh as stl_mesh          # numpy-stl
    from shapely.geometry import (
        MultiPolygon, Polygon, MultiLineString, LineString
    )
    from shapely.ops import unary_union, polygonize
    _DEPS_OK = True
except ImportError:
    _DEPS_OK = False


# ── Slicer parameters ─────────────────────────────────────────────────────────

LAYER_HEIGHT   = 0.2    # mm
LINE_WIDTH     = 0.4    # mm (nozzle diameter)
PERIMETERS     = 2      # shell count
INFILL_DENSITY = 0.20   # 20 %
TRAVEL_SPEED   = 150    # mm/s
PRINT_SPEED    = 50     # mm/s
FIRST_LAYER_SPEED = 25  # mm/s
RETRACT_MM     = 1.0    # mm retraction
RETRACT_SPEED  = 45     # mm/s


# ── Public entry point ────────────────────────────────────────────────────────

def available() -> bool:
    """Return True if numpy-stl and shapely are importable."""
    return _DEPS_OK


def slice_stl(
    stl_path: Path,
    profile: dict,
    material: str,
    material_temps: dict,
    output_dir: Path,
) -> Tuple[bool, str, Path | None]:
    """
    Slice an STL file to G-code using the built-in Python slicer.

    Returns (ok, log_text, gcode_path).
    """
    if not _DEPS_OK:
        return False, "numpy-stl or shapely not installed.", None

    log_lines: list[str] = []

    def log(msg: str) -> None:
        log_lines.append(msg)

    log(f"Basic Python slicer — {stl_path.name}")
    log(f"Layer height: {LAYER_HEIGHT} mm  |  Perimeters: {PERIMETERS}  "
        f"|  Infill: {int(INFILL_DENSITY*100)}%")

    try:
        m = stl_mesh.Mesh.from_file(str(stl_path))
    except Exception as exc:
        return False, f"Could not load STL: {exc}", None

    # ── Bounding box ──────────────────────────────────────────────────────────
    z_min = float(m.z.min())
    z_max = float(m.z.max())
    height_mm = z_max - z_min
    n_layers  = max(1, math.ceil(height_mm / LAYER_HEIGHT))
    log(f"Model height: {height_mm:.2f} mm  →  {n_layers} layers")

    temps = material_temps.get(material, {"hotend": 210, "bed": 60})
    bed_x = profile.get("bed_x", 235)
    bed_y = profile.get("bed_y", 235)

    # ── G-code header ─────────────────────────────────────────────────────────
    lines: list[str] = []
    a = lines.append

    a("; Vibe-to-Print — Basic Python Slicer")
    a(f"; Material: {material}  Hotend: {temps['hotend']}°C  Bed: {temps['bed']}°C")
    a(f"; Layer height: {LAYER_HEIGHT} mm  Perimeters: {PERIMETERS}  "
      f"Infill: {int(INFILL_DENSITY*100)}%")
    a(f"; Generated: {time.strftime('%Y-%m-%d %H:%M')}")
    a("")
    a("G21 ; mm units")
    a("G90 ; absolute positioning")
    a("M82 ; absolute extruder")
    a(f"M104 S{temps['hotend']} ; set hotend temp")
    a(f"M140 S{temps['bed']} ; set bed temp")
    a(f"M109 S{temps['hotend']} ; wait hotend")
    a(f"M190 S{temps['bed']} ; wait bed")
    a("G28 ; home all axes")
    a(f"G1 Z5 F3000")
    a(f"G1 X{bed_x/2:.2f} Y10 F6000 ; move to purge start")
    a("G1 Z0.3 F1200")
    a("G92 E0")
    a("G1 Y60 E6 F600 ; purge line")
    a("G92 E0")
    a("G1 Z2 F3000")
    a("")

    # ── Pre-compute all triangle data as numpy arrays ─────────────────────────
    # Each triangle has 3 vertices; m.vectors shape = (n_tri, 3, 3)
    verts = m.vectors  # shape (N, 3, 3) — N triangles, 3 verts, xyz

    e_pos  = 0.0   # extruder position
    retracted = False
    prev_xy: Tuple[float, float] | None = None

    def _retract() -> None:
        nonlocal e_pos, retracted
        if not retracted:
            a(f"G1 E{e_pos - RETRACT_MM:.5f} F{int(RETRACT_SPEED*60)} ; retract")
            retracted = True

    def _unretract() -> None:
        nonlocal e_pos, retracted
        if retracted:
            a(f"G1 E{e_pos:.5f} F{int(RETRACT_SPEED*60)} ; unretract")
            retracted = False

    def _travel(x: float, y: float, z: float) -> None:
        nonlocal prev_xy
        _retract()
        a(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{int(TRAVEL_SPEED*60)}")
        prev_xy = (x, y)
        _unretract()

    def _extrude_line(x0: float, y0: float, x1: float, y1: float,
                      z: float, spd: float) -> None:
        nonlocal e_pos, prev_xy
        dist = math.hypot(x1 - x0, y1 - y0)
        if dist < 1e-6:
            return
        if prev_xy != (x0, y0):
            _travel(x0, y0, z)
        # Extrusion volume: line_width × layer_height × length / (π(d/2)²)
        # Simplified: vol = LINE_WIDTH × LAYER_HEIGHT × dist
        e_vol  = LINE_WIDTH * LAYER_HEIGHT * dist
        e_pos += e_vol / (math.pi * (1.75 / 2) ** 2)  # 1.75 mm filament
        a(f"G1 X{x1:.3f} Y{y1:.3f} E{e_pos:.5f} F{int(spd*60)}")
        prev_xy = (x1, y1)

    # ── Layer loop ────────────────────────────────────────────────────────────
    for layer_idx in range(n_layers):
        z_slice = z_min + (layer_idx + 0.5) * LAYER_HEIGHT
        z_print = (layer_idx + 1) * LAYER_HEIGHT
        spd     = FIRST_LAYER_SPEED if layer_idx == 0 else PRINT_SPEED

        a(f"; Layer {layer_idx + 1}/{n_layers}  Z={z_print:.3f}")
        a(f"G1 Z{z_print:.3f} F1200")

        # ── Find cross-section at z_slice ─────────────────────────────────────
        segments = _cross_section_segments(verts, z_slice)
        if not segments:
            continue

        polys = _segments_to_polygons(segments)
        if not polys:
            continue

        for poly in polys:
            if poly.is_empty or poly.area < LINE_WIDTH ** 2:
                continue

            # ── Perimeters ────────────────────────────────────────────────────
            shells = []
            for i in range(PERIMETERS):
                offset = -(i + 0.5) * LINE_WIDTH
                shell  = poly.buffer(offset, join_style=2)
                if shell.is_empty:
                    break
                shells.append(shell)

            for shell in shells:
                coords = _polygon_coords(shell)
                if len(coords) < 2:
                    continue
                _travel(coords[0][0], coords[0][1], z_print)
                for x, y in coords[1:]:
                    _extrude_line(prev_xy[0], prev_xy[1], x, y, z_print, spd)

            # ── Rectilinear infill ─────────────────────────────────────────────
            if INFILL_DENSITY > 0 and shells:
                inner = shells[-1].buffer(-0.5 * LINE_WIDTH, join_style=2)
                if not inner.is_empty and inner.area > LINE_WIDTH ** 2:
                    spacing = LINE_WIDTH / max(INFILL_DENSITY, 0.01)
                    angle   = 45 if layer_idx % 2 == 0 else 135
                    infill  = _rectilinear_infill(inner, spacing, angle, z_print, spd,
                                                  _extrude_line, _travel, prev_xy)
                    prev_xy = infill  # returns final xy

    # ── Footer ────────────────────────────────────────────────────────────────
    _retract()
    a("")
    a(f"G1 Z{n_layers * LAYER_HEIGHT + 10:.3f} F3000 ; lift")
    a(f"G1 X0 Y{bed_y - 20:.0f} F6000 ; present print")
    a("M104 S0 ; hotend off")
    a("M140 S0 ; bed off")
    a("M84    ; motors off")
    a("; Print complete")

    gcode_path = output_dir / "vibe_model_basic.gcode"
    gcode_path.write_text("\n".join(lines), encoding="utf-8")

    log(f"G-code written: {gcode_path.name}  ({len(lines)} lines)")
    return True, "\n".join(log_lines), gcode_path


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _cross_section_segments(
    verts: np.ndarray, z: float
) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Return (p0, p1) line segments where the mesh intersects plane z."""
    segs = []
    for tri in verts:
        pts = []
        for i in range(3):
            j = (i + 1) % 3
            z0, z1 = tri[i][2], tri[j][2]
            if (z0 <= z < z1) or (z1 <= z < z0):
                t = (z - z0) / (z1 - z0)
                x = tri[i][0] + t * (tri[j][0] - tri[i][0])
                y = tri[i][1] + t * (tri[j][1] - tri[i][1])
                pts.append((x, y))
        if len(pts) == 2:
            segs.append((pts[0], pts[1]))
    return segs


def _segments_to_polygons(
    segments: List[Tuple[Tuple[float, float], Tuple[float, float]]]
) -> List[Polygon]:
    """Convert line segments (from STL cross-section) to closed Shapely polygons."""
    lines = MultiLineString([list(s) for s in segments])
    raw   = list(polygonize(lines))
    if not raw:
        return []
    merged = unary_union(raw)
    if isinstance(merged, Polygon):
        return [merged]
    if isinstance(merged, MultiPolygon):
        return list(merged.geoms)
    return []


def _polygon_coords(geom) -> List[Tuple[float, float]]:
    """Return exterior ring coords (closed) for a Polygon or MultiPolygon."""
    if isinstance(geom, Polygon):
        return list(geom.exterior.coords)
    if isinstance(geom, MultiPolygon):
        biggest = max(geom.geoms, key=lambda g: g.area)
        return list(biggest.exterior.coords)
    return []


def _rectilinear_infill(
    region: Polygon,
    spacing: float,
    angle_deg: float,
    z: float,
    speed: float,
    extrude_fn,
    travel_fn,
    prev_xy,
) -> Tuple[float, float]:
    """Fill region with rectilinear lines at angle_deg. Returns final (x, y)."""
    bounds = region.bounds          # (minx, miny, maxx, maxy)
    rad    = math.radians(angle_deg)
    cx     = (bounds[0] + bounds[2]) / 2
    cy     = (bounds[1] + bounds[3]) / 2
    diag   = math.hypot(bounds[2] - bounds[0], bounds[3] - bounds[1]) / 2 + spacing

    perp_x, perp_y = -math.sin(rad), math.cos(rad)   # normal to lines
    line_x, line_y =  math.cos(rad), math.sin(rad)    # along lines

    n = int(diag / spacing) + 1
    for i in range(-n, n + 1):
        ox = cx + perp_x * i * spacing
        oy = cy + perp_y * i * spacing
        # Clip long line against region
        p0 = (ox - line_x * diag, oy - line_y * diag)
        p1 = (ox + line_x * diag, oy + line_y * diag)
        clip = region.intersection(LineString([p0, p1]))
        if clip.is_empty:
            continue
        segs = []
        if isinstance(clip, LineString):
            segs = [clip]
        elif hasattr(clip, "geoms"):
            segs = [g for g in clip.geoms if isinstance(g, LineString)]
        for seg in segs:
            sc = list(seg.coords)
            if len(sc) < 2:
                continue
            # Alternate direction each line
            if i % 2 == 1:
                sc = sc[::-1]
            travel_fn(sc[0][0], sc[0][1], z)
            prev_xy = (sc[0][0], sc[0][1])
            for x, y in sc[1:]:
                extrude_fn(prev_xy[0], prev_xy[1], x, y, z, speed)
                prev_xy = (x, y)

    return prev_xy if prev_xy else (cx, cy)

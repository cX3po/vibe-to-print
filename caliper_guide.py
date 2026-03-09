"""
caliper_guide.py
----------------
SVG caliper-measurement diagrams for the "how to measure" guide.

Each function returns a self-contained HTML string safe for
st.markdown(..., unsafe_allow_html=True).

Diagrams
--------
outside_diameter()   – caliper jaws around the outside of a cylinder/knob
inside_diameter()    – upper inside-jaws measuring a bore/shaft hole
depth()              – depth rod measuring a blind hole or recess
thickness_step()     – flat jaws measuring wall thickness or step height
full_guide_html()    – all four diagrams in a 2×2 grid with tips
"""

# ── Shared style constants ────────────────────────────────────────────────────
_BG       = "#0d1b2a"
_BODY     = "#3a78c9"          # caliper body/jaws
_BODY_HI  = "#5a98e9"          # highlight / tip edge
_PART     = "#1e3a50"          # object being measured (fill)
_PART_STR = "#a8dadc"          # object stroke / accent
_ARROW    = "#ffd700"          # measurement arrows
_LABEL    = "#e0f0ff"          # white text
_DIM_TXT  = "#ffd700"          # dimension text
_CAPTION  = "#7a9ab8"          # caption / instruction text


def _wrap(inner_svg: str, title: str, tip: str) -> str:
    """Wrap an SVG and a caption in a styled card."""
    return f"""
<div style="background:{_BG};border:1px solid #1d3557;border-radius:10px;
            padding:12px;margin:4px;">
  <div style="font-size:14px;font-weight:700;color:{_PART_STR};
              margin-bottom:6px">{title}</div>
  <svg viewBox="0 0 380 170" xmlns="http://www.w3.org/2000/svg"
       style="width:100%;border-radius:6px;background:{_BG}">
    {inner_svg}
  </svg>
  <div style="font-size:12px;color:{_CAPTION};margin-top:6px;
              line-height:1.5">{tip}</div>
</div>"""


# ── 1 · Outside diameter / width ─────────────────────────────────────────────

def outside_diameter() -> str:
    svg = f"""
  <!-- Caliper rule body -->
  <rect x="20" y="10" width="340" height="18" rx="3"
        fill="{_BODY}" opacity="0.9"/>
  <text x="190" y="23" text-anchor="middle" fill="{_LABEL}"
        font-size="10" font-family="monospace" letter-spacing="2">CALIPER</text>

  <!-- Fixed jaw (left) — vertical bar + angled tip -->
  <rect x="20" y="28" width="16" height="72" rx="2" fill="{_BODY}"/>
  <polygon points="20,100 36,100 36,110 26,110" fill="{_BODY_HI}"/>

  <!-- Movable jaw (right) -->
  <rect x="272" y="28" width="16" height="72" rx="2" fill="{_BODY}"/>
  <polygon points="272,100 288,100 278,110 272,110" fill="{_BODY_HI}"/>

  <!-- Lock screw on movable jaw -->
  <circle cx="280" cy="45" r="5" fill="{_BG}" stroke="{_BODY_HI}" stroke-width="1.5"/>
  <text x="280" y="49" text-anchor="middle" fill="{_BODY_HI}"
        font-size="7">+</text>

  <!-- The object (cylinder cross-section) -->
  <ellipse cx="154" cy="89" rx="118" ry="38"
           fill="{_PART}" stroke="{_PART_STR}" stroke-width="2"/>
  <text x="154" y="94" text-anchor="middle" fill="{_PART_STR}"
        font-size="12">KNOB / PART</text>

  <!-- Measurement span line -->
  <line x1="36" y1="136" x2="272" y2="136"
        stroke="{_ARROW}" stroke-width="1.5" stroke-dasharray="5,3"/>

  <!-- Arrowheads -->
  <polygon points="36,131 22,136 36,141" fill="{_ARROW}"/>
  <polygon points="272,131 286,136 272,141" fill="{_ARROW}"/>

  <!-- Dimension label -->
  <text x="154" y="155" text-anchor="middle" fill="{_DIM_TXT}"
        font-size="13" font-weight="bold">← outer diameter →</text>

  <!-- Jaw contact indicators -->
  <line x1="36" y1="110" x2="36" y2="136"
        stroke="{_ARROW}" stroke-width="1" stroke-dasharray="2,2" opacity="0.5"/>
  <line x1="272" y1="110" x2="272" y2="136"
        stroke="{_ARROW}" stroke-width="1" stroke-dasharray="2,2" opacity="0.5"/>
"""
    return _wrap(svg,
                 "Outside Diameter / Width",
                 "Close the <strong>lower jaws</strong> firmly around the widest point "
                 "of the part. Read the measurement on the scale. "
                 "For a knob: measure across the widest face.")


# ── 2 · Inside diameter / bore ────────────────────────────────────────────────

def inside_diameter() -> str:
    svg = f"""
  <!-- Caliper rule body -->
  <rect x="20" y="10" width="340" height="18" rx="3" fill="{_BODY}" opacity="0.9"/>
  <text x="190" y="23" text-anchor="middle" fill="{_LABEL}"
        font-size="10" font-family="monospace" letter-spacing="2">CALIPER</text>

  <!-- Upper inside jaws — small pointed nubs on TOP of body -->
  <!-- Left upper jaw -->
  <rect x="20" y="28" width="16" height="28" rx="1" fill="{_BODY}"/>
  <polygon points="20,56 36,56 28,66" fill="{_BODY_HI}"/>

  <!-- Right upper jaw -->
  <rect x="272" y="28" width="16" height="28" rx="1" fill="{_BODY}"/>
  <polygon points="272,56 288,56 280,66" fill="{_BODY_HI}"/>

  <!-- The bore (hole cross-section) — a thick-walled cylinder -->
  <rect x="60" y="70" width="188" height="60" rx="4"
        fill="{_PART}" stroke="{_PART_STR}" stroke-width="2"/>
  <!-- Hole label -->
  <text x="154" y="105" text-anchor="middle" fill="{_PART_STR}" font-size="11">
    SHAFT HOLE / BORE
  </text>

  <!-- Inside jaw tips in the hole -->
  <line x1="28" y1="66" x2="28" y2="100" stroke="{_BODY_HI}" stroke-width="2"/>
  <circle cx="28" cy="100" r="4" fill="{_BODY_HI}"/>

  <line x1="280" y1="66" x2="280" y2="100" stroke="{_BODY_HI}" stroke-width="2"/>
  <circle cx="280" cy="100" r="4" fill="{_BODY_HI}"/>

  <!-- Measurement span inside the hole -->
  <line x1="32" y1="130" x2="276" y2="130"
        stroke="{_ARROW}" stroke-width="1.5" stroke-dasharray="5,3"/>
  <polygon points="32,125 18,130 32,135" fill="{_ARROW}"/>
  <polygon points="276,125 290,130 276,135" fill="{_ARROW}"/>

  <text x="154" y="155" text-anchor="middle" fill="{_DIM_TXT}"
        font-size="13" font-weight="bold">← inner (bore) diameter →</text>
"""
    return _wrap(svg,
                 "Inside Diameter / Bore / Shaft Hole",
                 "Use the <strong>upper pointed jaws</strong> (smaller pair). "
                 "Insert into the hole, expand until snug. "
                 "Rotate slightly to find the true diameter. "
                 "This gives you the shaft hole size.")


# ── 3 · Depth measurement ─────────────────────────────────────────────────────

def depth() -> str:
    svg = f"""
  <!-- Caliper rule body (horizontal) -->
  <rect x="60" y="10" width="260" height="18" rx="3" fill="{_BODY}" opacity="0.9"/>
  <text x="190" y="23" text-anchor="middle" fill="{_LABEL}"
        font-size="10" font-family="monospace" letter-spacing="2">CALIPER</text>

  <!-- Depth rod extending down from end of body -->
  <rect x="184" y="28" width="8" height="82" rx="1" fill="{_BODY_HI}"/>
  <!-- Depth rod tip -->
  <polygon points="181,110 191,110 188,116 184,116" fill="{_BODY_HI}"/>

  <!-- The part with a blind hole (cross section) -->
  <!-- Outer wall left -->
  <rect x="100" y="32" width="28" height="90" rx="2"
        fill="{_PART}" stroke="{_PART_STR}" stroke-width="2"/>
  <!-- Outer wall right -->
  <rect x="260" y="32" width="28" height="90" rx="2"
        fill="{_PART}" stroke="{_PART_STR}" stroke-width="2"/>
  <!-- Bottom of hole -->
  <rect x="128" y="100" width="132" height="22" rx="2"
        fill="{_PART}" stroke="{_PART_STR}" stroke-width="2"/>
  <!-- Hole interior label -->
  <text x="194" y="94" text-anchor="middle" fill="{_PART_STR}" font-size="10">
    RECESS / HOLE
  </text>

  <!-- Top surface reference line -->
  <line x1="60" y1="32" x2="100" y2="32"
        stroke="{_ARROW}" stroke-width="1" stroke-dasharray="3,2" opacity="0.6"/>
  <line x1="288" y1="32" x2="320" y2="32"
        stroke="{_ARROW}" stroke-width="1" stroke-dasharray="3,2" opacity="0.6"/>

  <!-- Vertical measurement arrows -->
  <line x1="340" y1="32" x2="340" y2="100"
        stroke="{_ARROW}" stroke-width="1.5" stroke-dasharray="5,3"/>
  <polygon points="335,32 340,18 345,32" fill="{_ARROW}"/>
  <polygon points="335,100 340,114 345,100" fill="{_ARROW}"/>

  <!-- Depth label -->
  <text x="358" y="70" text-anchor="middle" fill="{_DIM_TXT}"
        font-size="11" font-weight="bold" transform="rotate(90,358,70)">DEPTH</text>
"""
    return _wrap(svg,
                 "Depth / Recess / Blind Hole",
                 "Rest the <strong>flat end of the caliper body</strong> on the top surface. "
                 "The depth rod drops into the hole. Read the measurement. "
                 "Use for: boss height, pocket depth, shaft recess depth.")


# ── 4 · Wall thickness / step height ─────────────────────────────────────────

def thickness_step() -> str:
    svg = f"""
  <!-- Part with a step / shoulder -->
  <!-- Lower face -->
  <rect x="60" y="100" width="260" height="50" rx="3"
        fill="{_PART}" stroke="{_PART_STR}" stroke-width="2"/>
  <!-- Upper boss -->
  <rect x="120" y="50" width="140" height="55" rx="3"
        fill="{_PART}" stroke="{_PART_STR}" stroke-width="2" opacity="0.9"/>
  <text x="190" y="82" text-anchor="middle" fill="{_PART_STR}" font-size="10">
    BOSS / SHOULDER
  </text>
  <text x="190" y="130" text-anchor="middle" fill="{_PART_STR}" font-size="10">
    BASE
  </text>

  <!-- Caliper body horizontal at top -->
  <rect x="60" y="12" width="260" height="16" rx="3" fill="{_BODY}" opacity="0.9"/>
  <text x="190" y="24" text-anchor="middle" fill="{_LABEL}"
        font-size="10" font-family="monospace" letter-spacing="2">CALIPER</text>

  <!-- Left jaw resting on lower surface -->
  <rect x="68" y="28" width="14" height="72" rx="1" fill="{_BODY}"/>
  <line x1="68" y1="100" x2="120" y2="100"
        stroke="{_BODY_HI}" stroke-width="2"/>  <!-- jaw tip on lower surface -->

  <!-- Right jaw resting on upper surface -->
  <rect x="310" y="28" width="14" height="23" rx="1" fill="{_BODY}"/>
  <line x1="260" y1="50" x2="324" y2="50"
        stroke="{_BODY_HI}" stroke-width="2"/>  <!-- jaw tip on upper surface -->

  <!-- Vertical measurement arrows -->
  <line x1="46" y1="50" x2="46" y2="100"
        stroke="{_ARROW}" stroke-width="1.5" stroke-dasharray="5,3"/>
  <polygon points="41,50 46,36 51,50" fill="{_ARROW}"/>
  <polygon points="41,100 46,114 51,100" fill="{_ARROW}"/>

  <text x="28" y="80" text-anchor="middle" fill="{_DIM_TXT}"
        font-size="11" font-weight="bold" transform="rotate(-90,28,80)">STEP</text>
"""
    return _wrap(svg,
                 "Wall Thickness / Step Height",
                 "One jaw on the <strong>lower surface</strong>, one on the <strong>upper shoulder</strong>. "
                 "Or close jaws on the wall to measure thickness directly. "
                 "Use for: boss height, flange thickness, lid depth.")


# ── Full guide (2×2 grid) ─────────────────────────────────────────────────────

def full_guide_html() -> str:
    """Return all four diagrams in a responsive 2-column grid."""
    d1 = outside_diameter()
    d2 = inside_diameter()
    d3 = depth()
    d4 = thickness_step()

    pro_tips = """
<div style="background:#1d3557;border-radius:8px;padding:12px 16px;margin-top:8px">
  <strong style="color:#a8dadc">Pro tips for accurate readings</strong>
  <ul style="color:#cdd8e0;font-size:13px;margin-top:6px;margin-bottom:0;
             line-height:1.8">
    <li>Zero the caliper before measuring (press the zero button).</li>
    <li>Keep the jaw faces <strong>perpendicular</strong> to the surface — tilting adds error.</li>
    <li>For round shafts: rotate slightly while holding the jaws — the <em>minimum</em> reading is the true diameter.</li>
    <li>Measure 3× and average if you need high precision (±0.05 mm).</li>
    <li>Convert inches to mm: multiply by <strong>25.4</strong>.</li>
    <li>1/4&Prime; = 6.35 mm · 3/8&Prime; = 9.53 mm · 1/2&Prime; = 12.70 mm</li>
  </ul>
</div>"""

    return f"""
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
  {d1}{d2}{d3}{d4}
</div>
{pro_tips}"""

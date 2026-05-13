#!/usr/bin/env python3
"""
Generate Visio-style network architecture PowerPoint presentation.
Five9/Genesys Bridge - GCP Dedicated Interconnect Architecture
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.dml import MSO_THEME_COLOR
import copy

# ============================================================
# COLOR SCHEME
# ============================================================
DARK_BLUE = RGBColor(0x1B, 0x2A, 0x4A)
MEDIUM_BLUE = RGBColor(0x2C, 0x5F, 0x8A)
LIGHT_BLUE = RGBColor(0x4A, 0x90, 0xD9)
ORANGE = RGBColor(0xE8, 0x6C, 0x00)
GREEN = RGBColor(0x28, 0xA7, 0x45)
GCP_BLUE = RGBColor(0x42, 0x85, 0xF4)
GCP_GREEN = RGBColor(0x34, 0xA8, 0x53)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF0, 0xF2, 0xF5)
DARK_GRAY = RGBColor(0x4A, 0x4A, 0x4A)
RED = RGBColor(0xDC, 0x35, 0x45)

# Slide dimensions
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

OUTPUT_PATH = "/projects/sandbox/hello_nw/docs/Five9_Genesys_Bridge_Executive_v1.pptx"


def set_slide_bg(slide, color):
    """Set solid background color for a slide."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_shape_box(slide, left, top, width, height, fill_color, text="",
                  font_size=10, font_color=WHITE, bold=False, shape_type=MSO_SHAPE.ROUNDED_RECTANGLE,
                  border_color=None, border_width=Pt(1), text_align=PP_ALIGN.CENTER):
    """Add a shape box with text."""
    shape = slide.shapes.add_shape(shape_type, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if border_color:
        shape.line.color.rgb = border_color
        shape.line.width = border_width
    else:
        shape.line.fill.background()

    tf = shape.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    tf.margin_left = Pt(4)
    tf.margin_right = Pt(4)
    tf.margin_top = Pt(2)
    tf.margin_bottom = Pt(2)

    if text:
        p = tf.paragraphs[0]
        p.alignment = text_align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(font_size)
        run.font.color.rgb = font_color
        run.font.bold = bold

    return shape


def add_text_box(slide, left, top, width, height, text, font_size=10,
                 font_color=DARK_GRAY, bold=False, alignment=PP_ALIGN.LEFT):
    """Add a text box."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = alignment
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.color.rgb = font_color
    run.font.bold = bold
    return txBox


def add_connector(slide, start_x, start_y, end_x, end_y, color=DARK_GRAY, width=Pt(1.5)):
    """Add a connector line between two points."""
    connector = slide.shapes.add_connector(
        1,  # straight connector
        start_x, start_y, end_x, end_y
    )
    connector.line.color.rgb = color
    connector.line.width = width
    return connector


def add_multiline_textbox(slide, left, top, width, height, lines, font_size=9,
                          font_color=DARK_GRAY, bold=False, alignment=PP_ALIGN.LEFT):
    """Add a text box with multiple lines."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.alignment = alignment
        run = p.add_run()
        run.text = line
        run.font.size = Pt(font_size)
        run.font.color.rgb = font_color
        run.font.bold = bold
    return txBox


# ============================================================
# SLIDE 1: Title Slide
# ============================================================
def create_slide_1(prs):
    """Title slide with dark blue background."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
    set_slide_bg(slide, DARK_BLUE)

    # Main title
    add_text_box(slide, Inches(1), Inches(2.0), Inches(11.333), Inches(1.2),
                 "Network Architecture: GCP Dedicated Interconnect",
                 font_size=36, font_color=WHITE, bold=True, alignment=PP_ALIGN.CENTER)

    # Subtitle
    add_text_box(slide, Inches(1), Inches(3.4), Inches(11.333), Inches(0.8),
                 "Dual DC (Dallas + Phoenix) | Private Voice & Data Connectivity",
                 font_size=20, font_color=LIGHT_BLUE, bold=False, alignment=PP_ALIGN.CENTER)

    # Specs line
    add_text_box(slide, Inches(1), Inches(4.5), Inches(11.333), Inches(0.6),
                 "99.99% SLA | < 80ms Voice Latency | 10 Gbps Dedicated",
                 font_size=16, font_color=LIGHT_GRAY, bold=False, alignment=PP_ALIGN.CENTER)

    # Decorative line
    add_shape_box(slide, Inches(3), Inches(4.2), Inches(7.333), Inches(0.03),
                  LIGHT_BLUE, shape_type=MSO_SHAPE.RECTANGLE)

    return slide


# ============================================================
# SLIDE 2: Physical Network Topology
# ============================================================
def create_slide_2(prs):
    """Physical Network Topology - Dual DC to GCP (Visio-style)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    # Title bar
    add_shape_box(slide, Inches(0), Inches(0), SLIDE_WIDTH, Inches(0.7),
                  DARK_BLUE, "Physical Network Topology - Dual DC to GCP",
                  font_size=18, font_color=WHITE, bold=True)

    # ---- LEFT ZONE: On-Premises ----
    # Dallas DC container
    add_shape_box(slide, Inches(0.3), Inches(1.0), Inches(2.8), Inches(2.6),
                  LIGHT_GRAY, "", border_color=DARK_BLUE, border_width=Pt(2),
                  shape_type=MSO_SHAPE.RECTANGLE)
    add_text_box(slide, Inches(0.4), Inches(1.05), Inches(2.6), Inches(0.35),
                 "Dallas DC (Primary)", font_size=10, font_color=DARK_BLUE, bold=True)

    # Dallas SBC
    add_shape_box(slide, Inches(0.5), Inches(1.5), Inches(2.4), Inches(0.7),
                  MEDIUM_BLUE, "Oracle SBC (HA)", font_size=9, font_color=WHITE, bold=True)
    # Dallas Genesys
    add_shape_box(slide, Inches(0.5), Inches(2.4), Inches(2.4), Inches(0.7),
                  GREEN, "Genesys SIP/ORS", font_size=9, font_color=WHITE, bold=True)

    # Phoenix DC container
    add_shape_box(slide, Inches(0.3), Inches(4.0), Inches(2.8), Inches(2.6),
                  LIGHT_GRAY, "", border_color=DARK_BLUE, border_width=Pt(2),
                  shape_type=MSO_SHAPE.RECTANGLE)
    add_text_box(slide, Inches(0.4), Inches(4.05), Inches(2.6), Inches(0.35),
                 "Phoenix DC (DR)", font_size=10, font_color=DARK_BLUE, bold=True)

    # Phoenix SBC
    add_shape_box(slide, Inches(0.5), Inches(4.5), Inches(2.4), Inches(0.7),
                  MEDIUM_BLUE, "Oracle SBC (DR)", font_size=9, font_color=WHITE, bold=True)
    # Phoenix Genesys
    add_shape_box(slide, Inches(0.5), Inches(5.4), Inches(2.4), Inches(0.7),
                  GREEN, "Genesys DR", font_size=9, font_color=WHITE, bold=True)

    # ---- MIDDLE ZONE: Interconnect ----
    # Equinix DA7
    add_shape_box(slide, Inches(4.2), Inches(1.3), Inches(1.8), Inches(0.65),
                  DARK_GRAY, "Equinix DA7", font_size=9, font_color=WHITE, bold=True)
    add_text_box(slide, Inches(4.2), Inches(1.95), Inches(1.8), Inches(0.3),
                 "10G Ded.", font_size=8, font_color=DARK_GRAY, bold=False, alignment=PP_ALIGN.CENTER)

    # Equinix DA2
    add_shape_box(slide, Inches(4.2), Inches(2.5), Inches(1.8), Inches(0.65),
                  DARK_GRAY, "Equinix DA2", font_size=9, font_color=WHITE, bold=True)
    add_text_box(slide, Inches(4.2), Inches(3.15), Inches(1.8), Inches(0.3),
                 "10G Ded.", font_size=8, font_color=DARK_GRAY, bold=False, alignment=PP_ALIGN.CENTER)

    # Equinix PH1
    add_shape_box(slide, Inches(4.2), Inches(4.3), Inches(1.8), Inches(0.65),
                  DARK_GRAY, "Equinix PH1", font_size=9, font_color=WHITE, bold=True)
    add_text_box(slide, Inches(4.2), Inches(4.95), Inches(1.8), Inches(0.3),
                 "10G Ded.", font_size=8, font_color=DARK_GRAY, bold=False, alignment=PP_ALIGN.CENTER)

    # DataBank PHX1
    add_shape_box(slide, Inches(4.2), Inches(5.5), Inches(1.8), Inches(0.65),
                  DARK_GRAY, "DataBank PHX1", font_size=9, font_color=WHITE, bold=True)
    add_text_box(slide, Inches(4.2), Inches(6.15), Inches(1.8), Inches(0.3),
                 "10G Ded.", font_size=8, font_color=DARK_GRAY, bold=False, alignment=PP_ALIGN.CENTER)

    # Dark Fiber labels
    add_text_box(slide, Inches(3.2), Inches(0.85), Inches(1.2), Inches(0.3),
                 "AT&T Dark Fiber", font_size=7, font_color=DARK_GRAY, bold=False, alignment=PP_ALIGN.CENTER)
    add_text_box(slide, Inches(3.2), Inches(3.7), Inches(1.4), Inches(0.3),
                 "Verizon Dark Fiber", font_size=7, font_color=DARK_GRAY, bold=False, alignment=PP_ALIGN.CENTER)

    # ---- RIGHT ZONE: GCP ----
    # GCP us-south1 container
    add_shape_box(slide, Inches(7.2), Inches(1.0), Inches(4.0), Inches(3.5),
                  RGBColor(0xE8, 0xF0, 0xFE), "", border_color=GCP_BLUE, border_width=Pt(2),
                  shape_type=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text_box(slide, Inches(7.3), Inches(1.05), Inches(3.8), Inches(0.35),
                 "GCP us-south1 (Dallas)", font_size=10, font_color=GCP_BLUE, bold=True)

    add_shape_box(slide, Inches(7.4), Inches(1.5), Inches(3.6), Inches(0.55),
                  GCP_BLUE, "Cloud Router / BGP", font_size=9, font_color=WHITE, bold=True)
    add_shape_box(slide, Inches(7.4), Inches(2.2), Inches(3.6), Inches(0.55),
                  GCP_BLUE, "GTP (Voice)", font_size=9, font_color=WHITE, bold=True)
    add_shape_box(slide, Inches(7.4), Inches(2.9), Inches(3.6), Inches(0.55),
                  GCP_BLUE, "Dialogflow CX", font_size=9, font_color=WHITE, bold=True)
    add_shape_box(slide, Inches(7.4), Inches(3.6), Inches(3.6), Inches(0.55),
                  GCP_GREEN, "Cloud Run (API)", font_size=9, font_color=WHITE, bold=True)

    # GCP us-central1 (DR)
    add_shape_box(slide, Inches(7.2), Inches(4.8), Inches(4.0), Inches(1.2),
                  RGBColor(0xE8, 0xF0, 0xEE), "", border_color=GCP_GREEN, border_width=Pt(1.5),
                  shape_type=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text_box(slide, Inches(7.3), Inches(4.85), Inches(3.8), Inches(0.35),
                 "GCP us-central1 (DR)", font_size=10, font_color=GCP_GREEN, bold=True)
    add_shape_box(slide, Inches(7.4), Inches(5.3), Inches(3.6), Inches(0.5),
                  RGBColor(0xAA, 0xCC, 0xAA), "DR Replicas (Standby)", font_size=8, font_color=DARK_GRAY)

    # Five9 Cloud (TOP)
    add_shape_box(slide, Inches(0.5), Inches(0.75), Inches(1.8), Inches(0.5),
                  ORANGE, "Five9 Cloud", font_size=9, font_color=WHITE, bold=True,
                  shape_type=MSO_SHAPE.ROUNDED_RECTANGLE)

    # Connectors: Dallas DC to Equinix
    add_connector(slide, Inches(3.1), Inches(1.85), Inches(4.2), Inches(1.6), ORANGE, Pt(2))
    add_connector(slide, Inches(3.1), Inches(1.85), Inches(4.2), Inches(2.8), LIGHT_BLUE, Pt(1.5))

    # Phoenix DC to Equinix
    add_connector(slide, Inches(3.1), Inches(4.85), Inches(4.2), Inches(4.6), ORANGE, Pt(2))
    add_connector(slide, Inches(3.1), Inches(5.75), Inches(4.2), Inches(5.8), LIGHT_BLUE, Pt(1.5))

    # Equinix to GCP
    add_connector(slide, Inches(6.0), Inches(1.6), Inches(7.2), Inches(1.75), GCP_BLUE, Pt(2))
    add_connector(slide, Inches(6.0), Inches(2.8), Inches(7.2), Inches(2.5), GCP_BLUE, Pt(2))
    add_connector(slide, Inches(6.0), Inches(4.6), Inches(7.2), Inches(5.0), GCP_GREEN, Pt(1.5))
    add_connector(slide, Inches(6.0), Inches(5.8), Inches(7.2), Inches(5.4), GCP_GREEN, Pt(1.5))

    # Five9 to SBC
    add_connector(slide, Inches(1.4), Inches(1.25), Inches(1.4), Inches(1.5), ORANGE, Pt(2))

    # Connector labels
    add_text_box(slide, Inches(6.1), Inches(1.3), Inches(1.1), Inches(0.25),
                 "10 Gbps", font_size=7, font_color=GCP_BLUE, bold=True, alignment=PP_ALIGN.CENTER)
    add_text_box(slide, Inches(6.1), Inches(2.6), Inches(1.1), Inches(0.25),
                 "SIP TLS", font_size=7, font_color=GCP_BLUE, bold=False, alignment=PP_ALIGN.CENTER)
    add_text_box(slide, Inches(6.1), Inches(4.4), Inches(1.1), Inches(0.25),
                 "SRTP", font_size=7, font_color=GCP_GREEN, bold=False, alignment=PP_ALIGN.CENTER)

    # Legend
    add_shape_box(slide, Inches(0.3), Inches(6.8), Inches(12.7), Inches(0.55),
                  RGBColor(0xFA, 0xFA, 0xFA), "", border_color=DARK_GRAY, border_width=Pt(0.5),
                  shape_type=MSO_SHAPE.RECTANGLE)
    # Legend items
    add_shape_box(slide, Inches(0.5), Inches(6.92), Inches(0.6), Inches(0.06),
                  ORANGE, "", shape_type=MSO_SHAPE.RECTANGLE)
    add_text_box(slide, Inches(1.15), Inches(6.85), Inches(1.2), Inches(0.3),
                 "Voice Path", font_size=8, font_color=DARK_GRAY, bold=False)

    add_shape_box(slide, Inches(2.8), Inches(6.92), Inches(0.6), Inches(0.06),
                  LIGHT_BLUE, "", shape_type=MSO_SHAPE.RECTANGLE)
    add_text_box(slide, Inches(3.45), Inches(6.85), Inches(1.2), Inches(0.3),
                 "Data Path", font_size=8, font_color=DARK_GRAY, bold=False)

    add_shape_box(slide, Inches(5.2), Inches(6.92), Inches(0.6), Inches(0.06),
                  DARK_GRAY, "", shape_type=MSO_SHAPE.RECTANGLE)
    add_text_box(slide, Inches(5.85), Inches(6.85), Inches(1.8), Inches(0.3),
                 "Dark Fiber (dashed)", font_size=8, font_color=DARK_GRAY, bold=False)

    return slide



# ============================================================
# SLIDE 3: Voice Path Network Diagram
# ============================================================
def create_slide_3(prs):
    """Voice Path: Detailed Network Flow (Visio-style)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    # Title bar
    add_shape_box(slide, Inches(0), Inches(0), SLIDE_WIDTH, Inches(0.7),
                  DARK_BLUE, "Voice Path: Detailed Network Flow",
                  font_size=18, font_color=WHITE, bold=True)

    # Flow elements - left to right
    y_center = Inches(3.0)
    box_h = Inches(0.9)
    box_w = Inches(1.6)
    gap = Inches(0.15)

    # 1. Caller
    add_shape_box(slide, Inches(0.2), Inches(2.7), Inches(1.1), Inches(0.8),
                  DARK_GRAY, "Caller", font_size=9, font_color=WHITE, bold=True,
                  shape_type=MSO_SHAPE.OVAL)

    # 2. PSTN
    add_shape_box(slide, Inches(1.6), Inches(2.6), Inches(1.3), Inches(1.0),
                  RGBColor(0x88, 0x88, 0x88), "PSTN", font_size=9, font_color=WHITE, bold=True,
                  shape_type=MSO_SHAPE.ROUNDED_RECTANGLE)

    # 3. Oracle SBC
    add_shape_box(slide, Inches(3.2), Inches(2.55), Inches(1.5), Inches(1.1),
                  MEDIUM_BLUE, "Oracle SBC", font_size=9, font_color=WHITE, bold=True)
    add_text_box(slide, Inches(3.2), Inches(3.65), Inches(1.5), Inches(0.3),
                 "SIP/RTP Ingress", font_size=7, font_color=MEDIUM_BLUE, bold=False, alignment=PP_ALIGN.CENTER)

    # 4. Dedicated Interconnect (thick)
    add_shape_box(slide, Inches(5.0), Inches(2.8), Inches(1.8), Inches(0.6),
                  DARK_BLUE, "Dedicated Interconnect", font_size=8, font_color=WHITE, bold=True,
                  shape_type=MSO_SHAPE.RECTANGLE)
    add_text_box(slide, Inches(5.0), Inches(3.4), Inches(1.8), Inches(0.4),
                 "10G | VLAN 100 | < 2ms", font_size=7, font_color=DARK_BLUE, bold=False, alignment=PP_ALIGN.CENTER)

    # 5. GCP GTP
    add_shape_box(slide, Inches(7.1), Inches(2.55), Inches(1.5), Inches(1.1),
                  GCP_BLUE, "GCP GTP", font_size=9, font_color=WHITE, bold=True)
    add_text_box(slide, Inches(7.1), Inches(3.65), Inches(1.5), Inches(0.4),
                 "SIP TLS 5061\n+ SRTP", font_size=7, font_color=GCP_BLUE, bold=False, alignment=PP_ALIGN.CENTER)

    # 6. Dialogflow CX / CCAI
    add_shape_box(slide, Inches(8.9), Inches(2.55), Inches(1.8), Inches(1.1),
                  GCP_BLUE, "Dialogflow CX\n/ CCAI", font_size=9, font_color=WHITE, bold=True)
    add_text_box(slide, Inches(8.9), Inches(3.65), Inches(1.8), Inches(0.4),
                 "STT > NLU > TTS\n50-100ms", font_size=7, font_color=GCP_BLUE, bold=False, alignment=PP_ALIGN.CENTER)

    # Connectors (orange voice path)
    add_connector(slide, Inches(1.3), Inches(3.1), Inches(1.6), Inches(3.1), ORANGE, Pt(2.5))
    add_connector(slide, Inches(2.9), Inches(3.1), Inches(3.2), Inches(3.1), ORANGE, Pt(2.5))
    add_connector(slide, Inches(4.7), Inches(3.1), Inches(5.0), Inches(3.1), ORANGE, Pt(2.5))
    add_connector(slide, Inches(6.8), Inches(3.1), Inches(7.1), Inches(3.1), ORANGE, Pt(2.5))
    add_connector(slide, Inches(8.6), Inches(3.1), Inches(8.9), Inches(3.1), ORANGE, Pt(2.5))

    # Return path (below)
    add_shape_box(slide, Inches(1.0), Inches(4.5), Inches(10.5), Inches(0.6),
                  RGBColor(0xFF, 0xF3, 0xE0), "", border_color=ORANGE, border_width=Pt(1.5),
                  shape_type=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text_box(slide, Inches(1.2), Inches(4.55), Inches(10.0), Inches(0.5),
                 "Return: GTP \u2192 Interconnect \u2192 SBC \u2192 Genesys SIP \u2192 Agent Desktop",
                 font_size=9, font_color=ORANGE, bold=True, alignment=PP_ALIGN.CENTER)

    # Return arrows
    add_connector(slide, Inches(10.7), Inches(3.65), Inches(10.7), Inches(4.5), ORANGE, Pt(1.5))
    add_connector(slide, Inches(1.0), Inches(4.5), Inches(1.0), Inches(3.65), ORANGE, Pt(1.5))

    # Specs box at bottom
    add_shape_box(slide, Inches(0.5), Inches(5.5), Inches(12.3), Inches(1.2),
                  RGBColor(0xF8, 0xF9, 0xFA), "", border_color=MEDIUM_BLUE, border_width=Pt(1.5),
                  shape_type=MSO_SHAPE.ROUNDED_RECTANGLE)
    specs_lines = [
        "Voice Path Specifications:",
        "Codec: G.711u (64kbps) | Encryption: TLS + SRTP | Latency: < 80ms one-way | QoS: DSCP EF (46)"
    ]
    add_multiline_textbox(slide, Inches(0.8), Inches(5.7), Inches(11.8), Inches(0.9),
                          specs_lines, font_size=10, font_color=DARK_BLUE, bold=True,
                          alignment=PP_ALIGN.CENTER)

    return slide



# ============================================================
# SLIDE 4: Data Path Network Diagram
# ============================================================
def create_slide_4(prs):
    """Data Path: Private API Connectivity (Visio-style)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    # Title bar
    add_shape_box(slide, Inches(0), Inches(0), SLIDE_WIDTH, Inches(0.7),
                  DARK_BLUE, "Data Path: Private API Connectivity",
                  font_size=18, font_color=WHITE, bold=True)

    # Flow elements - left to right
    y_top = Inches(2.5)
    box_h = Inches(1.0)

    # 1. Genesys ORS
    add_shape_box(slide, Inches(0.3), y_top, Inches(1.6), box_h,
                  GREEN, "Genesys ORS", font_size=10, font_color=WHITE, bold=True)

    # 2. DC Router
    add_shape_box(slide, Inches(2.3), Inches(2.6), Inches(1.3), Inches(0.8),
                  DARK_GRAY, "DC Router", font_size=9, font_color=WHITE, bold=True)

    # 3. Dedicated Interconnect
    add_shape_box(slide, Inches(4.0), Inches(2.5), Inches(2.0), Inches(1.0),
                  DARK_BLUE, "Dedicated\nInterconnect", font_size=9, font_color=WHITE, bold=True,
                  shape_type=MSO_SHAPE.RECTANGLE)
    add_text_box(slide, Inches(4.0), Inches(3.5), Inches(2.0), Inches(0.4),
                 "10G | VLAN 200 | < 2ms", font_size=7, font_color=DARK_BLUE, bold=False, alignment=PP_ALIGN.CENTER)

    # 4. Cloud Router
    add_shape_box(slide, Inches(6.4), Inches(2.5), Inches(1.5), box_h,
                  GCP_BLUE, "Cloud Router", font_size=9, font_color=WHITE, bold=True)

    # 5. Private Service Connect
    add_shape_box(slide, Inches(8.2), Inches(2.5), Inches(1.7), box_h,
                  GCP_BLUE, "Private Service\nConnect", font_size=9, font_color=WHITE, bold=True)

    # 6. Cloud Run Middleware
    add_shape_box(slide, Inches(10.2), Inches(2.5), Inches(1.8), box_h,
                  GCP_GREEN, "Cloud Run\nMiddleware", font_size=9, font_color=WHITE, bold=True)

    # Connectors (blue data path)
    add_connector(slide, Inches(1.9), Inches(3.0), Inches(2.3), Inches(3.0), LIGHT_BLUE, Pt(2.5))
    add_connector(slide, Inches(3.6), Inches(3.0), Inches(4.0), Inches(3.0), LIGHT_BLUE, Pt(2.5))
    add_connector(slide, Inches(6.0), Inches(3.0), Inches(6.4), Inches(3.0), LIGHT_BLUE, Pt(2.5))
    add_connector(slide, Inches(7.9), Inches(3.0), Inches(8.2), Inches(3.0), LIGHT_BLUE, Pt(2.5))
    add_connector(slide, Inches(9.9), Inches(3.0), Inches(10.2), Inches(3.0), LIGHT_BLUE, Pt(2.5))

    # Fan out from Cloud Run to 3 services
    fan_y = Inches(4.3)
    # Firestore
    add_shape_box(slide, Inches(9.2), fan_y, Inches(1.3), Inches(0.7),
                  GCP_GREEN, "Firestore", font_size=8, font_color=WHITE, bold=True)
    # BigQuery
    add_shape_box(slide, Inches(10.6), fan_y, Inches(1.3), Inches(0.7),
                  GCP_GREEN, "BigQuery", font_size=8, font_color=WHITE, bold=True)
    # Pub/Sub
    add_shape_box(slide, Inches(12.0), fan_y, Inches(1.1), Inches(0.7),
                  GCP_GREEN, "Pub/Sub", font_size=8, font_color=WHITE, bold=True)

    # Fan-out connectors
    add_connector(slide, Inches(11.1), Inches(3.5), Inches(9.85), fan_y, GCP_GREEN, Pt(1.5))
    add_connector(slide, Inches(11.1), Inches(3.5), Inches(11.25), fan_y, GCP_GREEN, Pt(1.5))
    add_connector(slide, Inches(11.1), Inches(3.5), Inches(12.55), fan_y, GCP_GREEN, Pt(1.5))

    # Key callout box
    add_shape_box(slide, Inches(1.0), Inches(5.5), Inches(11.3), Inches(1.0),
                  RGBColor(0xE8, 0xF5, 0xE9), "", border_color=GREEN, border_width=Pt(2),
                  shape_type=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text_box(slide, Inches(1.3), Inches(5.7), Inches(10.8), Inches(0.7),
                 "All Private - No Public IPs | Private Google Access | < 50ms Round-Trip",
                 font_size=14, font_color=GREEN, bold=True, alignment=PP_ALIGN.CENTER)

    return slide



# ============================================================
# SLIDE 5: GCP VPC & Security Architecture
# ============================================================
def create_slide_5(prs):
    """GCP VPC Architecture & Security Controls (Visio-style)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    # Title bar
    add_shape_box(slide, Inches(0), Inches(0), SLIDE_WIDTH, Inches(0.7),
                  DARK_BLUE, "GCP VPC Architecture & Security Controls",
                  font_size=18, font_color=WHITE, bold=True)

    # VPC Service Controls Perimeter (RED dashed outer border)
    perimeter = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                       Inches(0.2), Inches(0.9), Inches(10.0), Inches(6.0))
    perimeter.fill.background()
    perimeter.line.color.rgb = RED
    perimeter.line.width = Pt(2.5)
    perimeter.line.dash_style = 4  # dash

    add_text_box(slide, Inches(0.4), Inches(0.95), Inches(4.0), Inches(0.3),
                 "VPC Service Controls Perimeter", font_size=9, font_color=RED, bold=True)

    # VPC Box inside perimeter
    vpc = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                  Inches(0.5), Inches(1.4), Inches(9.4), Inches(4.5))
    vpc.fill.solid()
    vpc.fill.fore_color.rgb = LIGHT_GRAY
    vpc.line.color.rgb = MEDIUM_BLUE
    vpc.line.width = Pt(2)

    add_text_box(slide, Inches(0.7), Inches(1.45), Inches(5.0), Inches(0.35),
                 "contact-center-vpc (Global)", font_size=11, font_color=MEDIUM_BLUE, bold=True)

    # 3 Subnet boxes side by side
    subnet_y = Inches(2.0)
    subnet_h = Inches(2.5)
    subnet_w = Inches(2.8)

    # Voice Subnet
    add_shape_box(slide, Inches(0.8), subnet_y, subnet_w, subnet_h,
                  RGBColor(0xFF, 0xF0, 0xE0), "", border_color=ORANGE, border_width=Pt(1.5),
                  shape_type=MSO_SHAPE.RECTANGLE)
    voice_lines = [
        "voice-subnet",
        "10.100.0.0/24",
        "",
        "\u2022 GTP Endpoints",
        "\u2022 SBC Landing"
    ]
    add_multiline_textbox(slide, Inches(0.9), Inches(2.1), Inches(2.6), Inches(2.3),
                          voice_lines, font_size=9, font_color=DARK_GRAY, bold=False)

    # Data Subnet
    add_shape_box(slide, Inches(3.8), subnet_y, subnet_w, subnet_h,
                  RGBColor(0xE0, 0xF0, 0xFF), "", border_color=LIGHT_BLUE, border_width=Pt(1.5),
                  shape_type=MSO_SHAPE.RECTANGLE)
    data_lines = [
        "data-subnet",
        "10.101.0.0/24",
        "",
        "\u2022 Cloud Run",
        "\u2022 PSC Endpoints"
    ]
    add_multiline_textbox(slide, Inches(3.9), Inches(2.1), Inches(2.6), Inches(2.3),
                          data_lines, font_size=9, font_color=DARK_GRAY, bold=False)

    # CCAI Subnet
    add_shape_box(slide, Inches(6.8), subnet_y, subnet_w, subnet_h,
                  RGBColor(0xE8, 0xF0, 0xFE), "", border_color=GCP_BLUE, border_width=Pt(1.5),
                  shape_type=MSO_SHAPE.RECTANGLE)
    ccai_lines = [
        "ccai-subnet",
        "10.102.0.0/24",
        "",
        "\u2022 Dialogflow CX",
        "\u2022 STT/TTS"
    ]
    add_multiline_textbox(slide, Inches(6.9), Inches(2.1), Inches(2.6), Inches(2.3),
                          ccai_lines, font_size=9, font_color=DARK_GRAY, bold=False)

    # DR replicas (smaller, grayed)
    dr_y = Inches(4.7)
    add_shape_box(slide, Inches(0.8), dr_y, Inches(9.0), Inches(0.7),
                  RGBColor(0xDD, 0xDD, 0xDD), "us-central1 DR replicas (standby)",
                  font_size=9, font_color=DARK_GRAY, bold=False,
                  border_color=RGBColor(0xBB, 0xBB, 0xBB), border_width=Pt(1))

    # Interconnect entry point at bottom
    add_shape_box(slide, Inches(2.5), Inches(5.8), Inches(2.5), Inches(0.7),
                  GCP_BLUE, "Cloud Router\n(Interconnect Entry)", font_size=8, font_color=WHITE, bold=True)

    # Lines from Cloud Router to subnets
    add_connector(slide, Inches(3.75), Inches(5.8), Inches(2.2), Inches(4.5), LIGHT_BLUE, Pt(1.5))
    add_connector(slide, Inches(3.75), Inches(5.8), Inches(5.2), Inches(4.5), LIGHT_BLUE, Pt(1.5))
    add_connector(slide, Inches(3.75), Inches(5.8), Inches(8.2), Inches(4.5), LIGHT_BLUE, Pt(1.5))

    # ---- Security Panel (right side) ----
    add_shape_box(slide, Inches(10.5), Inches(1.0), Inches(2.6), Inches(5.5),
                  RGBColor(0xFD, 0xF0, 0xF0), "", border_color=RED, border_width=Pt(1.5),
                  shape_type=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text_box(slide, Inches(10.6), Inches(1.1), Inches(2.4), Inches(0.35),
                 "Security Controls", font_size=10, font_color=RED, bold=True, alignment=PP_ALIGN.CENTER)

    security_items = [
        "\u2713 Private Google Access",
        "\u2713 No Public IPs",
        "\u2713 Cloud Armor WAF",
        "\u2713 Audit Logging",
        "\u2713 CMEK Encryption",
        "\u2713 VPC Svc Controls",
        "\u2713 IAM Least Privilege",
    ]
    add_multiline_textbox(slide, Inches(10.7), Inches(1.6), Inches(2.3), Inches(4.5),
                          security_items, font_size=9, font_color=DARK_GRAY, bold=False)

    return slide



# ============================================================
# SLIDE 6: High Availability & Failover Diagram
# ============================================================
def create_slide_6(prs):
    """High Availability: 99.99% SLA Design (Visio-style)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    # Title bar
    add_shape_box(slide, Inches(0), Inches(0), SLIDE_WIDTH, Inches(0.7),
                  DARK_BLUE, "High Availability: 99.99% SLA Design",
                  font_size=18, font_color=WHITE, bold=True)

    # 2x2 Grid layout
    quad_w = Inches(6.2)
    quad_h = Inches(3.1)

    # ---- TOP-LEFT: Normal Operation ----
    tl_x = Inches(0.2)
    tl_y = Inches(0.9)
    add_shape_box(slide, tl_x, tl_y, quad_w, quad_h,
                  RGBColor(0xF0, 0xFD, 0xF0), "", border_color=GREEN, border_width=Pt(1.5),
                  shape_type=MSO_SHAPE.RECTANGLE)
    add_text_box(slide, Inches(0.4), Inches(1.0), Inches(3.0), Inches(0.3),
                 "Normal Operation", font_size=11, font_color=GREEN, bold=True)

    # Dallas DC
    add_shape_box(slide, Inches(0.5), Inches(1.5), Inches(1.3), Inches(0.6),
                  DARK_BLUE, "Dallas DC", font_size=8, font_color=WHITE, bold=True)
    # DA7 (primary - green)
    add_shape_box(slide, Inches(2.2), Inches(1.5), Inches(1.2), Inches(0.6),
                  GREEN, "DA7 \u2713", font_size=8, font_color=WHITE, bold=True)
    # GCP
    add_shape_box(slide, Inches(4.0), Inches(1.5), Inches(2.0), Inches(0.6),
                  GCP_BLUE, "GCP us-south1", font_size=8, font_color=WHITE, bold=True)
    add_connector(slide, Inches(1.8), Inches(1.8), Inches(2.2), Inches(1.8), GREEN, Pt(2))
    add_connector(slide, Inches(3.4), Inches(1.8), Inches(4.0), Inches(1.8), GREEN, Pt(2))

    # DA2 (standby - gray)
    add_shape_box(slide, Inches(2.2), Inches(2.5), Inches(1.2), Inches(0.6),
                  RGBColor(0xBB, 0xBB, 0xBB), "DA2 (stby)", font_size=8, font_color=WHITE, bold=False)
    add_connector(slide, Inches(1.8), Inches(2.1), Inches(2.2), Inches(2.8), RGBColor(0xBB, 0xBB, 0xBB), Pt(1))

    # ---- TOP-RIGHT: Single Link Failure ----
    tr_x = Inches(6.8)
    tr_y = Inches(0.9)
    add_shape_box(slide, tr_x, tr_y, quad_w, quad_h,
                  RGBColor(0xFF, 0xF8, 0xF0), "", border_color=ORANGE, border_width=Pt(1.5),
                  shape_type=MSO_SHAPE.RECTANGLE)
    add_text_box(slide, Inches(7.0), Inches(1.0), Inches(4.0), Inches(0.3),
                 "Single Link Failure (< 1 sec)", font_size=11, font_color=ORANGE, bold=True)

    # Dallas DC
    add_shape_box(slide, Inches(7.1), Inches(1.5), Inches(1.3), Inches(0.6),
                  DARK_BLUE, "Dallas DC", font_size=8, font_color=WHITE, bold=True)
    # DA7 (failed - red X)
    add_shape_box(slide, Inches(8.8), Inches(1.5), Inches(1.2), Inches(0.6),
                  RED, "DA7 \u2717", font_size=8, font_color=WHITE, bold=True)
    # DA2 (active - green)
    add_shape_box(slide, Inches(8.8), Inches(2.5), Inches(1.2), Inches(0.6),
                  GREEN, "DA2 \u2713", font_size=8, font_color=WHITE, bold=True)
    # GCP
    add_shape_box(slide, Inches(10.6), Inches(2.0), Inches(2.0), Inches(0.6),
                  GCP_BLUE, "GCP us-south1", font_size=8, font_color=WHITE, bold=True)

    add_connector(slide, Inches(8.4), Inches(1.8), Inches(8.8), Inches(1.8), RED, Pt(2))
    add_connector(slide, Inches(8.4), Inches(2.1), Inches(8.8), Inches(2.8), GREEN, Pt(2))
    add_connector(slide, Inches(10.0), Inches(2.8), Inches(10.6), Inches(2.3), GREEN, Pt(2))

    # ---- BOTTOM-LEFT: Metro Failure ----
    bl_x = Inches(0.2)
    bl_y = Inches(4.2)
    add_shape_box(slide, bl_x, bl_y, quad_w, quad_h,
                  RGBColor(0xFF, 0xF0, 0xF0), "", border_color=RED, border_width=Pt(1.5),
                  shape_type=MSO_SHAPE.RECTANGLE)
    add_text_box(slide, Inches(0.4), Inches(4.3), Inches(4.0), Inches(0.3),
                 "Metro Failure (< 30 sec)", font_size=11, font_color=RED, bold=True)

    # Dallas DC (failed)
    add_shape_box(slide, Inches(0.5), Inches(4.8), Inches(1.3), Inches(0.6),
                  RED, "Dallas \u2717", font_size=8, font_color=WHITE, bold=True)
    # WAN
    add_shape_box(slide, Inches(2.1), Inches(5.0), Inches(0.8), Inches(0.5),
                  DARK_GRAY, "WAN", font_size=7, font_color=WHITE, bold=True)
    # Phoenix DC
    add_shape_box(slide, Inches(3.1), Inches(4.8), Inches(1.3), Inches(0.6),
                  DARK_BLUE, "Phoenix DC", font_size=8, font_color=WHITE, bold=True)
    # PH1
    add_shape_box(slide, Inches(4.7), Inches(4.8), Inches(0.8), Inches(0.6),
                  GREEN, "PH1", font_size=8, font_color=WHITE, bold=True)
    # GCP DR
    add_shape_box(slide, Inches(5.6), Inches(4.8), Inches(0.7), Inches(0.6),
                  GCP_GREEN, "DR", font_size=8, font_color=WHITE, bold=True)

    add_connector(slide, Inches(1.8), Inches(5.1), Inches(2.1), Inches(5.2), DARK_GRAY, Pt(1.5))
    add_connector(slide, Inches(2.9), Inches(5.2), Inches(3.1), Inches(5.1), GREEN, Pt(2))
    add_connector(slide, Inches(4.4), Inches(5.1), Inches(4.7), Inches(5.1), GREEN, Pt(2))
    add_connector(slide, Inches(5.5), Inches(5.1), Inches(5.6), Inches(5.1), GREEN, Pt(2))

    add_text_box(slide, Inches(0.5), Inches(5.6), Inches(5.5), Inches(0.3),
                 "Dallas DC \u2192 WAN \u2192 Phoenix DC \u2192 PH1 \u2192 GCP us-central1",
                 font_size=7, font_color=DARK_GRAY, bold=False)

    # ---- BOTTOM-RIGHT: GCP Region Failure ----
    br_x = Inches(6.8)
    br_y = Inches(4.2)
    add_shape_box(slide, br_x, br_y, quad_w, quad_h,
                  RGBColor(0xFF, 0xF0, 0xF0), "", border_color=RED, border_width=Pt(1.5),
                  shape_type=MSO_SHAPE.RECTANGLE)
    add_text_box(slide, Inches(7.0), Inches(4.3), Inches(4.5), Inches(0.3),
                 "GCP Region Failure (< 30 sec)", font_size=11, font_color=RED, bold=True)

    # Dallas DC
    add_shape_box(slide, Inches(7.1), Inches(4.8), Inches(1.3), Inches(0.6),
                  DARK_BLUE, "Dallas DC", font_size=8, font_color=WHITE, bold=True)
    # DA7
    add_shape_box(slide, Inches(8.8), Inches(4.8), Inches(1.0), Inches(0.6),
                  DARK_GRAY, "DA7", font_size=8, font_color=WHITE, bold=True)
    # GCP us-south1 (failed)
    add_shape_box(slide, Inches(10.2), Inches(4.8), Inches(2.0), Inches(0.6),
                  RED, "us-south1 \u2717", font_size=8, font_color=WHITE, bold=True)
    # GCP us-central1 (active)
    add_shape_box(slide, Inches(10.2), Inches(5.8), Inches(2.0), Inches(0.6),
                  GCP_GREEN, "us-central1 \u2713", font_size=8, font_color=WHITE, bold=True)

    add_connector(slide, Inches(8.4), Inches(5.1), Inches(8.8), Inches(5.1), DARK_GRAY, Pt(1.5))
    add_connector(slide, Inches(9.8), Inches(5.1), Inches(10.2), Inches(5.1), RED, Pt(2))
    # Redirect arrow down to us-central1
    add_connector(slide, Inches(9.8), Inches(5.1), Inches(10.2), Inches(6.1), GREEN, Pt(2.5))
    add_text_box(slide, Inches(7.5), Inches(6.5), Inches(4.5), Inches(0.3),
                 "Traffic redirects to GCP us-central1", font_size=8, font_color=GREEN, bold=True)

    return slide



# ============================================================
# MAIN: Build Presentation
# ============================================================
def main():
    """Generate the complete PowerPoint presentation."""
    prs = Presentation()

    # Set widescreen dimensions
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    print("Creating Slide 1: Title...")
    create_slide_1(prs)

    print("Creating Slide 2: Physical Network Topology...")
    create_slide_2(prs)

    print("Creating Slide 3: Voice Path Network Diagram...")
    create_slide_3(prs)

    print("Creating Slide 4: Data Path Network Diagram...")
    create_slide_4(prs)

    print("Creating Slide 5: GCP VPC & Security Architecture...")
    create_slide_5(prs)

    print("Creating Slide 6: High Availability & Failover...")
    create_slide_6(prs)

    # Save
    prs.save(OUTPUT_PATH)
    print(f"\nPresentation saved to: {OUTPUT_PATH}")
    print(f"Total slides: {len(prs.slides)}")


if __name__ == "__main__":
    main()

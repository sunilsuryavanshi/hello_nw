#!/usr/bin/env python3
"""
Generate Network Architecture PowerPoint Presentation
Output: Five9_Genesys_Bridge_Executive_v1.pptx
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

# Colors
DARK_BLUE = RGBColor(0x1B, 0x2A, 0x4A)
MEDIUM_BLUE = RGBColor(0x2C, 0x5F, 0x8A)
LIGHT_BLUE = RGBColor(0x4A, 0x90, 0xD9)
ORANGE = RGBColor(0xE8, 0x6C, 0x00)
GREEN = RGBColor(0x28, 0xA7, 0x45)
GCP_BLUE = RGBColor(0x42, 0x85, 0xF4)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF0, 0xF2, 0xF5)
DARK_GRAY = RGBColor(0x4A, 0x4A, 0x4A)

# Presentation setup
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)


def add_colored_box(slide, left, top, width, height, fill_color, text="",
                    font_size=12, font_color=WHITE, bold=False, border_color=None):
    """Add a colored rectangle with optional text."""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if border_color:
        shape.line.color.rgb = border_color
        shape.line.width = Pt(2)
    else:
        shape.line.fill.background()
    if text:
        tf = shape.text_frame
        tf.word_wrap = True
        tf.margin_left = Pt(6)
        tf.margin_right = Pt(6)
        tf.margin_top = Pt(4)
        tf.margin_bottom = Pt(4)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = text
        run.font.size = Pt(font_size)
        run.font.color.rgb = font_color
        run.font.bold = bold
        tf.paragraphs[0].space_before = Pt(0)
        tf.paragraphs[0].space_after = Pt(0)
    return shape


def add_text_box(slide, left, top, width, height, text, font_size=14,
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


def add_arrow_line(slide, start_left, start_top, end_left, end_top, color=DARK_GRAY, width=Pt(2)):
    """Add a connector line (arrow)."""
    connector = slide.shapes.add_connector(1, start_left, start_top, end_left, end_top)
    connector.line.color.rgb = color
    connector.line.width = width
    return connector


def set_slide_bg(slide, color):
    """Set slide background color."""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_slide_title(slide, title_text, subtitle_text=None):
    """Add a standard slide title bar."""
    # Title bar
    title_bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0), Inches(13.333), Inches(1.0)
    )
    title_bar.fill.solid()
    title_bar.fill.fore_color.rgb = DARK_BLUE
    title_bar.line.fill.background()
    tf = title_bar.text_frame
    tf.margin_left = Pt(30)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = title_text
    run.font.size = Pt(28)
    run.font.color.rgb = WHITE
    run.font.bold = True
    if subtitle_text:
        p2 = tf.add_paragraph()
        run2 = p2.add_run()
        run2.text = subtitle_text
        run2.font.size = Pt(14)
        run2.font.color.rgb = LIGHT_GRAY




# ============================================================
# SLIDE 1: Title Slide
# ============================================================
slide1 = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
set_slide_bg(slide1, DARK_BLUE)

# Main title
add_text_box(slide1, Inches(1), Inches(1.8), Inches(11.333), Inches(1.5),
             "Network Architecture: GCP Dedicated Interconnect",
             font_size=36, font_color=WHITE, bold=True, alignment=PP_ALIGN.CENTER)

# Subtitle
add_text_box(slide1, Inches(1), Inches(3.3), Inches(11.333), Inches(0.8),
             "Voice & Data Private Connectivity for Contact Center AI",
             font_size=22, font_color=LIGHT_BLUE, bold=False, alignment=PP_ALIGN.CENTER)

# Bottom info
add_text_box(slide1, Inches(1), Inches(4.5), Inches(11.333), Inches(0.6),
             "Dual DC (Dallas + Phoenix) | 99.99% SLA | < 80ms Voice Latency",
             font_size=16, font_color=LIGHT_GRAY, bold=False, alignment=PP_ALIGN.CENTER)

# Accent line
accent_line = slide1.shapes.add_shape(
    MSO_SHAPE.RECTANGLE, Inches(4), Inches(4.2), Inches(5.333), Pt(4)
)
accent_line.fill.solid()
accent_line.fill.fore_color.rgb = LIGHT_BLUE
accent_line.line.fill.background()

# Bottom bar
bottom_bar = slide1.shapes.add_shape(
    MSO_SHAPE.RECTANGLE, Inches(0), Inches(6.9), Inches(13.333), Inches(0.6)
)
bottom_bar.fill.solid()
bottom_bar.fill.fore_color.rgb = MEDIUM_BLUE
bottom_bar.line.fill.background()
tf = bottom_bar.text_frame
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
tf.margin_left = Pt(30)
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
run = p.add_run()
run.text = "Five9 IVR  |  GCP CCAI  |  Genesys Cloud Agent Desktop"
run.font.size = Pt(14)
run.font.color.rgb = WHITE

print("Slide 1: Title - Done")



# ============================================================
# SLIDE 2: Architecture Overview
# ============================================================
slide2 = prs.slides.add_slide(prs.slide_layouts[6])
set_slide_bg(slide2, WHITE)
add_slide_title(slide2, "Network Topology Overview")

# Define boxes for architecture components
# Row 1: Data Centers
add_colored_box(slide2, Inches(0.5), Inches(1.5), Inches(1.8), Inches(1.0),
                MEDIUM_BLUE, "Dallas DC\n(Primary)", font_size=11, font_color=WHITE, bold=True)
add_colored_box(slide2, Inches(0.5), Inches(3.0), Inches(1.8), Inches(1.0),
                MEDIUM_BLUE, "Phoenix DC\n(DR)", font_size=11, font_color=WHITE, bold=True)

# Equinix Facilities
add_colored_box(slide2, Inches(3.2), Inches(1.3), Inches(1.8), Inches(0.7),
                DARK_GRAY, "Equinix DA7", font_size=10, font_color=WHITE, bold=True)
add_colored_box(slide2, Inches(3.2), Inches(2.1), Inches(1.8), Inches(0.7),
                DARK_GRAY, "Equinix DA2", font_size=10, font_color=WHITE, bold=True)
add_colored_box(slide2, Inches(3.2), Inches(3.0), Inches(1.8), Inches(0.7),
                DARK_GRAY, "Equinix PH1", font_size=10, font_color=WHITE, bold=True)

# GCP Regions
add_colored_box(slide2, Inches(5.8), Inches(1.5), Inches(2.2), Inches(1.0),
                GCP_BLUE, "GCP\nus-south1\n(Dallas)", font_size=10, font_color=WHITE, bold=True)
add_colored_box(slide2, Inches(5.8), Inches(3.0), Inches(2.2), Inches(1.0),
                GCP_BLUE, "GCP\nus-central1\n(Iowa/DR)", font_size=10, font_color=WHITE, bold=True)

# Five9 Cloud
add_colored_box(slide2, Inches(9.0), Inches(2.0), Inches(2.0), Inches(1.2),
                ORANGE, "Five9\nCloud IVR", font_size=11, font_color=WHITE, bold=True)

# Genesys
add_colored_box(slide2, Inches(11.3), Inches(2.0), Inches(1.8), Inches(1.2),
                GREEN, "Genesys\nCloud CX", font_size=11, font_color=WHITE, bold=True)

# Connection labels
add_text_box(slide2, Inches(2.3), Inches(1.1), Inches(1.0), Inches(0.4),
             "10G", font_size=9, font_color=DARK_GRAY, bold=True)
add_text_box(slide2, Inches(4.9), Inches(1.1), Inches(1.2), Inches(0.4),
             "10G Dedicated", font_size=9, font_color=DARK_GRAY, bold=True)

# Legend
add_text_box(slide2, Inches(0.5), Inches(4.8), Inches(2.0), Inches(0.4),
             "Legend:", font_size=12, font_color=DARK_GRAY, bold=True)

# Voice path legend
voice_legend = slide2.shapes.add_shape(
    MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(5.2), Inches(0.8), Pt(12)
)
voice_legend.fill.solid()
voice_legend.fill.fore_color.rgb = ORANGE
voice_legend.line.fill.background()
add_text_box(slide2, Inches(1.4), Inches(5.1), Inches(2.0), Inches(0.4),
             "Voice Path (SIP/RTP)", font_size=10, font_color=DARK_GRAY)

# Data path legend
data_legend = slide2.shapes.add_shape(
    MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(5.6), Inches(0.8), Pt(12)
)
data_legend.fill.solid()
data_legend.fill.fore_color.rgb = LIGHT_BLUE
data_legend.line.fill.background()
add_text_box(slide2, Inches(1.4), Inches(5.5), Inches(2.0), Inches(0.4),
             "Data Path (HTTPS)", font_size=10, font_color=DARK_GRAY)

# Architecture notes
notes_text = ("• Dallas DC & Phoenix DC connect to Equinix meet-me rooms\n"
              "• 10 Gbps Dedicated Interconnect to GCP regions\n"
              "• Five9 IVR connects via GCP backbone\n"
              "• Genesys receives calls post-AI processing")
add_text_box(slide2, Inches(5.8), Inches(4.6), Inches(7.0), Inches(2.5),
             notes_text, font_size=11, font_color=DARK_GRAY)

print("Slide 2: Architecture Overview - Done")



# ============================================================
# SLIDE 3: GCP Region Selection
# ============================================================
slide3 = prs.slides.add_slide(prs.slide_layouts[6])
set_slide_bg(slide3, WHITE)
add_slide_title(slide3, "GCP Region Selection")

# Primary Region Box
add_colored_box(slide3, Inches(0.5), Inches(1.4), Inches(6.0), Inches(2.8),
                LIGHT_GRAY, "", border_color=GCP_BLUE)
add_text_box(slide3, Inches(0.8), Inches(1.5), Inches(5.5), Inches(0.5),
             "PRIMARY: us-south1 (Dallas)", font_size=18, font_color=GCP_BLUE, bold=True)
add_text_box(slide3, Inches(0.8), Inches(2.1), Inches(5.5), Inches(2.0),
             ("• Latency: < 2ms (same metro as Dallas DC)\n"
              "• Role: Primary CCAI processing\n"
              "• Interconnect: DA7 + DA2 (dual path)\n"
              "• Services: Dialogflow CX, Cloud Run,\n"
              "  Speech-to-Text, Text-to-Speech, Firestore"),
             font_size=13, font_color=DARK_GRAY)

# DR Region Box
add_colored_box(slide3, Inches(7.0), Inches(1.4), Inches(6.0), Inches(2.8),
                LIGHT_GRAY, "", border_color=MEDIUM_BLUE)
add_text_box(slide3, Inches(7.3), Inches(1.5), Inches(5.5), Inches(0.5),
             "DR: us-central1 (Iowa)", font_size=18, font_color=MEDIUM_BLUE, bold=True)
add_text_box(slide3, Inches(7.3), Inches(2.1), Inches(5.5), Inches(2.0),
             ("• Latency: 15-20ms from Phoenix DC\n"
              "• Role: Disaster Recovery\n"
              "• Interconnect: PH1 + PHX1 (dual path)\n"
              "• Services: Full CCAI stack (replicated)\n"
              "• Activation: < 30 second failover"),
             font_size=13, font_color=DARK_GRAY)

# Key Services Section
add_text_box(slide3, Inches(0.5), Inches(4.6), Inches(12.5), Inches(0.5),
             "Key GCP Services Available in Both Regions:", font_size=16, font_color=DARK_BLUE, bold=True)

services = [
    ("Dialogflow CX", GCP_BLUE),
    ("Cloud Run", GCP_BLUE),
    ("Speech-to-Text", GCP_BLUE),
    ("Text-to-Speech", GCP_BLUE),
    ("Firestore", GCP_BLUE),
    ("BigQuery", GCP_BLUE),
]
x_pos = 0.5
for svc, color in services:
    add_colored_box(slide3, Inches(x_pos), Inches(5.2), Inches(1.9), Inches(0.6),
                    color, svc, font_size=10, font_color=WHITE, bold=True)
    x_pos += 2.1

print("Slide 3: GCP Region Selection - Done")



# ============================================================
# SLIDE 4: Interconnect Design
# ============================================================
slide4 = prs.slides.add_slide(prs.slide_layouts[6])
set_slide_bg(slide4, WHITE)
add_slide_title(slide4, "Dedicated Interconnect: 99.99% Redundancy")

# 4 Connection boxes
connections = [
    ("DA7 (AT&T)", "Dallas Metro", "Primary Path A"),
    ("DA2 (Verizon)", "Dallas Metro", "Primary Path B"),
    ("PH1 (AT&T)", "Phoenix Metro", "DR Path A"),
    ("PHX1 (Verizon)", "Phoenix Metro", "DR Path B"),
]

y_pos = 1.4
for facility, metro, path_label in connections:
    # Facility box
    add_colored_box(slide4, Inches(0.5), Inches(y_pos), Inches(2.5), Inches(0.9),
                    DARK_GRAY, f"{facility}\n{metro}", font_size=11, font_color=WHITE, bold=True)
    # Arrow area - specs
    add_text_box(slide4, Inches(3.2), Inches(y_pos), Inches(4.0), Inches(0.9),
                 f"── 10 Gbps ──  VLAN 100 (Voice) + VLAN 200 (Data)  ──▶",
                 font_size=10, font_color=DARK_GRAY)
    # GCP target box
    region = "us-south1" if "DA" in facility else "us-central1"
    add_colored_box(slide4, Inches(7.5), Inches(y_pos), Inches(2.2), Inches(0.9),
                    GCP_BLUE, f"GCP\n{region}", font_size=11, font_color=WHITE, bold=True)
    # Path label
    add_text_box(slide4, Inches(10.0), Inches(y_pos + 0.1), Inches(2.5), Inches(0.5),
                 path_label, font_size=11, font_color=MEDIUM_BLUE, bold=True)
    y_pos += 1.2

# BGP & BFD Details
details_y = 6.0
add_text_box(slide4, Inches(0.5), Inches(details_y), Inches(12.5), Inches(1.0),
             ("BGP: Customer ASN 64512 ↔ Google ASN 16550  |  "
              "BFD Enabled (failover < 5 seconds)  |  "
              "MED-based primary/backup routing"),
             font_size=12, font_color=DARK_BLUE, bold=True, alignment=PP_ALIGN.CENTER)

print("Slide 4: Interconnect Design - Done")



# ============================================================
# SLIDE 5: Voice Path
# ============================================================
slide5 = prs.slides.add_slide(prs.slide_layouts[6])
set_slide_bg(slide5, WHITE)
add_slide_title(slide5, "Voice Path: On-Prem SBC → GCP CCAI → Genesys Agent")

# Flow boxes
flow_items = [
    ("PSTN\nInbound", DARK_GRAY, 0.3),
    ("Oracle\nSBC", MEDIUM_BLUE, 2.0),
    ("Dedicated\nInterconnect", DARK_GRAY, 3.7),
    ("GCP\nGTP/LB", GCP_BLUE, 5.5),
    ("Dialogflow\nCX (CCAI)", GCP_BLUE, 7.3),
    ("Return via\nInterconnect", DARK_GRAY, 9.2),
    ("Genesys\nAgent", GREEN, 11.0),
]

for label, color, x in flow_items:
    add_colored_box(slide5, Inches(x), Inches(2.0), Inches(1.6), Inches(1.0),
                    color, label, font_size=10, font_color=WHITE, bold=True)

# Arrows between boxes (text-based)
arrow_y = 2.3
for i in range(len(flow_items) - 1):
    x_start = flow_items[i][2] + 1.6
    add_text_box(slide5, Inches(x_start), Inches(arrow_y), Inches(0.4), Inches(0.4),
                 "→", font_size=18, font_color=ORANGE, bold=True)

# Key specifications
specs_text = ("Key Voice Path Specifications:\n\n"
              "• Protocol: SIP over TLS (Port 5061)\n"
              "• Media: SRTP (encrypted RTP)\n"
              "• Codec: G.711 μ-law (64 kbps)\n"
              "• Target Latency: < 80ms one-way\n"
              "• QoS: DSCP EF (46) for voice packets\n"
              "• Capacity: 500 concurrent sessions per SBC pair")
add_text_box(slide5, Inches(0.5), Inches(3.5), Inches(6.0), Inches(3.5),
             specs_text, font_size=12, font_color=DARK_GRAY)

# Voice quality box
add_colored_box(slide5, Inches(7.0), Inches(3.8), Inches(5.8), Inches(2.5),
                LIGHT_GRAY, "", border_color=ORANGE)
add_text_box(slide5, Inches(7.3), Inches(3.9), Inches(5.3), Inches(0.4),
             "Voice Quality Requirements", font_size=14, font_color=ORANGE, bold=True)
add_text_box(slide5, Inches(7.3), Inches(4.4), Inches(5.3), Inches(1.8),
             ("• MOS Score: > 4.0 target\n"
              "• Jitter: < 30ms\n"
              "• Packet Loss: < 1%\n"
              "• One-way Delay: < 80ms\n"
              "• Echo Cancellation: Enabled on SBC"),
             font_size=12, font_color=DARK_GRAY)

print("Slide 5: Voice Path - Done")



# ============================================================
# SLIDE 6: Data Path
# ============================================================
slide6 = prs.slides.add_slide(prs.slide_layouts[6])
set_slide_bg(slide6, WHITE)
add_slide_title(slide6, "Data Path: Genesys ORS → GCP Middleware (Private)")

# Flow boxes for data path
data_flow = [
    ("Genesys\nORS", GREEN, 0.5),
    ("Interconnect\n(data-vlan)", DARK_GRAY, 2.8),
    ("Private Service\nConnect", GCP_BLUE, 5.1),
    ("Cloud Run\nMiddleware", GCP_BLUE, 7.4),
    ("Firestore /\nBigQuery", GCP_BLUE, 9.8),
]

for label, color, x in data_flow:
    add_colored_box(slide6, Inches(x), Inches(1.8), Inches(2.0), Inches(1.0),
                    color, label, font_size=10, font_color=WHITE, bold=True)

# Arrows
for i in range(len(data_flow) - 1):
    x_start = data_flow[i][2] + 2.0
    add_text_box(slide6, Inches(x_start), Inches(2.0), Inches(0.8), Inches(0.5),
                 "──▶", font_size=14, font_color=LIGHT_BLUE, bold=True)

# Key points
key_points = ("Key Data Path Characteristics:\n\n"
              "• No Public IP addresses - fully private\n"
              "• Private Service Connect endpoint for GCP services\n"
              "• mTLS authentication between services\n"
              "• Target latency: < 50ms round-trip\n"
              "• VLAN 200 (data) separated from voice traffic\n"
              "• Cloud Armor WAF for API protection")
add_text_box(slide6, Inches(0.5), Inches(3.3), Inches(6.0), Inches(3.5),
             key_points, font_size=12, font_color=DARK_GRAY)

# Data flow details box
add_colored_box(slide6, Inches(7.0), Inches(3.5), Inches(5.8), Inches(3.0),
                LIGHT_GRAY, "", border_color=LIGHT_BLUE)
add_text_box(slide6, Inches(7.3), Inches(3.6), Inches(5.3), Inches(0.4),
             "Data Integration Patterns", font_size=14, font_color=MEDIUM_BLUE, bold=True)
add_text_box(slide6, Inches(7.3), Inches(4.1), Inches(5.3), Inches(2.2),
             ("• Screen Pop: ORS → Cloud Run → Agent Desktop\n"
              "  (Customer context in < 200ms)\n\n"
              "• Post-Call: Recording → GCS → BigQuery\n"
              "  (Analytics pipeline)\n\n"
              "• Real-time: CCAI hints → Genesys routing\n"
              "  (Intent-based call routing)"),
             font_size=11, font_color=DARK_GRAY)

print("Slide 6: Data Path - Done")



# ============================================================
# SLIDE 7: VPC & Security
# ============================================================
slide7 = prs.slides.add_slide(prs.slide_layouts[6])
set_slide_bg(slide7, WHITE)
add_slide_title(slide7, "GCP VPC Design & VPC Service Controls")

# VPC Service Controls Perimeter (outer box)
add_colored_box(slide7, Inches(0.3), Inches(1.3), Inches(8.5), Inches(5.8),
                WHITE, "", border_color=RGBColor(0xCC, 0x00, 0x00))
add_text_box(slide7, Inches(0.5), Inches(1.4), Inches(4.0), Inches(0.4),
             "VPC Service Controls Perimeter", font_size=12, font_color=RGBColor(0xCC, 0x00, 0x00), bold=True)

# VPC Box
add_colored_box(slide7, Inches(0.6), Inches(1.9), Inches(8.0), Inches(4.9),
                LIGHT_GRAY, "", border_color=MEDIUM_BLUE)
add_text_box(slide7, Inches(0.8), Inches(2.0), Inches(3.0), Inches(0.4),
             "VPC: ccai-prod-vpc", font_size=13, font_color=MEDIUM_BLUE, bold=True)

# Subnets
subnets = [
    ("voice-subnet\n10.100.0.0/24", ORANGE, 1.0, 2.6),
    ("data-subnet\n10.101.0.0/24", LIGHT_BLUE, 3.6, 2.6),
    ("ccai-subnet\n10.102.0.0/24", GCP_BLUE, 6.2, 2.6),
]
for label, color, x, y in subnets:
    add_colored_box(slide7, Inches(x), Inches(y), Inches(2.3), Inches(1.0),
                    color, label, font_size=11, font_color=WHITE, bold=True)

# Services in subnets
add_text_box(slide7, Inches(1.0), Inches(3.8), Inches(2.3), Inches(1.5),
             "• SBC Landing\n• Voice GW\n• RTP Processing",
             font_size=9, font_color=DARK_GRAY)
add_text_box(slide7, Inches(3.6), Inches(3.8), Inches(2.3), Inches(1.5),
             "• Cloud Run\n• API Gateway\n• PSC Endpoints",
             font_size=9, font_color=DARK_GRAY)
add_text_box(slide7, Inches(6.2), Inches(3.8), Inches(2.3), Inches(1.5),
             "• Dialogflow CX\n• STT/TTS\n• Firestore",
             font_size=9, font_color=DARK_GRAY)

# Firewall rules summary
add_text_box(slide7, Inches(0.8), Inches(5.5), Inches(7.5), Inches(1.0),
             "Firewall: Deny-all default | Allow voice: TCP 5061, UDP 16384-32767 | Allow data: TCP 443 only",
             font_size=10, font_color=DARK_GRAY)

# Security features (right panel)
add_colored_box(slide7, Inches(9.0), Inches(1.3), Inches(4.0), Inches(5.8),
                DARK_BLUE, "", border_color=DARK_BLUE)
add_text_box(slide7, Inches(9.2), Inches(1.5), Inches(3.6), Inches(0.4),
             "Security Controls", font_size=14, font_color=WHITE, bold=True)
security_items = ("✓ Private Google Access\n\n"
                  "✓ No Public IP addresses\n\n"
                  "✓ VPC Service Controls\n\n"
                  "✓ Cloud Armor WAF\n\n"
                  "✓ mTLS service mesh\n\n"
                  "✓ CMEK encryption\n\n"
                  "✓ Cloud Audit Logs\n\n"
                  "✓ DLP API integration")
add_text_box(slide7, Inches(9.2), Inches(2.1), Inches(3.6), Inches(4.8),
             security_items, font_size=12, font_color=WHITE)

print("Slide 7: VPC & Security - Done")



# ============================================================
# SLIDE 8: Latency Analysis
# ============================================================
slide8 = prs.slides.add_slide(prs.slide_layouts[6])
set_slide_bg(slide8, WHITE)
add_slide_title(slide8, "Latency Budget: Voice Path (< 80ms Target)")

# Latency segments
segments = [
    ("DC → Equinix", "< 1ms", 0.8, MEDIUM_BLUE),
    ("Equinix → GCP Edge", "1-2ms", 1.6, DARK_GRAY),
    ("GCP Internal Routing", "1-2ms", 2.4, GCP_BLUE),
    ("CCAI Processing", "50-100ms", 3.2, ORANGE),
    ("Return Path (GCP → DC)", "3-5ms", 4.0, MEDIUM_BLUE),
]

# Header
add_text_box(slide8, Inches(0.5), Inches(1.3), Inches(4.0), Inches(0.4),
             "Segment", font_size=13, font_color=DARK_BLUE, bold=True)
add_text_box(slide8, Inches(4.5), Inches(1.3), Inches(2.0), Inches(0.4),
             "Latency", font_size=13, font_color=DARK_BLUE, bold=True)
add_text_box(slide8, Inches(6.5), Inches(1.3), Inches(6.0), Inches(0.4),
             "Visual Budget", font_size=13, font_color=DARK_BLUE, bold=True)

for label, latency, y, color in segments:
    add_text_box(slide8, Inches(0.5), Inches(y), Inches(4.0), Inches(0.5),
                 label, font_size=12, font_color=DARK_GRAY)
    add_text_box(slide8, Inches(4.5), Inches(y), Inches(2.0), Inches(0.5),
                 latency, font_size=12, font_color=DARK_GRAY, bold=True)
    # Bar chart representation
    if "50-100" in latency:
        bar_width = 5.5
    elif "3-5" in latency:
        bar_width = 0.8
    elif "1-2" in latency:
        bar_width = 0.4
    else:
        bar_width = 0.2
    bar = slide8.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(6.5), Inches(y + 0.1), Inches(bar_width), Inches(0.3)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()

# Total line
add_text_box(slide8, Inches(0.5), Inches(5.0), Inches(4.0), Inches(0.5),
             "TOTAL (Typical)", font_size=14, font_color=DARK_BLUE, bold=True)
add_text_box(slide8, Inches(4.5), Inches(5.0), Inches(2.0), Inches(0.5),
             "60-80ms", font_size=14, font_color=DARK_BLUE, bold=True)

# Status badge
add_colored_box(slide8, Inches(6.5), Inches(4.9), Inches(3.0), Inches(0.6),
                GREEN, "✓ WITHIN TARGET", font_size=14, font_color=WHITE, bold=True)

# Notes
add_text_box(slide8, Inches(0.5), Inches(5.8), Inches(12.0), Inches(1.5),
             ("Notes:\n"
              "• CCAI processing is the dominant factor (50-100ms depending on complexity)\n"
              "• Network transport adds only 5-10ms total (benefit of Dedicated Interconnect)\n"
              "• Worst case with DR failover to us-central1: adds 15-20ms (still within 150ms budget)"),
             font_size=11, font_color=DARK_GRAY)

print("Slide 8: Latency Analysis - Done")



# ============================================================
# SLIDE 9: HA & Failover
# ============================================================
slide9 = prs.slides.add_slide(prs.slide_layouts[6])
set_slide_bg(slide9, WHITE)
add_slide_title(slide9, "High Availability & Disaster Recovery")

# 4 HA Layers
layers = [
    ("Layer 1: SBC HA", "< 3 seconds", "Active/Standby SBC pair\nAutomatic session preservation",
     MEDIUM_BLUE, 1.4),
    ("Layer 2: Interconnect", "< 5 seconds", "4x 10G links (2 per metro)\nBFD detection + BGP re-route",
     DARK_GRAY, 2.8),
    ("Layer 3: Geographic DR", "< 30 seconds", "Dallas → Phoenix failover\nDNS + BGP path change",
     GCP_BLUE, 4.2),
    ("Layer 4: GCP Region", "< 30 seconds", "us-south1 → us-central1\nCross-region load balancing",
     ORANGE, 5.6),
]

for title, rto, description, color, y in layers:
    # Layer title box
    add_colored_box(slide9, Inches(0.5), Inches(y), Inches(3.0), Inches(1.0),
                    color, title, font_size=12, font_color=WHITE, bold=True)
    # RTO badge
    add_colored_box(slide9, Inches(3.8), Inches(y + 0.15), Inches(1.8), Inches(0.7),
                    GREEN, rto, font_size=12, font_color=WHITE, bold=True)
    # Description
    add_text_box(slide9, Inches(6.0), Inches(y), Inches(5.5), Inches(1.0),
                 description, font_size=11, font_color=DARK_GRAY)

# Overall SLA box
add_colored_box(slide9, Inches(9.5), Inches(1.3), Inches(3.5), Inches(0.6),
                DARK_BLUE, "Combined SLA: 99.99%", font_size=13, font_color=WHITE, bold=True)

# Failover summary
add_text_box(slide9, Inches(0.5), Inches(6.8), Inches(12.5), Inches(0.5),
             "Zero single points of failure: Dual DC | Dual ISP | Dual GCP Region | Dual SBC",
             font_size=12, font_color=DARK_BLUE, bold=True, alignment=PP_ALIGN.CENTER)

print("Slide 9: HA & Failover - Done")



# ============================================================
# SLIDE 10: Cost & Timeline
# ============================================================
slide10 = prs.slides.add_slide(prs.slide_layouts[6])
set_slide_bg(slide10, WHITE)
add_slide_title(slide10, "Investment & Implementation Timeline")

# Cost Summary Section
add_text_box(slide10, Inches(0.5), Inches(1.3), Inches(6.0), Inches(0.5),
             "Monthly Recurring Cost", font_size=16, font_color=DARK_BLUE, bold=True)

cost_items = [
    ("Dedicated Interconnect (4x 10G)", "$10,953"),
    ("GCP Services (CCAI, Compute, Storage)", "$4,625"),
]

y = 1.9
for item, cost in cost_items:
    add_text_box(slide10, Inches(0.8), Inches(y), Inches(4.5), Inches(0.4),
                 item, font_size=12, font_color=DARK_GRAY)
    add_text_box(slide10, Inches(5.0), Inches(y), Inches(1.5), Inches(0.4),
                 cost, font_size=12, font_color=DARK_GRAY, bold=True)
    y += 0.4

# Total
add_colored_box(slide10, Inches(0.5), Inches(2.9), Inches(6.0), Inches(0.6),
                DARK_BLUE, "  Total Monthly:  ~$15,578/month", font_size=14, font_color=WHITE, bold=True)

# Timeline Section
add_text_box(slide10, Inches(0.5), Inches(3.8), Inches(12.0), Inches(0.5),
             "Implementation Timeline: 12 Weeks", font_size=16, font_color=DARK_BLUE, bold=True)

# Timeline phases as colored bars
phases = [
    ("Phase 1: Procurement", "Wk 1-4", "Cross-connects, LOAs, ISP circuits", MEDIUM_BLUE, 0, 4),
    ("Phase 2: GCP Infra", "Wk 3-6", "VPC, interconnect attach, Cloud Router", GCP_BLUE, 2, 4),
    ("Phase 3: Security", "Wk 5-7", "VPC-SC, firewall rules, mTLS, testing", ORANGE, 4, 3),
    ("Phase 4: Go-Live", "Wk 9-12", "Integration test, cutover, monitoring", GREEN, 8, 4),
]

bar_top = 4.5
for phase_name, weeks, desc, color, start_wk, duration_wk in phases:
    # Phase label
    add_text_box(slide10, Inches(0.5), Inches(bar_top), Inches(2.5), Inches(0.4),
                 phase_name, font_size=11, font_color=DARK_GRAY, bold=True)
    # Timeline bar (scaled: 12 weeks = 8 inches, starting at x=3.5)
    bar_x = 3.5 + (start_wk * 8.0 / 12.0)
    bar_w = duration_wk * 8.0 / 12.0
    add_colored_box(slide10, Inches(bar_x), Inches(bar_top), Inches(bar_w), Inches(0.4),
                    color, weeks, font_size=9, font_color=WHITE, bold=True)
    # Description
    add_text_box(slide10, Inches(bar_x), Inches(bar_top + 0.4), Inches(bar_w + 1.0), Inches(0.3),
                 desc, font_size=8, font_color=DARK_GRAY)
    bar_top += 0.8

# Week markers
add_text_box(slide10, Inches(3.5), Inches(7.0), Inches(8.0), Inches(0.3),
             "Wk1    Wk2    Wk3    Wk4    Wk5    Wk6    Wk7    Wk8    Wk9    Wk10   Wk11   Wk12",
             font_size=8, font_color=DARK_GRAY, alignment=PP_ALIGN.LEFT)

print("Slide 10: Cost & Timeline - Done")

# ============================================================
# SAVE PRESENTATION
# ============================================================
output_dir = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(output_dir, "Five9_Genesys_Bridge_Executive_v1.pptx")
prs.save(output_path)
print(f"\n{'='*60}")
print(f"Presentation saved successfully!")
print(f"Output: {output_path}")
print(f"Slides: {len(prs.slides)} slides")
print(f"Size: {prs.slide_width} x {prs.slide_height}")
print(f"{'='*60}")

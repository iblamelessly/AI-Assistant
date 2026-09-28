"""
Document Generator for JARVIS AI Assistant.
Generates publication-quality PowerPoint (.pptx), Word (.docx), and PDF (.pdf) documents
with professional typography, modern themes, card layouts, styled tables, and visual hierarchy.
"""

import os
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

# --- PowerPoint Imports ---
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# --- Word Imports ---
import docx
from docx.shared import Inches as DocxInches, Pt as DocxPt, RGBColor as DocxRGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

# --- PDF Imports ---
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.pdfgen import canvas


# Document Theme Color Palettes — 20 Professional Themes
THEMES = {
    # ── DARK THEMES ──────────────────────────────────────────────────────────
    "jarvis_dark": {
        "bg": (11, 15, 25),            # #0B0F19
        "card_bg": (18, 24, 38),       # #121826
        "primary": (0, 210, 255),      # #00D2FF (Cyan)
        "secondary": (129, 140, 248),  # #818CF8 (Indigo)
        "accent": (16, 185, 129),      # #10B981 (Emerald)
        "text_main": (241, 245, 249),  # #F1F5F9
        "text_muted": (148, 163, 184), # #94A3B8
        "border": (30, 41, 59),        # #1E293B
    },
    "midnight_blue": {
        "bg": (11, 17, 32),            # #0B1120
        "card_bg": (19, 28, 52),       # #131C34
        "primary": (29, 78, 216),      # #1D4ED8 (Royal blue)
        "secondary": (251, 191, 36),   # #FBBF24 (Gold)
        "accent": (99, 102, 241),      # #6366F1 (Violet)
        "text_main": (239, 246, 255),  # #EFF6FF
        "text_muted": (147, 197, 253), # #93C5FD
        "border": (30, 58, 138),       # #1E3A8A
    },
    "obsidian": {
        "bg": (17, 17, 17),            # #111111
        "card_bg": (28, 28, 30),       # #1C1C1E
        "primary": (108, 99, 255),     # #6C63FF (Violet)
        "secondary": (232, 121, 249),  # #E879F9 (Fuchsia)
        "accent": (251, 191, 36),      # #FBBF24 (Gold)
        "text_main": (245, 245, 247),  # #F5F5F7
        "text_muted": (174, 174, 178), # #AEAEB2
        "border": (44, 44, 46),        # #2C2C2E
    },
    "cyberpunk": {
        "bg": (13, 2, 33),             # #0D0221
        "card_bg": (22, 8, 50),        # #160832
        "primary": (225, 29, 72),      # #E11D48 (Hot pink)
        "secondary": (253, 224, 71),   # #FDE047 (Neon yellow)
        "accent": (0, 229, 255),       # #00E5FF (Electric cyan)
        "text_main": (255, 245, 255),  # #FFF5FF
        "text_muted": (216, 180, 254), # #D8B4FE
        "border": (76, 29, 149),       # #4C1D95
    },
    "aurora": {
        "bg": (5, 10, 8),              # #050A08
        "card_bg": (10, 20, 15),       # #0A140F
        "primary": (5, 150, 105),      # #059669 (Emerald)
        "secondary": (45, 212, 191),   # #2DD4BF (Teal)
        "accent": (163, 230, 53),      # #A3E635 (Lime)
        "text_main": (240, 253, 244),  # #F0FDF4
        "text_muted": (134, 239, 172), # #86EFAC
        "border": (6, 78, 59),         # #064E3B
    },
    "deep_space": {
        "bg": (6, 8, 15),              # #06080F
        "card_bg": (12, 15, 28),       # #0C0F1C
        "primary": (67, 56, 202),      # #4338CA (Indigo)
        "secondary": (103, 232, 249),  # #67E8F9 (Sky cyan)
        "accent": (167, 139, 250),     # #A78BFA (Purple)
        "text_main": (238, 242, 255),  # #EEF2FF
        "text_muted": (165, 180, 252), # #A5B4FC
        "border": (49, 46, 129),       # #312E81
    },
    "volcanic": {
        "bg": (22, 10, 0),             # #160A00
        "card_bg": (38, 18, 5),        # #261205
        "primary": (234, 88, 12),      # #EA580C (Burnt orange)
        "secondary": (252, 211, 77),   # #FCD34D (Flame gold)
        "accent": (239, 68, 68),       # #EF4444 (Red)
        "text_main": (255, 247, 237),  # #FFF7ED
        "text_muted": (253, 186, 116), # #FDBA74
        "border": (124, 45, 18),       # #7C2D12
    },
    # ── LIGHT / CLEAN THEMES ─────────────────────────────────────────────────
    "minimal_white": {
        "bg": (255, 255, 255),         # #FFFFFF
        "card_bg": (249, 250, 251),    # #F9FAFB
        "primary": (15, 23, 42),       # #0F172A (Charcoal)
        "secondary": (14, 165, 233),   # #0EA5E9 (Sky blue)
        "accent": (16, 185, 129),      # #10B981 (Teal)
        "text_main": (15, 23, 42),     # #0F172A
        "text_muted": (107, 114, 128), # #6B7280
        "border": (229, 231, 235),     # #E5E7EB
    },
    "soft_pearl": {
        "bg": (250, 249, 247),         # #FAF9F7
        "card_bg": (255, 255, 255),    # #FFFFFF
        "primary": (30, 41, 59),       # #1E293B (Dark navy)
        "secondary": (244, 63, 94),    # #F43F5E (Coral rose)
        "accent": (251, 146, 60),      # #FB923C (Warm orange)
        "text_main": (15, 23, 42),     # #0F172A
        "text_muted": (100, 116, 139), # #64748B
        "border": (226, 232, 240),     # #E2E8F0
    },
    "corporate_blue": {
        "bg": (255, 255, 255),         # #FFFFFF
        "card_bg": (239, 246, 255),    # #EFF6FF
        "primary": (30, 58, 95),       # #1E3A5F (Deep navy)
        "secondary": (37, 99, 235),    # #2563EB (Corporate blue)
        "accent": (6, 182, 212),       # #06B6D4 (Cyan)
        "text_main": (15, 23, 42),     # #0F172A
        "text_muted": (71, 85, 105),   # #475569
        "border": (191, 219, 254),     # #BFDBFE
    },
    "executive": {
        "bg": (255, 255, 255),         # #FFFFFF
        "card_bg": (248, 249, 250),    # #F8F9FA
        "primary": (30, 41, 59),       # #1E293B
        "secondary": (217, 119, 6),    # #D97706 (Amber gold)
        "accent": (13, 148, 136),      # #0D9488 (Teal)
        "text_main": (30, 41, 59),     # #1E293B
        "text_muted": (107, 114, 128), # #6B7280
        "border": (229, 231, 235),     # #E5E7EB
    },
    "modern_tech": {
        "bg": (248, 250, 252),         # #F8FAFC
        "card_bg": (255, 255, 255),    # #FFFFFF
        "primary": (15, 23, 42),       # #0F172A (Navy slate)
        "secondary": (2, 132, 199),    # #0284C7 (Electric cyan)
        "accent": (79, 70, 229),       # #4F46E5 (Indigo)
        "text_main": (15, 23, 42),     # #0F172A
        "text_muted": (100, 116, 139), # #64748B
        "border": (226, 232, 240),     # #E2E8F0
    },
    "arctic": {
        "bg": (239, 246, 255),         # #EFF6FF
        "card_bg": (255, 255, 255),    # #FFFFFF
        "primary": (30, 58, 95),       # #1E3A5F (Navy)
        "secondary": (6, 182, 212),    # #06B6D4 (Cyan)
        "accent": (56, 189, 248),      # #38BDF8 (Sky)
        "text_main": (15, 23, 42),     # #0F172A
        "text_muted": (71, 85, 105),   # #475569
        "border": (186, 230, 253),     # #BAE6FD
    },
    # ── CREATIVE / SIGNATURE THEMES ──────────────────────────────────────────
    "ocean_blue": {
        "bg": (12, 27, 46),            # #0C1B2E
        "card_bg": (17, 38, 64),       # #112640
        "primary": (3, 105, 161),      # #0369A1 (Ocean blue)
        "secondary": (34, 211, 238),   # #22D3EE (Aqua)
        "accent": (251, 191, 36),      # #FBBF24 (Gold)
        "text_main": (240, 249, 255),  # #F0F9FF
        "text_muted": (125, 211, 252), # #7DD3FC
        "border": (7, 89, 133),        # #075985
    },
    "forest": {
        "bg": (10, 31, 10),            # #0A1F0A
        "card_bg": (16, 42, 16),       # #102A10
        "primary": (22, 163, 74),      # #16A34A (Forest green)
        "secondary": (202, 138, 4),    # #CA8A04 (Gold)
        "accent": (45, 212, 191),      # #2DD4BF (Teal)
        "text_main": (240, 253, 244),  # #F0FDF4
        "text_muted": (134, 239, 172), # #86EFAC
        "border": (20, 83, 45),        # #14532D
    },
    "sunset": {
        "bg": (28, 10, 0),             # #1C0A00
        "card_bg": (44, 16, 5),        # #2C1005
        "primary": (220, 38, 38),      # #DC2626 (Crimson red)
        "secondary": (249, 115, 22),   # #F97316 (Orange)
        "accent": (251, 191, 36),      # #FBBF24 (Amber)
        "text_main": (255, 247, 237),  # #FFF7ED
        "text_muted": (253, 186, 116), # #FDBA74
        "border": (154, 52, 18),       # #9A3412
    },
    "royal_purple": {
        "bg": (18, 11, 31),            # #120B1F
        "card_bg": (30, 18, 52),       # #1E1234
        "primary": (124, 58, 237),     # #7C3AED (Violet)
        "secondary": (236, 72, 153),   # #EC4899 (Pink)
        "accent": (251, 191, 36),      # #FBBF24 (Gold)
        "text_main": (245, 243, 255),  # #F5F3FF
        "text_muted": (196, 181, 253), # #C4B5FD
        "border": (76, 29, 149),       # #4C1D95
    },
    "rose_gold": {
        "bg": (255, 240, 245),         # #FFF0F5
        "card_bg": (255, 255, 255),    # #FFFFFF
        "primary": (159, 18, 57),      # #9F1239 (Deep rose)
        "secondary": (217, 119, 6),    # #D97706 (Champagne gold)
        "accent": (236, 72, 153),      # #EC4899 (Pink)
        "text_main": (28, 10, 23),     # #1C0A17
        "text_muted": (161, 98, 132),  # #A16284
        "border": (251, 207, 232),     # #FBCFE8
    },
    "emerald_pro": {
        "bg": (6, 18, 17),             # #061211
        "card_bg": (10, 30, 28),       # #0A1E1C
        "primary": (13, 148, 136),     # #0D9488 (Teal)
        "secondary": (132, 204, 22),   # #84CC16 (Lime)
        "accent": (45, 212, 191),      # #2DD4BF (Aqua teal)
        "text_main": (240, 253, 250),  # #F0FDFA
        "text_muted": (94, 234, 212),  # #5EEAD4
        "border": (19, 78, 74),        # #134E4A
    },
    "monochrome": {
        "bg": (0, 0, 0),               # #000000
        "card_bg": (18, 18, 18),       # #121212
        "primary": (55, 65, 81),       # #374151 (Dark grey)
        "secondary": (107, 114, 128),  # #6B7280 (Grey)
        "accent": (209, 213, 219),     # #D1D5DB (Light grey)
        "text_main": (255, 255, 255),  # #FFFFFF
        "text_muted": (156, 163, 175), # #9CA3AF
        "border": (31, 41, 55),        # #1F2937
    },
    "cherry_blossom": {
        "bg": (255, 240, 245),         # #FFF0F5
        "card_bg": (255, 255, 255),    # #FFFFFF
        "primary": (159, 18, 57),      # #9F1239 (Deep cherry)
        "secondary": (236, 72, 153),   # #EC4899 (Blossom pink)
        "accent": (217, 119, 6),       # #D97706 (Warm gold)
        "text_main": (28, 10, 23),     # #1C0A17
        "text_muted": (190, 24, 93),   # #BE185D
        "border": (253, 164, 175),     # #FDA4AF
    },
}

# Natural language → theme_name alias map
THEME_ALIASES = {
    # jarvis_dark
    "dark": "jarvis_dark",          "jarvis": "jarvis_dark",       "ai": "jarvis_dark",
    "black": "jarvis_dark",         "teal": "jarvis_dark",
    # midnight_blue
    "midnight": "midnight_blue",    "midnight blue": "midnight_blue",
    "navy": "midnight_blue",        "dark blue": "midnight_blue",   "royal blue": "midnight_blue",
    # obsidian
    "obsidian": "obsidian",         "charcoal": "obsidian",        "violet": "obsidian",
    # cyberpunk
    "cyber": "cyberpunk",           "cyberpunk": "cyberpunk",      "neon": "cyberpunk",
    "glitch": "cyberpunk",          "purple": "cyberpunk",         "magenta": "cyberpunk",
    # aurora
    "aurora": "aurora",             "green": "aurora",             "emerald dark": "aurora",
    "dark green": "aurora",
    # deep_space
    "space": "deep_space",          "galaxy": "deep_space",        "deep space": "deep_space",
    "indigo": "deep_space",         "cosmos": "deep_space",
    # volcanic
    "volcanic": "volcanic",         "fire": "volcanic",            "lava": "volcanic",
    "orange": "volcanic",           "inferno": "volcanic",
    # minimal_white
    "white": "minimal_white",       "minimal": "minimal_white",    "clean": "minimal_white",
    "light": "minimal_white",       "simple": "minimal_white",     "plain": "minimal_white",
    # soft_pearl
    "cream": "soft_pearl",          "pearl": "soft_pearl",         "warm": "soft_pearl",
    "ivory": "soft_pearl",
    # corporate_blue
    "corporate": "corporate_blue",  "business": "corporate_blue",  "formal": "corporate_blue",
    "professional": "corporate_blue",
    # executive
    "gold": "executive",            "executive": "executive",      "luxury": "executive",
    "premium": "executive",         "elite": "executive",
    # modern_tech
    "tech": "modern_tech",          "modern": "modern_tech",       "slate": "modern_tech",
    "digital": "modern_tech",       "startup": "modern_tech",
    # arctic
    "arctic": "arctic",             "ice": "arctic",               "cool": "arctic",
    "winter": "arctic",             "frost": "arctic",
    # ocean_blue
    "ocean": "ocean_blue",          "blue": "ocean_blue",          "sea": "ocean_blue",
    "aqua": "ocean_blue",           "marine": "ocean_blue",        "nautical": "ocean_blue",
    # forest
    "forest": "forest",             "nature": "forest",            "jungle": "forest",
    "earth": "forest",
    # sunset
    "sunset": "sunset",             "red": "sunset",               "coral": "sunset",
    "dusk": "sunset",               "twilight": "sunset",
    # royal_purple
    "royal": "royal_purple",        "deep purple": "royal_purple", "majestic": "royal_purple",
    "regal": "royal_purple",        "grape": "royal_purple",
    # rose_gold
    "rose": "rose_gold",            "rose gold": "rose_gold",      "pink": "rose_gold",
    "blush": "rose_gold",           "feminine": "rose_gold",
    # emerald_pro
    "emerald": "emerald_pro",       "jade": "emerald_pro",         "lime": "emerald_pro",
    "mint": "emerald_pro",
    # monochrome
    "mono": "monochrome",           "monochrome": "monochrome",    "grey": "monochrome",
    "gray": "monochrome",           "grayscale": "monochrome",     "black and white": "monochrome",
    # cherry_blossom
    "cherry": "cherry_blossom",     "blossom": "cherry_blossom",   "sakura": "cherry_blossom",
    "floral": "cherry_blossom",
}

THEME_DISPLAY_NAMES = {
    "jarvis_dark":    "JARVIS Dark",       "midnight_blue":  "Midnight Blue",
    "obsidian":       "Obsidian",          "cyberpunk":      "Cyberpunk",
    "aurora":         "Aurora",            "deep_space":     "Deep Space",
    "volcanic":       "Volcanic",          "minimal_white":  "Minimal White",
    "soft_pearl":     "Soft Pearl",        "corporate_blue": "Corporate Blue",
    "executive":      "Executive Gold",    "modern_tech":    "Modern Tech",
    "arctic":         "Arctic",            "ocean_blue":     "Ocean Blue",
    "forest":         "Forest",            "sunset":         "Sunset",
    "royal_purple":   "Royal Purple",      "rose_gold":      "Rose Gold",
    "emerald_pro":    "Emerald Pro",       "monochrome":     "Monochrome",
    "cherry_blossom": "Cherry Blossom",
}


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas for dynamic total page number in PDFs."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748B"))
        # Footer text
        self.drawString(54, 32, "JARVIS Autonomous Document Intelligence")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 32, page_str)
        # Subtle divider
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 46, letter[0] - 54, 46)
        self.restoreState()


class DocumentGenerator:
    """Enterprise-grade document generator for PowerPoint, Word, and PDF."""

    def __init__(self):
        self.output_dir = Path(__file__).resolve().parent.parent / "documents" / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _clean_filename(self, title: str, extension: str) -> Path:
        slug = re.sub(r'[^a-zA-Z0-9_-]+', '_', title.lower()).strip('_')
        if not slug:
            slug = "document"
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return self.output_dir / f"{slug}_{timestamp}.{extension}"

    def _synthesize_content_structure(self, topic: str) -> Dict[str, Any]:
        """Synthesizes rich, structured outline when only a high-level topic is provided."""
        t_clean = topic.strip().title()

        return {
            "title": t_clean,
            "subtitle": f"Strategic Analysis, Principles & Implementation Framework",
            "author": "JARVIS Executive Intelligence",
            "date": time.strftime("%B %d, %Y"),
            "slides": [
                {
                    "type": "title",
                    "title": t_clean,
                    "subtitle": "Comprehensive Guide, Core Dimensions & Practical Application",
                    "badge": "EXECUTIVE BRIEFING"
                },
                {
                    "type": "agenda",
                    "title": "Executive Overview & Roadmap",
                    "subtitle": "Key thematic areas explored in this presentation",
                    "cards": [
                        {"tag": "PART 01", "heading": "Fundamental Foundations", "desc": f"Core definitions, essential ethics, and baseline philosophies governing {t_clean}."},
                        {"tag": "PART 02", "heading": "Core Pillars & Dimensions", "desc": "Key principles, structural frameworks, and operational values required for excellence."},
                        {"tag": "PART 03", "heading": "Strategic Implementation", "desc": "Practical workflows, daily habits, and systemic approaches to execution."},
                        {"tag": "PART 04", "heading": "Impact & Measurable Outcomes", "desc": "Assessing effectiveness, long-term societal benefits, and continuous improvement."}
                    ]
                },
                {
                    "type": "cards",
                    "title": "Core Pillars & Fundamental Dimensions",
                    "subtitle": "The foundational components driving success and integrity",
                    "cards": [
                        {
                            "tag": "Pillar 1",
                            "heading": "Integrity & Truthfulness",
                            "desc": "Unwavering commitment to honesty, ethical alignment, transparency, and accountability across all interactions."
                        },
                        {
                            "tag": "Pillar 2",
                            "heading": "Empathy & Compassion",
                            "desc": "Active listening, profound emotional intelligence, human-centric decision making, and shared mutual respect."
                        },
                        {
                            "tag": "Pillar 3",
                            "heading": "Excellence & Discipline",
                            "desc": "Relentless pursuit of quality, continuous personal growth, deliberate practice, and proactive responsibility."
                        }
                    ]
                },
                {
                    "type": "split",
                    "title": "Practical Execution & Daily Integration",
                    "subtitle": "Bridging abstract conceptual principles into concrete everyday action",
                    "left": {
                        "heading": "Guiding Philosophy",
                        "text": f"True mastery of {t_clean} does not emerge from passive theory. It demands daily proactive discipline, moral courage, and deliberate choices under pressure."
                    },
                    "bullets": [
                        ("Lead by Example", "Demonstrate principles consistently before expecting adherence from others."),
                        ("Structured Reflection", "Regularly audit actions and decisions against ethical guidelines and core standards."),
                        ("Open Communication", "Foster constructive, transparent dialogue where truth is respected and constructive feedback is welcomed."),
                        ("Resilience Under Pressure", "Uphold foundational values even during crises, deadlines, or conflicts.")
                    ]
                },
                {
                    "type": "metrics",
                    "title": "Measurable Impact & Key Benefits",
                    "subtitle": "Quantifiable positive outcomes observed when principles are systematically embedded",
                    "metrics": [
                        {"value": "94%", "label": "Trust & Cohesion", "caption": "Stronger collaboration and psychological safety across teams."},
                        {"value": "3.8x", "label": "Resilience Factor", "caption": "Significantly higher endurance through organizational challenges."},
                        {"value": "100%", "label": "Ethical Alignment", "caption": "Zero compromise on integrity and sustainable long-term value."}
                    ]
                },
                {
                    "type": "conclusion",
                    "title": "Conclusion & Strategic Summary",
                    "subtitle": "Key takeaways and next steps for long-term excellence",
                    "bullets": [
                        ("Internalize the Values", f"Embed {t_clean} into daily routines, decisions, and interactions."),
                        ("Foster Continuous Growth", "Seek opportunities to mentor, educate, and reinforce positive cultural standards."),
                        ("Measure What Matters", "Regularly reflect on personal and collective alignment with foundational goals.")
                    ]
                }
            ],
            "document_sections": [
                {
                    "heading": "1. Executive Summary",
                    "type": "callout",
                    "text": f"This document presents an authoritative exploration of {t_clean}. By synthesizing foundational principles, practical implementation methodologies, and measurable outcomes, it provides a comprehensive roadmap for individuals and organizations striving for excellence, ethical leadership, and sustainable success."
                },
                {
                    "heading": "2. Background & Strategic Context",
                    "type": "paragraphs",
                    "paragraphs": [
                        f"{t_clean} represents a critical cornerstone in modern leadership, personal development, and organizational harmony. In an increasingly complex and interconnected world, grounding decisions in clear, steadfast principles prevents drift, enhances trust, and accelerates achievement.",
                        "Without a deliberate framework, individuals and teams often fall prey to short-term thinking or compromise under pressure. Systematic adoption of these core dimensions provides both a moral compass and an operational catalyst."
                    ]
                },
                {
                    "heading": "3. Core Pillars Framework",
                    "type": "table",
                    "headers": ["Pillar", "Core Focus", "Actionable Behavior", "Impact Metric"],
                    "rows": [
                        ["Integrity", "Moral truthfulness and ethics", "Consistent transparency even when difficult", "Highest stakeholder trust"],
                        ["Empathy", "Understanding & human respect", "Active listening and compassionate inquiry", "Psychological safety"],
                        ["Discipline", "Focus and rigorous commitment", "Reliable execution and continuous practice", "Compounded excellence"],
                        ["Responsibility", "Ownership and accountability", "Owning outcomes without blame", "Proactive problem solving"]
                    ]
                },
                {
                    "heading": "4. Implementation Methodology",
                    "type": "bullets",
                    "bullets": [
                        ("Daily Value Audits", "Begin and conclude each day with a 5-minute self-assessment against core standards."),
                        ("Radical Transparency", "Communicate intent clearly, share context openly, and encourage candid questions."),
                        ("Empathetic Engagement", "Seek first to understand opposing viewpoints before seeking consensus."),
                        ("Sustained Practice", "Treat ethical values as muscles that strengthen through consistent daily application.")
                    ]
                },
                {
                    "heading": "5. Strategic Conclusion & Recommendations",
                    "type": "callout",
                    "text": f"Embracing {t_clean} is a lifelong commitment rather than a static milestone. By embedding these standards into our culture, decisions, and communications, we cultivate lasting leadership, trust, and enduring impact."
                }
            ]
        }

    # =========================================================================
    # 1. POWERPOINT PRESENTATION (.PPTX) GENERATOR
    # =========================================================================
    def create_presentation(self, topic: str, slides_data: Optional[List[Dict[str, Any]]] = None, theme_name: str = "jarvis_dark", output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a high-impact, widescreen 16:9 PowerPoint presentation.
        Features modern card layouts, badges, colored accents, and distinct slide formats.
        """
        prs = Presentation()
        # Set 16:9 widescreen slide dimensions
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        blank_slide_layout = prs.slide_layouts[6] # completely blank layout

        theme = THEMES.get(theme_name, THEMES["jarvis_dark"])
        color_bg = RGBColor(*theme["bg"])
        color_card = RGBColor(*theme["card_bg"])
        color_primary = RGBColor(*theme["primary"])
        color_secondary = RGBColor(*theme["secondary"])
        color_accent = RGBColor(*theme["accent"])
        color_text = RGBColor(*theme["text_main"])
        color_muted = RGBColor(*theme["text_muted"])
        color_border = RGBColor(*theme["border"])

        # Prepare content
        if not slides_data or len(slides_data) == 0:
            synthesized = self._synthesize_content_structure(topic)
            slides_list = synthesized["slides"]
            main_title = synthesized["title"]
        else:
            slides_list = slides_data
            main_title = topic.strip().title()

        def set_slide_background(slide):
            bg_shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
            bg_shape.fill.solid()
            bg_shape.fill.fore_color.rgb = color_bg
            bg_shape.line.fill.background()
            # Top subtle accent stripe
            top_stripe = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.08))
            top_stripe.fill.solid()
            top_stripe.fill.fore_color.rgb = color_primary
            top_stripe.line.fill.background()

        def add_slide_header(slide, title_text, subtitle_text=""):
            # Title
            title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.9))
            tf = title_box.text_frame
            tf.word_wrap = True
            tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
            p = tf.paragraphs[0]
            p.text = title_text
            p.font.size = Pt(28)
            p.font.bold = True
            p.font.color.rgb = color_text
            p.font.name = "Calibri"

            # Subtitle
            if subtitle_text:
                p2 = tf.add_paragraph()
                p2.text = subtitle_text
                p2.font.size = Pt(13)
                p2.font.color.rgb = color_muted
                p2.font.name = "Calibri"
                p2.space_before = Pt(4)

        # Loop through slide definitions
        for idx, sdata in enumerate(slides_list):
            slide = prs.slides.add_slide(blank_slide_layout)
            set_slide_background(slide)
            stype = sdata.get("type", "content")

            # --- Slide Type: Title Slide ---
            if stype == "title":
                # Large Card Container in center
                card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.2), Inches(1.3), Inches(10.9), Inches(4.9))
                card.fill.solid()
                card.fill.fore_color.rgb = color_card
                card.line.color.rgb = color_primary
                card.line.width = Pt(1.5)

                # Badge
                badge = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.8), Inches(1.9), Inches(2.2), Inches(0.42))
                badge.fill.solid()
                badge.fill.fore_color.rgb = color_primary
                badge.line.fill.background()
                btf = badge.text_frame
                bp = btf.paragraphs[0]
                bp.text = sdata.get("badge", "JARVIS PRESENTATION")
                bp.font.size = Pt(10)
                bp.font.bold = True
                bp.font.color.rgb = RGBColor(255, 255, 255)
                bp.font.name = "Calibri"
                bp.alignment = PP_ALIGN.CENTER

                # Title Text
                tb = slide.shapes.add_textbox(Inches(1.8), Inches(2.55), Inches(9.7), Inches(2.2))
                tf = tb.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = sdata.get("title", main_title)
                p.font.size = Pt(40)
                p.font.bold = True
                p.font.color.rgb = color_text
                p.font.name = "Calibri"

                p2 = tf.add_paragraph()
                p2.text = sdata.get("subtitle", "Autonomous Executive Briefing & Intelligence")
                p2.font.size = Pt(16)
                p2.font.color.rgb = color_muted
                p2.font.name = "Calibri"
                p2.space_before = Pt(12)

                # Metadata Footer inside card
                meta_tb = slide.shapes.add_textbox(Inches(1.8), Inches(5.1), Inches(9.7), Inches(0.5))
                mtf = meta_tb.text_frame
                mp = mtf.paragraphs[0]
                mp.text = f"Prepared by JARVIS AI  |  {time.strftime('%B %Y')}  |  Confidential"
                mp.font.size = Pt(11)
                mp.font.color.rgb = color_secondary
                mp.font.name = "Calibri"

            # --- Slide Type: Cards / Pillars ---
            elif stype in ["cards", "agenda"]:
                add_slide_header(slide, sdata.get("title", "Key Pillars"), sdata.get("subtitle", ""))
                cards = sdata.get("cards", [])
                card_count = min(len(cards), 4) or 1
                spacing = Inches(0.3)
                total_width = Inches(11.7)
                card_w = (total_width - (spacing * (card_count - 1))) / card_count
                card_h = Inches(4.5)
                start_x = Inches(0.8)
                start_y = Inches(1.8)

                for c_i, c in enumerate(cards[:4]):
                    cur_x = start_x + (c_i * (card_w + spacing))
                    # Card box
                    c_box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cur_x, start_y, card_w, card_h)
                    c_box.fill.solid()
                    c_box.fill.fore_color.rgb = color_card
                    c_box.line.color.rgb = color_border
                    c_box.line.width = Pt(1)

                    # Top accent tag inside card
                    tag_shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cur_x + Inches(0.3), start_y + Inches(0.3), Inches(1.3), Inches(0.36))
                    tag_shape.fill.solid()
                    tag_shape.fill.fore_color.rgb = color_primary if c_i % 2 == 0 else color_secondary
                    tag_shape.line.fill.background()
                    ttp = tag_shape.text_frame.paragraphs[0]
                    ttp.text = c.get("tag", f"0{c_i+1}")
                    ttp.font.size = Pt(10)
                    ttp.font.bold = True
                    ttp.font.color.rgb = RGBColor(255, 255, 255)
                    ttp.alignment = PP_ALIGN.CENTER

                    # Text inside card
                    c_tb = slide.shapes.add_textbox(cur_x + Inches(0.3), start_y + Inches(0.85), card_w - Inches(0.6), card_h - Inches(1.1))
                    ctf = c_tb.text_frame
                    ctf.word_wrap = True
                    # Heading
                    chp = ctf.paragraphs[0]
                    chp.text = c.get("heading", "")
                    chp.font.size = Pt(18)
                    chp.font.bold = True
                    chp.font.color.rgb = color_text
                    chp.font.name = "Calibri"

                    # Description
                    cdp = ctf.add_paragraph()
                    cdp.text = c.get("desc", "")
                    cdp.font.size = Pt(12)
                    cdp.font.color.rgb = color_muted
                    cdp.font.name = "Calibri"
                    cdp.space_before = Pt(12)

            # --- Slide Type: Split (Left feature card + Right bullets) ---
            elif stype == "split":
                add_slide_header(slide, sdata.get("title", "Strategic Execution"), sdata.get("subtitle", ""))

                # Left Focus Card
                left_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(4.5), Inches(4.6))
                left_card.fill.solid()
                left_card.fill.fore_color.rgb = color_card
                left_card.line.color.rgb = color_primary
                left_card.line.width = Pt(1.5)

                ltb = slide.shapes.add_textbox(Inches(1.2), Inches(2.2), Inches(3.7), Inches(3.8))
                ltf = ltb.text_frame
                ltf.word_wrap = True
                lp1 = ltf.paragraphs[0]
                left_info = sdata.get("left", {})
                lp1.text = left_info.get("heading", "Core Tenet")
                lp1.font.size = Pt(22)
                lp1.font.bold = True
                lp1.font.color.rgb = color_primary

                lp2 = ltf.add_paragraph()
                lp2.text = left_info.get("text", "")
                lp2.font.size = Pt(13)
                lp2.font.color.rgb = color_text
                lp2.space_before = Pt(14)

                # Right Bullet Points Container
                right_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(5.6), Inches(1.8), Inches(6.9), Inches(4.6))
                right_card.fill.solid()
                right_card.fill.fore_color.rgb = color_card
                right_card.line.color.rgb = color_border
                right_card.line.width = Pt(1)

                rtb = slide.shapes.add_textbox(Inches(6.0), Inches(2.1), Inches(6.1), Inches(4.0))
                rtf = rtb.text_frame
                rtf.word_wrap = True

                bullets = sdata.get("bullets", [])
                for b_i, b in enumerate(bullets):
                    bp = rtf.paragraphs[0] if b_i == 0 else rtf.add_paragraph()
                    if isinstance(b, tuple):
                        lead, text = b
                        bp.text = f"•  {lead}: "
                        run = bp.runs[0]
                        run.font.bold = True
                        run.font.color.rgb = color_accent
                        run.font.size = Pt(13)

                        run2 = bp.add_run()
                        run2.text = text
                        run2.font.color.rgb = color_text
                        run2.font.size = Pt(13)
                    else:
                        bp.text = f"•  {str(b)}"
                        bp.font.color.rgb = color_text
                        bp.font.size = Pt(13)
                    bp.space_before = Pt(10)

            # --- Slide Type: Metrics & Outcomes ---
            elif stype == "metrics":
                add_slide_header(slide, sdata.get("title", "Impact Metrics"), sdata.get("subtitle", ""))
                metrics = sdata.get("metrics", [])
                m_count = min(len(metrics), 3) or 1
                col_w = Inches(3.6)
                spacing = Inches(0.45)
                start_x = Inches(0.8)

                for m_i, m in enumerate(metrics[:3]):
                    cur_x = start_x + (m_i * (col_w + spacing))
                    m_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cur_x, Inches(2.0), col_w, Inches(4.2))
                    m_card.fill.solid()
                    m_card.fill.fore_color.rgb = color_card
                    m_card.line.color.rgb = color_primary if m_i == 0 else color_border
                    m_card.line.width = Pt(1.5 if m_i == 0 else 1)

                    tb = slide.shapes.add_textbox(cur_x + Inches(0.3), Inches(2.4), col_w - Inches(0.6), Inches(3.4))
                    mtf = tb.text_frame
                    mtf.word_wrap = True

                    vp = mtf.paragraphs[0]
                    vp.text = m.get("value", "100%")
                    vp.font.size = Pt(46)
                    vp.font.bold = True
                    vp.font.color.rgb = color_primary
                    vp.alignment = PP_ALIGN.CENTER

                    lp = mtf.add_paragraph()
                    lp.text = m.get("label", "")
                    lp.font.size = Pt(18)
                    lp.font.bold = True
                    lp.font.color.rgb = color_text
                    lp.space_before = Pt(8)
                    lp.alignment = PP_ALIGN.CENTER

                    cp = mtf.add_paragraph()
                    cp.text = m.get("caption", "")
                    cp.font.size = Pt(12)
                    cp.font.color.rgb = color_muted
                    cp.space_before = Pt(12)
                    cp.alignment = PP_ALIGN.CENTER

            # --- Slide Type: Default Content / Conclusion ---
            else:
                add_slide_header(slide, sdata.get("title", "Key Takeaways"), sdata.get("subtitle", ""))
                c_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(11.7), Inches(4.6))
                c_card.fill.solid()
                c_card.fill.fore_color.rgb = color_card
                c_card.line.color.rgb = color_border

                ctb = slide.shapes.add_textbox(Inches(1.2), Inches(2.2), Inches(10.9), Inches(3.8))
                ctf = ctb.text_frame
                ctf.word_wrap = True

                bullets = sdata.get("bullets", [])
                for b_i, b in enumerate(bullets):
                    bp = ctf.paragraphs[0] if b_i == 0 else ctf.add_paragraph()
                    if isinstance(b, tuple):
                        lead, text = b
                        bp.text = f"✔  {lead}: "
                        run = bp.runs[0]
                        run.font.bold = True
                        run.font.color.rgb = color_primary
                        run.font.size = Pt(14)

                        run2 = bp.add_run()
                        run2.text = text
                        run2.font.color.rgb = color_text
                        run2.font.size = Pt(14)
                    else:
                        bp.text = f"✔  {str(b)}"
                        bp.font.color.rgb = color_text
                        bp.font.size = Pt(14)
                    bp.space_before = Pt(14)

            # Footer on non-title slides
            if stype != "title":
                ftb = slide.shapes.add_textbox(Inches(0.8), Inches(6.8), Inches(11.7), Inches(0.4))
                ftf = ftb.text_frame
                fp = ftf.paragraphs[0]
                fp.text = f"{main_title}  |  Slide {idx+1} of {len(slides_list)}"
                fp.font.size = Pt(10)
                fp.font.color.rgb = color_muted

        # Save presentation
        save_target = Path(output_path) if output_path else self._clean_filename(main_title, "pptx")
        save_target.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(save_target))

        return {
            "success": True,
            "action": "create_presentation",
            "format": "pptx",
            "title": main_title,
            "slides_count": len(slides_list),
            "output_path": str(save_target.resolve()),
            "file_size": save_target.stat().st_size,
            "summary": f"Created professional 16:9 PowerPoint presentation: '{save_target.name}' with {len(slides_list)} high-impact slides."
        }

    # =========================================================================
    # 2. WORD DOCUMENT (.DOCX) GENERATOR
    # =========================================================================
    def create_document(self, title: str, sections: Optional[List[Dict[str, Any]]] = None, theme_name: str = "executive", output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a beautifully styled Word (.docx) document with custom headers,
        shaded callout boxes, styled data tables, and distinct typography.
        """
        doc = docx.Document()
        # Page Margins 1 inch
        for section in doc.sections:
            section.top_margin = DocxInches(1.0)
            section.bottom_margin = DocxInches(1.0)
            section.left_margin = DocxInches(1.0)
            section.right_margin = DocxInches(1.0)

        theme = THEMES.get(theme_name, THEMES["executive"])
        p_rgb = DocxRGBColor(*theme["primary"])
        s_rgb = DocxRGBColor(*theme["secondary"])
        m_rgb = DocxRGBColor(*theme["text_muted"])
        c_rgb = DocxRGBColor(*theme["accent"])

        # Prepare content
        if not sections or len(sections) == 0:
            synthesized = self._synthesize_content_structure(title)
            main_title = synthesized["title"]
            subtitle = synthesized["subtitle"]
            sections_list = synthesized["document_sections"]
        else:
            main_title = title.strip().title()
            subtitle = "Strategic Analysis & Practical Framework"
            sections_list = sections

        # Title Block
        title_p = doc.add_paragraph()
        title_run = title_p.add_run(main_title)
        title_run.font.size = DocxPt(26)
        title_run.font.bold = True
        title_run.font.color.rgb = p_rgb
        title_p.paragraph_format.space_after = DocxPt(4)

        # Subtitle
        sub_p = doc.add_paragraph()
        sub_run = sub_p.add_run(subtitle)
        sub_run.font.size = DocxPt(13)
        sub_run.font.color.rgb = s_rgb
        sub_p.paragraph_format.space_after = DocxPt(16)

        # Metadata Line
        meta_p = doc.add_paragraph()
        meta_run = meta_p.add_run(f"Author: JARVIS Autonomous Intelligence  •  Date: {time.strftime('%B %d, %Y')}")
        meta_run.font.size = DocxPt(10)
        meta_run.font.italic = True
        meta_run.font.color.rgb = m_rgb
        meta_p.paragraph_format.space_after = DocxPt(20)

        # Divider
        p_div = doc.add_paragraph()
        p_div_run = p_div.add_run("―" * 46)
        p_div_run.font.color.rgb = DocxRGBColor(203, 213, 225)
        p_div.paragraph_format.space_after = DocxPt(18)

        # Helper: Style cell shading in tables
        def set_cell_background(cell, hex_color):
            shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
            cell._tc.get_or_add_tcPr().append(shading)

        # Render sections
        for sec in sections_list:
            stype = sec.get("type", "paragraphs")
            heading_text = sec.get("heading", "")

            if heading_text:
                h = doc.add_paragraph()
                h_run = h.add_run(heading_text)
                h_run.font.size = DocxPt(16)
                h_run.font.bold = True
                h_run.font.color.rgb = p_rgb
                h.paragraph_format.space_before = DocxPt(18)
                h.paragraph_format.space_after = DocxPt(8)

            # Section: Callout Box (Single cell table with left border & shading)
            if stype == "callout":
                table = doc.add_table(rows=1, cols=1)
                table.alignment = WD_TABLE_ALIGNMENT.CENTER
                table.autofit = False
                cell = table.cell(0, 0)
                cell.width = DocxInches(6.5)
                set_cell_background(cell, "F1F5F9")

                # Left thick border XML
                tcPr = cell._tc.get_or_add_tcPr()
                borders = parse_xml(f'<w:tcBorders {nsdecls("w")}><w:left w:val="single" w:sz="24" w:space="0" w:color="0284C7"/><w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/></w:tcBorders>')
                tcPr.append(borders)

                cp = cell.paragraphs[0]
                cp.paragraph_format.left_indent = DocxInches(0.15)
                cp.paragraph_format.right_indent = DocxInches(0.15)
                cp.paragraph_format.space_before = DocxPt(8)
                cp.paragraph_format.space_after = DocxPt(8)
                c_run = cp.add_run(sec.get("text", ""))
                c_run.font.size = DocxPt(11)
                c_run.font.italic = True
                c_run.font.color.rgb = DocxRGBColor(51, 65, 85)

                doc.add_paragraph().paragraph_format.space_after = DocxPt(10)

            # Section: Table
            elif stype == "table":
                headers = sec.get("headers", [])
                rows = sec.get("rows", [])
                if headers and rows:
                    tbl = doc.add_table(rows=len(rows) + 1, cols=len(headers))
                    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
                    tbl.autofit = False

                    # Header Row
                    hdr_row = tbl.rows[0]
                    for idx, h_text in enumerate(headers):
                        c = hdr_row.cells[idx]
                        set_cell_background(c, "1E293B")
                        p = c.paragraphs[0]
                        p.paragraph_format.space_before = DocxPt(6)
                        p.paragraph_format.space_after = DocxPt(6)
                        r = p.add_run(str(h_text))
                        r.font.bold = True
                        r.font.size = DocxPt(10)
                        r.font.color.rgb = DocxRGBColor(255, 255, 255)

                    # Data Rows
                    for r_idx, row_vals in enumerate(rows):
                        row = tbl.rows[r_idx + 1]
                        row_bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
                        for c_idx, val in enumerate(row_vals):
                            if c_idx < len(row.cells):
                                c = row.cells[c_idx]
                                set_cell_background(c, row_bg)
                                p = c.paragraphs[0]
                                p.paragraph_format.space_before = DocxPt(4)
                                p.paragraph_format.space_after = DocxPt(4)
                                r = p.add_run(str(val))
                                r.font.size = DocxPt(9.5)
                                r.font.color.rgb = DocxRGBColor(30, 41, 59)

                    doc.add_paragraph().paragraph_format.space_after = DocxPt(12)

            # Section: Bullets
            elif stype == "bullets":
                bullets = sec.get("bullets", [])
                for b in bullets:
                    bp = doc.add_paragraph(style='List Bullet')
                    bp.paragraph_format.space_after = DocxPt(4)
                    if isinstance(b, tuple):
                        lead, text = b
                        r1 = bp.add_run(f"{lead}: ")
                        r1.font.bold = True
                        r1.font.color.rgb = p_rgb
                        r2 = bp.add_run(text)
                        r2.font.color.rgb = DocxRGBColor(51, 65, 85)
                    else:
                        bp.add_run(str(b))

            # Section: Regular Paragraphs
            else:
                for p_text in sec.get("paragraphs", []):
                    p = doc.add_paragraph()
                    p.paragraph_format.space_after = DocxPt(8)
                    p.paragraph_format.line_spacing = 1.15
                    run = p.add_run(p_text)
                    run.font.size = DocxPt(11)
                    run.font.color.rgb = DocxRGBColor(51, 65, 85)

        # Save document
        save_target = Path(output_path) if output_path else self._clean_filename(main_title, "docx")
        save_target.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(save_target))

        return {
            "success": True,
            "action": "create_document",
            "format": "docx",
            "title": main_title,
            "output_path": str(save_target.resolve()),
            "file_size": save_target.stat().st_size,
            "summary": f"Created professional Word document: '{save_target.name}' with formatted tables and executive styling."
        }

    # =========================================================================
    # 3. PDF REPORT (.PDF) GENERATOR
    # =========================================================================
    def create_pdf(self, title: str, sections: Optional[List[Dict[str, Any]]] = None, theme_name: str = "modern_tech", output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a publication-quality PDF report using ReportLab Platypus
        with custom palettes, formatted tables, colored callout boxes, and running footers.
        """
        save_target = Path(output_path) if output_path else self._clean_filename(title, "pdf")
        save_target.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(save_target),
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=60
        )

        theme = THEMES.get(theme_name, THEMES["modern_tech"])
        hex_primary = "#{:02x}{:02x}{:02x}".format(*theme["primary"])
        hex_secondary = "#{:02x}{:02x}{:02x}".format(*theme["secondary"])
        hex_accent = "#{:02x}{:02x}{:02x}".format(*theme["accent"])

        styles = getSampleStyleSheet()

        # Custom Styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=26,
            leading=30,
            textColor=colors.HexColor(hex_primary),
            spaceAfter=6
        )

        subtitle_style = ParagraphStyle(
            'CustomSubTitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor(hex_secondary),
            spaceAfter=14
        )

        meta_style = ParagraphStyle(
            'CustomMeta',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=16
        )

        h1_style = ParagraphStyle(
            'CustomH1',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=15,
            leading=19,
            textColor=colors.HexColor(hex_primary),
            spaceBefore=14,
            spaceAfter=8
        )

        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#334155"),
            spaceAfter=8
        )

        callout_style = ParagraphStyle(
            'CustomCallout',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1E293B")
        )

        table_hdr_style = ParagraphStyle(
            'CustomTblHdr',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9.5,
            leading=12,
            textColor=colors.white
        )

        table_cell_style = ParagraphStyle(
            'CustomTblCell',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1E293B")
        )

        story = []

        # Prepare Content
        if not sections or len(sections) == 0:
            synthesized = self._synthesize_content_structure(title)
            main_title = synthesized["title"]
            subtitle = synthesized["subtitle"]
            sections_list = synthesized["document_sections"]
        else:
            main_title = title.strip().title()
            subtitle = "Strategic Analysis & Practical Framework"
            sections_list = sections

        # Title Block
        story.append(Paragraph(main_title, title_style))
        story.append(Paragraph(subtitle, subtitle_style))
        story.append(Paragraph(f"Author: JARVIS Intelligence  •  Date: {time.strftime('%B %d, %Y')}  •  Status: Official", meta_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=14))

        # Render sections
        for sec in sections_list:
            stype = sec.get("type", "paragraphs")
            heading_text = sec.get("heading", "")

            if heading_text:
                story.append(Paragraph(heading_text, h1_style))

            if stype == "callout":
                callout_p = Paragraph(sec.get("text", ""), callout_style)
                tbl = Table([[callout_p]], colWidths=[letter[0] - 108])
                tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ('LINEBEFORE', (0, 0), (0, -1), 3.5, colors.HexColor(hex_secondary)),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 10))

            elif stype == "table":
                headers = sec.get("headers", [])
                rows = sec.get("rows", [])
                if headers and rows:
                    tbl_data = []
                    # Header row
                    hdr_row = [Paragraph(str(h), table_hdr_style) for h in headers]
                    tbl_data.append(hdr_row)
                    # Data rows
                    for r in rows:
                        row_cells = [Paragraph(str(val), table_cell_style) for val in r]
                        tbl_data.append(row_cells)

                    avail_w = letter[0] - 108
                    col_w = avail_w / len(headers)
                    t = Table(tbl_data, colWidths=[col_w] * len(headers))
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(hex_primary)),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('TOPPADDING', (0, 0), (-1, -1), 5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")])
                    ]))
                    story.append(t)
                    story.append(Spacer(1, 10))

            elif stype == "bullets":
                for b in sec.get("bullets", []):
                    if isinstance(b, tuple):
                        lead, text = b
                        b_text = f"<b>{lead}:</b> {text}"
                    else:
                        b_text = str(b)
                    story.append(Paragraph(f"• &nbsp; {b_text}", body_style))
                story.append(Spacer(1, 6))

            else:
                for p_text in sec.get("paragraphs", []):
                    story.append(Paragraph(p_text, body_style))
                story.append(Spacer(1, 6))

        # Build PDF with two-pass NumberedCanvas
        doc.build(story, canvasmaker=NumberedCanvas)

        return {
            "success": True,
            "action": "create_pdf",
            "format": "pdf",
            "title": main_title,
            "output_path": str(save_target.resolve()),
            "file_size": save_target.stat().st_size,
            "summary": f"Generated publication-quality PDF report: '{save_target.name}' with executive styling and dynamic page numbering."
        }


# Singleton document generator instance
document_generator = DocumentGenerator()

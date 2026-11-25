"""Render lesson Markdown content into well-formatted PDFs using ReportLab."""

import re
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    HRFlowable,
    ListFlowable,
    ListItem,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
    NextPageTemplate,
    PageBreak,
)
from reportlab.platypus.tableofcontents import TableOfContents

from apps.courses.models import Course

ACCENT = colors.HexColor("#3d59a1")
ACCENT_DARK = colors.HexColor("#24283b")
MUTED = colors.HexColor("#565f89")
CODE_BG = colors.HexColor("#f0f1f7")
CODE_BORDER = colors.HexColor("#c7cce0")
ZEBRA = colors.HexColor("#eef1fa")

_body_font = "Helvetica"
_body_bold = "Helvetica-Bold"
_mono_font = "Courier"

for font_path, family in (
    ((Path("C:/Windows/Fonts/tahoma.ttf"), "tahomabd.ttf"), "SLPBody"),
    ((Path("C:/Windows/Fonts/arial.ttf"), "arialbd.ttf"), "SLPBody"),
    ((Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), "DejaVuSans-Bold.ttf"), "SLPBody"),
):
    if font_path[0].exists():
        pdfmetrics.registerFont(TTFont("SLPBody", str(font_path[0])))
        bold_path = font_path[0].parent / font_path[1]
        if bold_path.exists():
            pdfmetrics.registerFont(TTFont("SLPBody-Bold", str(bold_path)))
            _body_font = "SLPBody"
            _body_bold = "SLPBody-Bold"
        break

for mono_path in (
    Path("C:/Windows/Fonts/consola.ttf"),
    Path("C:/Windows/Fonts/cour.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
):
    if mono_path.exists():
        pdfmetrics.registerFont(TTFont("SLPMono", str(mono_path)))
        _mono_font = "SLPMono"
        break


class _LessonStyles:
    def __init__(self):
        self.title = ParagraphStyle(
            "LessonPdfTitle",
            fontName=_body_bold,
            fontSize=20,
            leading=25,
            textColor=ACCENT_DARK,
            spaceAfter=2 * mm,
        )
        self.subtitle = ParagraphStyle(
            "LessonPdfSubtitle",
            fontName=_body_font,
            fontSize=10,
            leading=14,
            textColor=MUTED,
        )
        self.h2 = ParagraphStyle(
            "LessonPdfH2",
            fontName=_body_bold,
            fontSize=14,
            leading=18,
            textColor=ACCENT,
            spaceBefore=6 * mm,
            spaceAfter=2 * mm,
        )
        self.h3 = ParagraphStyle(
            "LessonPdfH3",
            fontName=_body_bold,
            fontSize=12,
            leading=16,
            textColor=ACCENT_DARK,
            spaceBefore=4 * mm,
            spaceAfter=1.5 * mm,
        )
        self.body = ParagraphStyle(
            "LessonPdfBody",
            fontName=_body_font,
            fontSize=10,
            leading=14.5,
            textColor=ACCENT_DARK,
            spaceAfter=2 * mm,
        )
        self.bullet = ParagraphStyle(
            "LessonPdfBullet",
            parent=self.body,
            leftIndent=6 * mm,
            bulletIndent=2 * mm,
            spaceAfter=1 * mm,
        )
        self.code = ParagraphStyle(
            "LessonPdfCode",
            fontName=_mono_font,
            fontSize=8.5,
            leading=11.5,
            textColor=ACCENT_DARK,
        )
        self.meta = ParagraphStyle(
            "LessonPdfMeta",
            fontName=_body_font,
            fontSize=9,
            leading=13,
            textColor=MUTED,
        )
        self.entry_title = ParagraphStyle(
            "LessonEntryTitle",
            fontName=_body_bold,
            fontSize=17,
            leading=22,
            textColor=ACCENT_DARK,
            spaceBefore=4 * mm,
        )
        self.cover_title = ParagraphStyle(
            "LessonPdfCoverTitle",
            fontName=_body_bold,
            fontSize=26,
            leading=32,
            textColor=ACCENT_DARK,
            alignment=TA_CENTER,
        )
        self.cover_meta = ParagraphStyle(
            "LessonPdfCoverMeta",
            fontName=_body_font,
            fontSize=11,
            leading=16,
            textColor=MUTED,
            alignment=TA_CENTER,
        )


STYLES = _LessonStyles()


def _inline(markdown_text: str) -> str:
    text = escape(markdown_text)
    placeholders = []

    def stash_code(match):
        placeholders.append(
            f'<font face="{_mono_font}" color="#a31515">{match.group(1)}</font>'
        )
        return f"@@CODE{len(placeholders) - 1}@@"

    text = re.sub(r"`([^`]+)`", stash_code, text)
    text = re.sub(r"\*\*([^*]+)\*\*", rf"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    for index, snippet in enumerate(placeholders):
        text = text.replace(f"@@CODE{index}@@", snippet)
    return text


def _code_block(code_text: str):
    pre = Preformatted(code_text.rstrip("\n"), STYLES.code)
    table = Table([[pre]], colWidths=[None])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, CODE_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return [Spacer(1, 1.5 * mm), table, Spacer(1, 2.5 * mm)]


def _list_item(text: str) -> ListItem:
    return ListItem(Paragraph(_inline(text), STYLES.bullet))


def parse_markdown(markdown_text: str, toc_lesson_titles=None):
    """Convert lesson Markdown into a list of ReportLab flowables."""
    flowables = []
    list_buffer = []

    def flush_list():
        nonlocal list_buffer
        if list_buffer:
            flowables.append(
                ListFlowable(list_buffer, bulletType="bullet", leftIndent=2 * mm)
            )
            list_buffer = []

    lines = markdown_text.split("\n")
    in_code = False
    code_lines = []
    code_lang = ""

    for line in lines:
        if in_code:
            if line.strip().startswith("```"):
                flowables.extend(_code_block("\n".join(code_lines)))
                in_code = False
                code_lines = []
            else:
                code_lines.append(line)
            continue
        if line.strip().startswith("```"):
            flush_list()
            in_code = True
            code_lang = line.strip()[3:].strip()
            continue

        heading = re.match(r"^(#{2,3})\s+(.*)$", line)
        bullet = re.match(r"^[-*]\s+(.*)$", line.strip())
        numbered = re.match(r"^(\d+)[.)]\s+(.*)$", line.strip())

        if heading:
            flush_list()
            level, title_text = len(heading.group(1)), heading.group(2)
            style = STYLES.h2 if level == 2 else STYLES.h3
            flowables.append(Paragraph(_inline(title_text), style))
            if level == 2:
                flowables.append(
                    HRFlowable(
                        width="100%",
                        thickness=0.6,
                        color=CODE_BORDER,
                        spaceAfter=2 * mm,
                    )
                )
        elif bullet:
            list_buffer.append(_list_item(bullet.group(1)))
        elif numbered:
            list_buffer.append(
                ListItem(Paragraph(_inline(numbered.group(2)), STYLES.bullet))
            )
        elif line.strip():
            flush_list()
            flowables.append(Paragraph(_inline(line.strip()), STYLES.body))
        else:
            flush_list()

    if in_code and code_lines:
        flowables.extend(_code_block("\n".join(code_lines)))
    flush_list()
    return flowables


class _LessonDocTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in (
            "LessonEntryTitle",
            "LessonPdfH2",
        ):
            level = 0 if flowable.style.name == "LessonEntryTitle" else 1
            text = flowable.getPlainText()
            self.notify("TOCEntry", (level, text, self.page))


def _header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(_body_font, 8)
    canvas.setFillColor(MUTED)
    width, height = doc.pagesize
    canvas.drawString(16 * mm, height - 10 * mm, doc.lesson_header)
    canvas.drawRightString(width - 16 * mm, height - 10 * mm, "Smart Learning Platform")
    canvas.setStrokeColor(CODE_BORDER)
    canvas.setLineWidth(0.4)
    canvas.line(16 * mm, height - 12 * mm, width - 16 * mm, height - 12 * mm)
    canvas.drawCentredString(width / 2, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _cover_footer(canvas, doc):
    pass


def lesson_story(lesson) -> list:
    styles = STYLES
    story = [
        Paragraph(
            f"Lesson {lesson.order}: {escape(lesson.title)}", styles.title
        ),
        Paragraph(
            escape(lesson.description) if lesson.description else "", styles.subtitle
        ),
        HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=4 * mm),
    ]
    story.extend(parse_markdown(lesson.content or ""))
    if lesson.duration_minutes:
        story.append(Spacer(1, 6 * mm))
        story.append(
            Paragraph(
                f"Estimated study time: {lesson.duration_minutes} minutes",
                styles.meta,
            )
        )
    return story


def _cover_story(course, lessons) -> list:
    total_minutes = sum(l.duration_minutes for l in lessons)
    story = [
        Spacer(1, 60 * mm),
        Paragraph(escape(course.title), STYLES.cover_title),
        Paragraph(f"{escape(course.code)} - Lesson Notes Pack", STYLES.cover_meta),
        Spacer(1, 8 * mm),
        Paragraph(
            f"{len(lessons)} lessons - "
            f"{total_minutes // 60}h {total_minutes % 60}m of study material",
            STYLES.cover_meta,
        ),
        NextPageTemplate("body"),
        PageBreak(),
        Paragraph("Table of Contents", STYLES.title),
        Spacer(1, 4 * mm),
    ]
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "TOCLesson",
            fontName=_body_bold,
            fontSize=11,
            leading=18,
            leftIndent=2 * mm,
        ),
        ParagraphStyle(
            "TOCSection",
            fontName=_body_font,
            fontSize=9.5,
            leading=14,
            leftIndent=10 * mm,
            textColor=MUTED,
        ),
    ]
    story.append(toc)
    return story


def _build_doc(buffer, story, course, footer_fn):
    doc = _LessonDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=f"{course.code} - Smart Learning Platform",
        author="Smart Learning Platform",
    )
    doc.lesson_header = f"{course.code} - {course.title}"
    cover_frame = Frame(
        16 * mm, 16 * mm, doc.width, doc.height, id="cover"
    )
    body_frame = Frame(
        16 * mm, 16 * mm, doc.width, doc.height, id="body"
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[cover_frame], onPage=footer_fn),
            PageTemplate(id="body", frames=[body_frame], onPage=footer_fn),
        ]
    )
    doc.multiBuild(story)


def render_lesson_pdf(lesson, buffer):
    """Render a single published lesson into its own PDF."""
    course = lesson.course
    story = lesson_story(lesson)
    _build_doc(buffer, story, course, _header_footer)


def render_course_pack_pdf(course, buffer):
    """Render one combined PDF containing the cover, TOC and every lesson."""
    lessons = list(
        course.lessons.filter(is_published=True).order_by("order")
    )
    story = _cover_story(course, lessons)
    for index, lesson in enumerate(lessons):
        story.append(Paragraph(escape(lesson.title), STYLES.entry_title))
        story.append(
            Paragraph(
                f"Lesson {lesson.order} - {escape(lesson.description or '')}",
                STYLES.subtitle,
            )
        )
        story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=4 * mm))
        story.extend(parse_markdown(lesson.content or ""))
        if index != len(lessons) - 1:
            story.append(PageBreak())
    _build_doc(buffer, story, course, _header_footer)

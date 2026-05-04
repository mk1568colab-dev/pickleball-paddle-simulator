"""Generate polished classroom infographic PNGs for the simulator guide.

The figures are intentionally generated from code so they stay reproducible.
The design system below keeps all eight images aligned to the same 16:9
classroom-slide layout: title area, main diagram, structured table/cards, and
bottom key lesson.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "documentation" / "figures" / "game_big_picture"

WIDTH = 1920
HEIGHT = 1080
MARGIN = 72
HEADER_TOP = 54
CONTENT_TOP = 190
FOOTER_TOP = 988


# Consistent classroom palette.
BG = "#fff8ed"
PAPER = "#ffffff"
INK = "#172033"
MUTED = "#59677b"
RULE = "#d8e0ea"
SHADOW = "#d1d9e6"

BLUE = "#2563eb"      # demand / forecast / information
GREEN = "#16a34a"     # operations / service / good outcome
ORANGE = "#d97706"    # supply / cost / warning
PURPLE = "#7c3aed"    # portfolio / innovation / pipeline
RED = "#dc2626"       # finance risk / defects / debt pressure
TEAL = "#0d9488"      # process / reputation / lifecycle

PALE = {
    BLUE: "#dbeafe",
    GREEN: "#dcfce7",
    ORANGE: "#fef3c7",
    PURPLE: "#ede9fe",
    RED: "#fee2e2",
    TEAL: "#ccfbf1",
}

BROWN = "#a16207"
BROWN_DARK = "#713f12"
BROWN_LIGHT = "#d6a15f"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Prefer Windows UI fonts, fall back cleanly if unavailable."""

    names = [
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "calibrib.ttf" if bold else "calibri.ttf",
    ]
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


TITLE = font(50, True)
SUBTITLE = font(25)
H1 = font(34, True)
H2 = font(27, True)
H3 = font(22, True)
BODY = font(19)
BODY_BOLD = font(19, True)
SMALL = font(16)
SMALL_BOLD = font(16, True)
TINY = font(13)
TINY_BOLD = font(13, True)
FORMULA = font(18)


def text_h(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text or "Ag", font=fnt)
    return bbox[3] - bbox[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for raw in text.split("\n"):
        words = raw.split()
        if not words:
            lines.append("")
            continue
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            if draw.textlength(test, font=fnt) <= max_w:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines


def draw_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    fnt: ImageFont.ImageFont,
    fill: str = INK,
    align: str = "left",
    gap: int = 4,
) -> int:
    x1, y1, x2, y2 = box
    y = y1
    max_w = max(20, x2 - x1)
    for line in wrap_text(draw, text, fnt, max_w):
        lh = text_h(draw, line, fnt)
        if y + lh > y2:
            break
        line_w = int(draw.textlength(line, font=fnt))
        if align == "center":
            x = x1 + (x2 - x1 - line_w) // 2
        elif align == "right":
            x = x2 - line_w
        else:
            x = x1
        draw.text((x, y), line, font=fnt, fill=fill)
        y += lh + gap
    return y


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    # Very subtle warm texture: enough to avoid flatness, not enough to distract.
    for x in range(-300, WIDTH + 300, 170):
        draw.line((x, 0, x - 250, HEIGHT), fill="#fbefd9", width=1)
    return image, draw


def rounded(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str = PAPER,
    outline: str = RULE,
    radius: int = 22,
    shadow: bool = True,
    width: int = 2,
) -> None:
    x1, y1, x2, y2 = box
    if shadow:
        draw.rounded_rectangle((x1 + 6, y1 + 7, x2 + 6, y2 + 7), radius=radius, fill=SHADOW)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def header(draw: ImageDraw.ImageDraw, number: int, title: str, subtitle: str, mode: str, color: str) -> None:
    draw.rounded_rectangle((MARGIN, HEADER_TOP, MARGIN + 24, HEADER_TOP + 86), radius=12, fill=color)
    draw.text((MARGIN + 52, HEADER_TOP - 2), f"Figure {number}. {title}", font=TITLE, fill=INK)
    draw_text(draw, subtitle, (MARGIN + 54, HEADER_TOP + 68, 1350, HEADER_TOP + 112), SUBTITLE, MUTED)
    rounded(draw, (1492, 58, 1848, 120), fill=PALE[color], outline=color, radius=18, shadow=False)
    draw_text(draw, mode.upper(), (1510, 78, 1830, 108), SMALL_BOLD, color, align="center")


def key_lesson(draw: ImageDraw.ImageDraw, text: str) -> None:
    rounded(draw, (MARGIN, FOOTER_TOP, WIDTH - MARGIN, 1040), fill=PAPER, outline="#b9c5d6", radius=18, shadow=True)
    draw.text((MARGIN + 28, FOOTER_TOP + 15), "Key lesson:", font=SMALL_BOLD, fill=INK)
    draw_text(draw, text, (MARGIN + 135, FOOTER_TOP + 15, WIDTH - MARGIN - 24, 1030), SMALL, MUTED)


def badge(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, color: str) -> None:
    rounded(draw, box, fill=PALE[color], outline=color, radius=18, shadow=False)
    draw_text(draw, text, (box[0] + 16, box[1] + 9, box[2] - 16, box[3] - 8), SMALL_BOLD, color, align="center")


def card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    body: str,
    color: str,
    fill: str | None = None,
    title_font: ImageFont.ImageFont = H3,
    body_font: ImageFont.ImageFont = SMALL,
) -> None:
    rounded(draw, box, fill=fill or PAPER, outline=color, radius=20, shadow=True, width=2)
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1, y1, x1 + 11, y2), radius=16, fill=color)
    title_bottom = draw_text(draw, title, (x1 + 24, y1 + 17, x2 - 20, y2 - 14), title_font, INK)
    # Keep card content visually balanced. If a card has only a little text,
    # place it near the vertical middle instead of leaving a large empty panel.
    body_lines = wrap_text(draw, body, body_font, max(20, x2 - x1 - 44))
    line_height = text_h(draw, "Ag", body_font) + 4
    estimated_body_h = max(0, len(body_lines) * line_height - 4)
    available_top = title_bottom + 5
    available_h = max(0, y2 - 16 - available_top)
    if estimated_body_h > 0 and estimated_body_h < available_h * 0.55:
        body_y = available_top + int((available_h - estimated_body_h) * 0.25)
    else:
        body_y = available_top
    draw_text(draw, body, (x1 + 24, body_y, x2 - 20, y2 - 16), body_font, MUTED)


def formula_box(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, formula: str) -> None:
    rounded(draw, box, fill="#eef5ff", outline="#93b5ff", radius=18, shadow=True)
    x1, y1, x2, y2 = box
    draw.text((x1 + 24, y1 + 18), title, font=BODY_BOLD, fill=BLUE)
    formula_font = SMALL if (y2 - y1) < 120 else FORMULA
    draw_text(draw, formula, (x1 + 24, y1 + 52, x2 - 24, y2 - 12), formula_font, INK, gap=4)


def numbered_step_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    number: str,
    title: str,
    body: str,
    color: str,
) -> None:
    rounded(draw, box, fill=PALE[color], outline=color, radius=20, shadow=True, width=2)
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1, y1, x1 + 11, y2), radius=16, fill=color)
    draw.ellipse((x1 + 22, y1 + 28, x1 + 72, y1 + 78), fill=color)
    draw_text(draw, number, (x1 + 22, y1 + 39, x1 + 72, y1 + 66), BODY_BOLD, PAPER, align="center")
    title_bottom = draw_text(draw, title, (x1 + 90, y1 + 25, x2 - 20, y1 + 62), H3, INK)
    body_lines = wrap_text(draw, body, SMALL, max(20, x2 - x1 - 110))
    line_height = text_h(draw, "Ag", SMALL) + 4
    estimated_body_h = max(0, len(body_lines) * line_height - 4)
    available_top = title_bottom + 4
    available_h = max(0, y2 - 16 - available_top)
    body_y = available_top + int((available_h - estimated_body_h) * 0.2) if estimated_body_h < available_h else available_top
    draw_text(draw, body, (x1 + 90, body_y, x2 - 20, y2 - 16), SMALL, MUTED)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str = INK, width: int = 4) -> None:
    draw.line((start, end), fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 17
    points = [
        end,
        (int(end[0] - size * math.cos(angle - 0.45)), int(end[1] - size * math.sin(angle - 0.45))),
        (int(end[0] - size * math.cos(angle + 0.45)), int(end[1] - size * math.sin(angle + 0.45))),
    ]
    draw.polygon(points, fill=color)


def elbow_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    mid: tuple[int, int],
    end: tuple[int, int],
    color: str,
    width: int = 4,
) -> None:
    draw.line((start, mid), fill=color, width=width)
    arrow(draw, mid, end, color=color, width=width)


def table(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    columns: Sequence[tuple[str, float]],
    rows: Sequence[Sequence[str]],
    accent: str,
    row_font: ImageFont.ImageFont = TINY,
) -> None:
    rounded(draw, box, fill=PAPER, outline=RULE, radius=18, shadow=True)
    x1, y1, x2, y2 = box
    header_h = 42
    usable_w = x2 - x1
    col_x = [x1]
    for _, frac in columns:
        col_x.append(col_x[-1] + int(usable_w * frac))
    col_x[-1] = x2
    draw.rounded_rectangle((x1, y1, x2, y1 + header_h), radius=18, fill=PALE[accent], outline=RULE)
    draw.rectangle((x1, y1 + header_h - 14, x2, y1 + header_h), fill=PALE[accent])
    for idx, (name, _) in enumerate(columns):
        draw_text(draw, name, (col_x[idx] + 12, y1 + 11, col_x[idx + 1] - 10, y1 + header_h - 5), TINY_BOLD, accent)
    row_h = max(22, int((y2 - y1 - header_h) / max(1, len(rows))))
    for r, row in enumerate(rows):
        top = y1 + header_h + r * row_h
        if top >= y2:
            break
        bottom = min(y2, top + row_h)
        if bottom <= top:
            continue
        fill = "#fbfdff" if r % 2 == 0 else PAPER
        draw.rectangle((x1, top, x2, bottom), fill=fill)
        draw.line((x1, top, x2, top), fill=RULE, width=1)
        for c, value in enumerate(row):
            draw_text(draw, str(value), (col_x[c] + 12, top + 7, col_x[c + 1] - 10, bottom - 5), row_font, INK)
    for cx in col_x[1:-1]:
        draw.line((cx, y1, cx, y2), fill=RULE, width=1)


def progress_bar(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], pct: float, color: str, label: str) -> None:
    x1, y1, x2, y2 = box
    rounded(draw, box, fill="#f8fafc", outline=RULE, radius=12, shadow=False)
    fill_w = int((x2 - x1) * max(0, min(1, pct)))
    if fill_w > 0:
        draw.rounded_rectangle((x1, y1, x1 + fill_w, y2), radius=12, fill=color)
    draw_text(draw, label, (x1 + 10, y1 + 5, x2 - 10, y2 - 4), TINY_BOLD, INK, align="center")


def mini_chip(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, color: str) -> None:
    rounded(draw, box, fill=PAPER, outline=color, radius=14, shadow=False, width=2)
    draw_text(draw, label, (box[0] + 10, box[1] + 8, box[2] - 10, box[3] - 6), TINY_BOLD, color, align="center")


def draw_checkmark(draw: ImageDraw.ImageDraw, center: tuple[int, int], color: str) -> None:
    cx, cy = center
    draw.ellipse((cx - 17, cy - 17, cx + 17, cy + 17), fill=color)
    draw.line((cx - 8, cy, cx - 2, cy + 7, cx + 10, cy - 9), fill=PAPER, width=4)


def dog(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    scale: float = 0.55,
    shirt: str = BLUE,
    accessory: str = "clipboard",
    facing: str = "right",
) -> None:
    """Small, consistent dachshund mascot used as support, not layout furniture."""

    s = scale
    flip = -1 if facing == "left" else 1
    body = (x, y, x + int(260 * s), y + int(78 * s))
    draw.rounded_rectangle(body, radius=int(40 * s), fill=BROWN_LIGHT, outline=BROWN_DARK, width=max(2, int(3 * s)))
    draw.rounded_rectangle((x + int(78 * s), y + int(15 * s), x + int(188 * s), y + int(76 * s)), radius=int(23 * s), fill=shirt)
    head_cx = x + (int(250 * s) if facing == "right" else int(8 * s))
    draw.ellipse((head_cx - int(40 * s), y - int(42 * s), head_cx + int(40 * s), y + int(34 * s)), fill=BROWN_LIGHT, outline=BROWN_DARK, width=max(1, int(2 * s)))
    snout_x = head_cx + flip * int(48 * s)
    draw.ellipse((snout_x - int(33 * s), y - int(15 * s), snout_x + int(33 * s), y + int(21 * s)), fill="#f2c37f", outline=BROWN_DARK, width=max(1, int(2 * s)))
    draw.ellipse((snout_x + flip * int(19 * s) - int(4 * s), y, snout_x + flip * int(19 * s) + int(4 * s), y + int(7 * s)), fill=INK)
    draw.ellipse((head_cx + flip * int(16 * s) - int(4 * s), y - int(20 * s), head_cx + flip * int(16 * s) + int(4 * s), y - int(12 * s)), fill=INK)
    ear_x = head_cx - flip * int(28 * s)
    draw.ellipse((ear_x - int(18 * s), y - int(35 * s), ear_x + int(18 * s), y + int(28 * s)), fill=BROWN, outline=BROWN_DARK, width=max(1, int(2 * s)))
    for lx in [x + int(45 * s), x + int(188 * s)]:
        draw.rounded_rectangle((lx, y + int(60 * s), lx + int(22 * s), y + int(112 * s)), radius=int(10 * s), fill=BROWN_LIGHT, outline=BROWN_DARK, width=1)
        draw.ellipse((lx - int(4 * s), y + int(104 * s), lx + int(33 * s), y + int(121 * s)), fill=BROWN_DARK)
    tail_start = (x + int(10 * s), y + int(18 * s)) if facing == "right" else (x + int(252 * s), y + int(18 * s))
    tail_end = (tail_start[0] - flip * int(55 * s), tail_start[1] - int(35 * s))
    draw.line((tail_start, tail_end), fill=BROWN_DARK, width=max(3, int(5 * s)))
    if accessory == "clipboard":
        bx, by = x + int(92 * s), y + int(20 * s)
        draw.rounded_rectangle((bx, by, bx + int(62 * s), by + int(82 * s)), radius=int(8 * s), fill=PAPER, outline=INK, width=1)
        for i in [28, 46]:
            draw.line((bx + int(12 * s), by + int(i * s), bx + int(51 * s), by + int(i * s)), fill=MUTED, width=1)
    elif accessory == "wrench":
        draw.line((x + int(102 * s), y + int(24 * s), x + int(158 * s), y + int(80 * s)), fill=INK, width=max(3, int(5 * s)))
        draw.ellipse((x + int(148 * s), y + int(70 * s), x + int(176 * s), y + int(98 * s)), outline=INK, width=max(2, int(4 * s)))
    elif accessory == "cash":
        draw.rectangle((x + int(95 * s), y + int(34 * s), x + int(168 * s), y + int(80 * s)), fill=PALE[GREEN], outline=GREEN, width=1)
        draw.text((x + int(119 * s), y + int(40 * s)), "$", font=font(max(13, int(23 * s)), True), fill=GREEN)
    elif accessory == "lab":
        draw.polygon(
            [
                (x + int(105 * s), y + int(25 * s)),
                (x + int(150 * s), y + int(25 * s)),
                (x + int(170 * s), y + int(90 * s)),
                (x + int(86 * s), y + int(90 * s)),
            ],
            fill=PALE[TEAL],
            outline=TEAL,
        )


def clean_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in OUTPUT_DIR.glob("*.png"):
        path.unlink()


def save(image: Image.Image, filename: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT_DIR / filename, "PNG")


def fig1_round_loop() -> None:
    image, draw = canvas()
    header(draw, 1, "The Round Loop", "The simulator repeats a business cycle: decide, compete, learn, then adjust.", "process", TEAL)
    steps = [
        ("1", "Read market report", "Demand level\nsegment mix\ncost, risk, tech", BLUE),
        ("2", "Submit decisions", "Forecasts\nproduction + sourcing\nportfolio + finance", GREEN),
        ("3", "Engine calculates", "Demand allocation\ncapacity/material caps\ncost, cash, debt", ORANGE),
        ("4", "Learn and adjust", "Review rankings\nexplain tradeoffs\nprepare next move", PURPLE),
    ]
    x0, y0, w, h, gap = 135, 260, 350, 160, 85
    centers: list[tuple[int, int]] = []
    for i, (num, title, body, color) in enumerate(steps):
        x = x0 + i * (w + gap)
        numbered_step_card(draw, (x, y0, x + w, y0 + h), num, title, body, color)
        centers.append((x + w // 2, y0 + h // 2))
        if i > 0:
            arrow(draw, (x - gap + 20, y0 + h // 2), (x - 12, y0 + h // 2), color=steps[i - 1][3], width=5)
    elbow_arrow(draw, (centers[-1][0], y0 + h + 15), (centers[-1][0], 505), (centers[0][0], 505), PURPLE, width=5)
    arrow(draw, (centers[0][0], 505), (centers[0][0], y0 + h + 10), PURPLE, width=5)
    dog(draw, 1510, 470, 0.62, shirt=PURPLE, accessory="clipboard", facing="left")
    table(
        draw,
        (180, 600, 1740, 865),
        [("What carries forward", 0.26), ("Meaning for next round", 0.74)],
        [
            ("Inventory / backlog", "Unsold units and unmet demand shape service pressure."),
            ("Capacity", "Expansion decisions increase future production ability."),
            ("Reputation", "Quality and fill rate affect future demand attractiveness."),
            ("Cash / debt", "Spending and borrowing change financial flexibility."),
            ("Product age / pipeline", "Products mature or decline; projects move toward launch."),
        ],
        TEAL,
        row_font=SMALL,
    )
    key_lesson(draw, "Each round is not isolated. The next decision starts from the operational, financial, and portfolio consequences of the previous one.")
    save(image, "Figure_1_The_Round_Loop.png")


def fig2_control_map() -> None:
    image, draw = canvas()
    header(draw, 2, "What Students Control", "Students manage connected decisions, not a single strategy label.", "dashboard map", BLUE)
    center = (720, 285, 1200, 465)
    rounded(draw, center, fill="#f8fbff", outline=BLUE, radius=28, shadow=True, width=3)
    draw_text(draw, "Team Decision System", (760, 320, 1160, 360), H2, INK, align="center")
    draw_text(draw, "Every input must fit the business model.", (770, 375, 1150, 418), SMALL, MUTED, align="center")
    dog(draw, 870, 495, 0.50, shirt=BLUE, accessory="clipboard")
    cards = [
        ((95, 225, 455, 345), "Demand", "forecast units\nselling price\ntarget segment", BLUE),
        ((95, 390, 455, 510), "Operations", "production plan\novertime + capacity\nQC spend", GREEN),
        ((95, 555, 455, 675), "Supply", "raw material order\nsupplier mix\nexpedite share", ORANGE),
        ((1465, 225, 1825, 345), "Portfolio", "Product A/B/C\nlifecycle stage\nretire / replace", PURPLE),
        ((1465, 390, 1825, 510), "Pipeline", "project investment\ntesting intensity\nlaunch timing", TEAL),
        ((1465, 555, 1825, 675), "Finance", "starting cash\nplanned borrowing\ndebt pressure", RED),
    ]
    for box, title, body, color in cards:
        card(draw, box, title, body, color, PALE[color])
        if box[0] < 500:
            arrow(draw, (box[2] + 16, (box[1] + box[3]) // 2), (center[0] - 12, (center[1] + center[3]) // 2), color, width=4)
        else:
            arrow(draw, (box[0] - 16, (box[1] + box[3]) // 2), (center[2] + 12, (center[1] + center[3]) // 2), color, width=4)
    table(
        draw,
        (165, 700, 1755, 945),
        [("Control Area", 0.18), ("Student Decisions", 0.42), ("Why It Matters", 0.40)],
        [
            ("Demand", "Forecast units, price, target segment", "Shapes expected sales and production plan."),
            ("Operations", "Production, overtime, QC, capacity expansion", "Sets feasible output, defects, and cost."),
            ("Supply", "Raw material order, supplier mix, expedite share", "Controls material cost, risk, and availability."),
            ("Portfolio", "Active products, retirement, lifecycle focus", "Determines what competes in the market."),
            ("Pipeline", "NPD investment, testing, launch decision", "Builds future products but uses cash today."),
            ("Finance", "Borrowing, cash pressure, debt discipline", "Limits growth if spending outruns liquidity."),
        ],
        BLUE,
        row_font=TINY,
    )
    key_lesson(draw, "Good performance comes from fit: forecast fits production, production fits capacity and materials, and growth fits cash.")
    save(image, "Figure_2_What_Students_Control.png")


def fig3_portfolio_pipeline() -> None:
    image, draw = canvas()
    header(draw, 3, "Portfolio and Pipeline", "Teams sell active products today while building future products for tomorrow.", "portfolio system", PURPLE)
    rounded(draw, (90, 220, 900, 720), fill="#fbfaff", outline=PURPLE, radius=26)
    draw_text(draw, "Active Portfolio", (125, 250, 520, 295), H2, INK)
    dog(draw, 650, 257, 0.42, shirt=PURPLE, accessory="clipboard")
    table(
        draw,
        (125, 330, 865, 655),
        [("Slot", 0.12), ("Product", 0.25), ("Segment", 0.20), ("Lifecycle", 0.20), ("Round Choice", 0.23)],
        [
            ("A", "Core paddle", "premium / mid", "launch-growth", "price, forecast, QC"),
            ("B", "Volume paddle", "mid / beginner", "growth-maturity", "production, target inventory"),
            ("C", "Backup slot", "any segment", "maturity-decline", "retire or replace"),
        ],
        PURPLE,
        row_font=SMALL,
    )
    rounded(draw, (1020, 220, 1830, 720), fill="#f8fffd", outline=TEAL, radius=26)
    draw_text(draw, "Development Pipeline", (1055, 250, 1500, 295), H2, INK)
    dog(draw, 1590, 257, 0.42, shirt=TEAL, accessory="lab", facing="left")
    project_y = [335, 475]
    for idx, y in enumerate(project_y, start=1):
        card(draw, (1060, y, 1790, y + 105), f"Project P{idx}", "Fixed concept; adjustable investment and testing.", TEAL, "#f0fdfa")
        progress_bar(draw, (1420, y + 62, 1745, y + 88), 0.35 if idx == 1 else 0.15, PURPLE, "readiness gate")
    badge(draw, (1140, 625, 1710, 675), "Pipeline launches only after all gates pass", PURPLE)
    checklist = [
        ("Funding ready", GREEN),
        ("Readiness ready", GREEN),
        ("Timing ready", ORANGE),
        ("Launch decision checked", PURPLE),
    ]
    y = 760
    for i, (txt, color) in enumerate(checklist):
        x = 260 + i * 365
        rounded(draw, (x, y, x + 300, y + 76), fill=PALE[color], outline=color, radius=18, shadow=True)
        draw_checkmark(draw, (x + 39, y + 38), color)
        draw_text(draw, txt, (x + 70, y + 25, x + 285, y + 55), SMALL_BOLD, INK)
    formula_box(draw, (365, 855, 1555, 942), "Launch rule", "can_launch = funding_ready AND readiness_ready AND timing_ready AND team_checks_launch_now")
    key_lesson(draw, "The portfolio earns today. The pipeline protects tomorrow, but only when investment, testing, timing, and launch decisions line up.")
    save(image, "Figure_3_Portfolio_and_Pipeline.png")


def fig4_demand_allocation() -> None:
    image, draw = canvas()
    header(draw, 4, "How Demand Is Allocated", "Market demand is shared across products using transparent attractiveness logic.", "calculation", BLUE)
    flow = [
        ((105, 245, 455, 405), "Market Segments", "Premium demand\nMid-market demand\nBeginner demand\nmarket report sets mix", ORANGE),
        ((1465, 245, 1815, 405), "Demand Share", "Each segment is split\nacross all products.\nHigher relative score\nwins more demand.", GREEN),
    ]
    for box, title, body, color in flow:
        card(draw, box, title, body, color, PALE[color])
    rounded(draw, (630, 220, 1290, 430), fill=PALE[BLUE], outline=BLUE, radius=20, shadow=True, width=2)
    draw.rounded_rectangle((630, 220, 641, 430), radius=16, fill=BLUE)
    draw_text(draw, "Product Attractiveness Score", (655, 244, 1268, 274), H3, INK)
    draw_text(draw, "Score combines seven simple demand signals:", (655, 282, 1268, 307), SMALL, MUTED)
    chips = [
        ("Price fit", BLUE),
        ("Quality", GREEN),
        ("Segment fit", PURPLE),
        ("Service", TEAL),
        ("Tech fit", ORANGE),
        ("Lifecycle", TEAL),
        ("Reputation", RED),
    ]
    chip_positions = [
        (655, 325, 805, 365),
        (825, 325, 975, 365),
        (995, 325, 1145, 365),
        (1165, 325, 1265, 365),
        (655, 378, 805, 418),
        (825, 378, 975, 418),
        (995, 378, 1145, 418),
    ]
    for (label, color), box in zip(chips, chip_positions):
        mini_chip(draw, box, label, color)
    arrow(draw, (470, 325), (615, 325), ORANGE, width=5)
    arrow(draw, (1305, 325), (1450, 325), GREEN, width=5)
    formula_box(
        draw,
        (190, 485, 1730, 610),
        "Core formula",
        "product_segment_demand = segment_demand * product_attractiveness / total_attractiveness_in_segment",
    )
    table(
        draw,
        (210, 665, 1710, 925),
        [("Factor", 0.22), ("Effect on Attractiveness", 0.78)],
        [
            ("Price", "Lower relative price helps, especially in beginner and price-sensitive markets."),
            ("Quality", "Higher QC and lower defect risk help, especially when customers are picky."),
            ("Service", "Inventory and feasible capacity improve fill rate and reduce lost sales."),
            ("Tech", "Products closer to or ahead of market generation get a demand bonus."),
            ("Lifecycle", "Launch/growth products get energy; decline products lose pull."),
            ("Reputation", "Past service and quality performance affect future demand allocation."),
        ],
        BLUE,
        row_font=SMALL,
    )
    key_lesson(draw, "Demand is not random. Products win demand when their price, quality, service, lifecycle, technology, and reputation fit the market.")
    save(image, "Figure_4_Demand_Allocation_Infographic.png")


def fig5_operations_cost() -> None:
    image, draw = canvas()
    header(draw, 5, "Operations and Cost Engine", "Production is constrained before it becomes sales, costs, and cash consequences.", "process flow", GREEN)
    steps = [
        ((100, 255, 370, 385), "Capacity + Overtime", "installed capacity\n+ overtime units\nsets output ceiling", GREEN),
        ((445, 255, 715, 385), "Materials", "beginning RM\n+ new orders\nsupplier risk matters", ORANGE),
        ((790, 255, 1060, 385), "Production Cap", "planned production\nis capped by\ncapacity and RM", PURPLE),
        ((100, 500, 370, 630), "Defects", "base defect rate\n+ supply stress\n- QC spending", RED),
        ((445, 500, 715, 630), "Good Units", "good output =\nproduction x\n(1 - defects)", GREEN),
        ((790, 500, 1060, 630), "Sales Service", "sales = min\nallocated demand,\navailable units", TEAL),
    ]
    for box, title, body, color in steps:
        card(draw, box, title, body, color, PALE[color])
    arrow(draw, (370, 320), (445, 320), GREEN, width=5)
    arrow(draw, (715, 320), (790, 320), ORANGE, width=5)
    elbow_arrow(draw, (925, 385), (925, 450), (235, 500), RED, width=5)
    arrow(draw, (370, 565), (445, 565), GREEN, width=5)
    arrow(draw, (715, 565), (790, 565), TEAL, width=5)
    table(
        draw,
        (1160, 225, 1810, 735),
        [("Cost Type", 0.32), ("Main Driver", 0.68)],
        [
            ("Procurement", "raw materials and supplier mix"),
            ("Production", "units produced and conversion cost"),
            ("QC", "quality budget per unit"),
            ("Holding", "leftover finished goods inventory"),
            ("Warranty", "defect rate and units sold"),
            ("Backlog", "unmet demand held for later"),
            ("Expansion", "added future capacity"),
            ("NPD", "development investment"),
            ("Interest", "short-term debt balance"),
        ],
        ORANGE,
    )
    formula_box(
        draw,
        (160, 765, 1760, 925),
        "Financial outcome",
        "total_cost = procurement + production + QC + holding + warranty + backlog + expansion + NPD + interest\nprofit = revenue - total_cost",
    )
    dog(draw, 300, 690, 0.48, shirt=GREEN, accessory="wrench")
    key_lesson(draw, "Operational feasibility comes first: capacity, materials, defects, inventory, and service create the financial outcome.")
    save(image, "Figure_5_Operations_and_Cost_Engine.png")


def fig6_forecasting_sop() -> None:
    image, draw = canvas()
    header(draw, 6, "Forecasting and S&OP", "Forecasts do not create demand; they discipline the operating plan.", "planning feedback", BLUE)
    rounded(draw, (105, 245, 555, 710), fill=PAPER, outline=BLUE, radius=24, shadow=True)
    draw_text(draw, "Forecast Board", (145, 275, 515, 315), H2, INK, align="center")
    # Chart.
    x1, y1, x2, y2 = 175, 400, 490, 620
    draw.line((x1, y2, x2, y2), fill=INK, width=3)
    draw.line((x1, y1, x1, y2), fill=INK, width=3)
    draw.line([(190, 585), (245, 540), (300, 555), (360, 485), (470, 520)], fill=BLUE, width=5)
    draw.line([(190, 560), (245, 565), (300, 515), (360, 530), (470, 455)], fill=GREEN, width=5)
    badge(draw, (175, 645, 315, 686), "forecast", BLUE)
    badge(draw, (335, 645, 475, 686), "actual", GREEN)
    dog(draw, 115, 720, 0.44, shirt=BLUE, accessory="clipboard")
    cards = [
        ((670, 245, 1125, 345), "Forecast inputs", "expected demand\nby active product", BLUE),
        ((670, 375, 1125, 475), "Production plan", "planned units\nby product slot", GREEN),
        ((670, 505, 1125, 605), "Material + capacity plan", "raw materials\novertime\nexpansion", ORANGE),
        ((670, 635, 1125, 735), "Cash plan", "borrowing choice\nliquidity check", RED),
    ]
    for box, title, body, color in cards:
        card(draw, box, title, body, color, PALE[color])
    for i in range(len(cards) - 1):
        arrow(draw, ((cards[i][0][0] + cards[i][0][2]) // 2, cards[i][0][3]), ((cards[i + 1][0][0] + cards[i + 1][0][2]) // 2, cards[i + 1][0][1] - 8), cards[i][3], width=4)
    rounded(draw, (1320, 270, 1810, 615), fill=PALE[PURPLE], outline=PURPLE, radius=20, shadow=True, width=2)
    draw.rounded_rectangle((1320, 270, 1331, 615), radius=16, fill=PURPLE)
    draw_text(draw, "After-Round Metrics", (1348, 300, 1785, 336), H2, INK)
    metric_rows = [
        ("Forecast error", "actual - forecast"),
        ("Absolute error", "size of miss"),
        ("Bias", "over / under habit"),
        ("WAPE", "portfolio accuracy"),
        ("Service gap", "unmet demand"),
    ]
    for i, (metric, meaning) in enumerate(metric_rows):
        top = 365 + i * 43
        rounded(draw, (1348, top, 1782, top + 34), fill=PAPER, outline="#d7c9ff", radius=12, shadow=False, width=1)
        draw_text(draw, metric, (1362, top + 8, 1515, top + 28), TINY_BOLD, PURPLE)
        draw_text(draw, meaning, (1530, top + 8, 1768, top + 28), TINY, MUTED)
    arrow(draw, (1128, 490), (1305, 445), PURPLE, width=5)
    formula_box(
        draw,
        (315, 795, 1605, 930),
        "Forecast accuracy formulas",
        "forecast_error = actual_demand - forecast\nabsolute_error = abs(actual_demand - forecast)\nteam_WAPE = sum(abs(actual - forecast)) / max(sum(actual), 1)",
    )
    key_lesson(draw, "Forecasting matters because bad plans create inventory, stockouts, debt, and service failures.")
    save(image, "Figure_6_Forecasting_and_SOP.png")


def fig7_cash_debt() -> None:
    image, draw = canvas()
    header(draw, 7, "Cash and Debt Pressure", "Profit and cash are related, but they are not the same managerial signal.", "finance bridge", RED)
    bridge = [
        ("Starting Cash", "cash carried in", BLUE),
        ("+ Revenue", "units sold x price", GREEN),
        ("- Costs", "materials + production", ORANGE),
        ("- Expansion", "capacity investment", PURPLE),
        ("- NPD", "future products", TEAL),
        ("- Interest", "debt charge", RED),
        ("= Cash Before Borrowing", "liquidity check", BLUE),
    ]
    x, y = 105, 255
    for i, (txt, body, color) in enumerate(bridge):
        box = (x + i * 252, y, x + i * 252 + 215, y + 100)
        card(draw, box, txt, body, color, PALE[color], BODY_BOLD, TINY)
        if i < len(bridge) - 1:
            arrow(draw, (box[2] + 8, y + 50), (box[2] + 35, y + 50), color, width=4)
    formula_box(
        draw,
        (160, 430, 1180, 585),
        "Cash bridge formula",
        "ending_cash_before_borrowing = starting_cash + revenue - costs - expansion - NPD - interest",
    )
    card(draw, (1250, 430, 1810, 585), "Debt rule", "If cash goes below zero,\nthe simulator creates\nshort-term debt for the\ncash shortfall.", RED, PALE[RED], H2, BODY)
    rounded(draw, (250, 660, 760, 860), fill="#f0fdf4", outline=GREEN, radius=24)
    draw_text(draw, "Debt / Liquidity Meter", (295, 690, 720, 730), H2, INK, align="center")
    for i, color in enumerate([GREEN, ORANGE, RED]):
        draw.rectangle((340 + i * 95, 770, 410 + i * 95, 825), fill=color)
    draw.line((525, 832, 610, 742), fill=INK, width=7)
    draw.ellipse((595, 728, 630, 763), fill=INK)
    table(
        draw,
        (880, 655, 1705, 875),
        [("Good Sign", 0.50), ("Warning Sign", 0.50)],
        [
            ("positive cash", "negative cash"),
            ("low debt", "rising debt"),
            ("profit with liquidity", "profit but cash shortage"),
            ("funded growth", "growth funded by emergency borrowing"),
        ],
        RED,
        row_font=SMALL,
    )
    dog(draw, 90, 710, 0.48, shirt=RED, accessory="cash")
    key_lesson(draw, "A team can sell a lot and still be in trouble if inventory, defects, expansion, or NPD spending drains cash.")
    save(image, "Figure_7_Cash_and_Debt_Pressure.png")


def fig8_strategy_archetypes() -> None:
    image, draw = canvas()
    header(draw, 8, "Strategy Archetypes", "Different strategies win in different environments and under different scoring priorities.", "comparison", PURPLE)
    strategies = [
        ("Cash Conservative", "Cash crunch / supply shock", "Misses upside", "cash, low debt", BLUE, "cash"),
        ("Balanced S&OP", "Forecast volatility", "Too cautious", "forecast-plan fit", GREEN, "clipboard"),
        ("Premium Quality", "Picky customers", "High cost", "QC, reputation", ORANGE, "clipboard"),
        ("Innovation Leap", "Tech shift", "Late payoff", "NPD, Gen advantage", PURPLE, "lab"),
        ("Aggressive Growth", "Demand boom", "Debt stress", "capacity, volume", RED, "wrench"),
        ("Low-Cost Volume", "Price war / beginner boom", "Weak margin", "low cost, scale", TEAL, "cash"),
    ]
    x_positions = [95, 685, 1275]
    y_positions = [225, 545]
    for i, (name, env, risk, focus, color, accessory) in enumerate(strategies):
        x = x_positions[i % 3]
        y = y_positions[i // 3]
        rounded(draw, (x, y, x + 550, y + 250), fill=PAPER, outline=color, radius=24, shadow=True)
        draw.rounded_rectangle((x, y, x + 550, y + 58), radius=24, fill=PALE[color], outline=color)
        draw.rectangle((x, y + 34, x + 550, y + 58), fill=PALE[color])
        draw_text(draw, name, (x + 24, y + 16, x + 526, y + 50), BODY_BOLD, INK, align="center")
        dog(draw, x + 28, y + 105, 0.44, shirt=color, accessory=accessory)
        table(
            draw,
            (x + 190, y + 78, x + 520, y + 218),
            [("Item", 0.38), ("Meaning", 0.62)],
            [
                ("Best", env),
                ("Risk", risk),
                ("Focus", focus),
            ],
            color,
            row_font=TINY,
        )
        rounded(draw, (x + 28, y + 205, x + 210, y + 235), fill=PALE[color], outline=color, radius=14, shadow=False)
        draw_text(draw, "No permanent winner", (x + 38, y + 213, x + 200, y + 228), TINY_BOLD, color, align="center")
    formula_box(
        draw,
        (310, 855, 1610, 940),
        "Classroom scoring idea",
        "Score should include profit, service, forecast discipline, cash health, and innovation timing.",
    )
    key_lesson(draw, "The strongest strategy depends on market conditions and on what performance measure the instructor values.")
    save(image, "Figure_8_Strategy_Archetypes.png")


def main() -> None:
    clean_output_dir()
    fig1_round_loop()
    fig2_control_map()
    fig3_portfolio_pipeline()
    fig4_demand_allocation()
    fig5_operations_cost()
    fig6_forecasting_sop()
    fig7_cash_debt()
    fig8_strategy_archetypes()
    print(f"Created polished classroom infographic image pack in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

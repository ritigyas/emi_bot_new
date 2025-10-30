#!/usr/bin/env python3
"""
generate_cards.py - improved template layout support and fitted text/wrapping.

Generates per-customer template cards:
 - {id}_loan.png
 - {id}_emi.png
 - {id}_bank.png

Usage:
    python generate_cards.py
"""

import os
import sys
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List

import textwrap
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ----- CONFIG -----
PROJECT_ROOT = Path(".")
OUTPUT_DIR = PROJECT_ROOT / "assets" / "generated"
TEMPLATES_DIR = PROJECT_ROOT / "assets" / "templates"
LOGOS_DIR = PROJECT_ROOT / "assets" / "logos"
FONTS_DIR = PROJECT_ROOT / "assets" / "fonts"

CUSTOMER_CSV = PROJECT_ROOT / "data" / "customers_master.csv"
LOG_PATH = PROJECT_ROOT / "logs" / "card_generation.log"

# Templates filenames (place your design images here)
TEMPLATE_FILES = {
    "loan": TEMPLATES_DIR / "loan.png",   # e.g. a designed image with visual elements
    "emi": TEMPLATES_DIR / "emi.png",
    "bank": TEMPLATES_DIR / "bank.png",
}

# Visual / design defaults
WIDTH, HEIGHT = 1280, 720  # expected template size (script uses these coords)
DEFAULT_FONT_NAME = "Montserrat-SemiBold.ttf"  # place valid .ttf in assets/fonts or use system font
TEXT_COLOR = (255, 255, 255)  # white

# Ensure folders exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
LOGOS_DIR.mkdir(parents=True, exist_ok=True)
FONTS_DIR.mkdir(parents=True, exist_ok=True)

# ----- Logging -----
logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("cardgen")
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

# ----- Layout definitions -----
# Boxes specified as (x, y, w, h). Coordinates are for 1280x720 templates.
# Tune these values to match placeholders in your template images.
LAYOUTS: Dict[str, Dict[str, Any]] = {
    "loan": {
        "template": TEMPLATE_FILES["loan"],
        "boxes": {
            "emi_id": (0, 20, WIDTH, 100, "center"),
            "name": (80, 140, WIDTH - 160, 140, "left"),
            "amount": (80, 320, WIDTH - 160, 140, "left"),
        },
        "font_sizes": {"emi_id": 64, "name": 72, "amount": 64},
    },
    "emi": {
        "template": TEMPLATE_FILES["emi"],
        "boxes": {
            "title": (80, 40, WIDTH - 160, 60, "left"),
            "emi_amount": (80, 120, WIDTH - 160, 180, "left"),
            "due": (80, 320, WIDTH - 160, 80, "left"),
            "phone": (80, HEIGHT - 100, WIDTH - 160, 60, "left"),
        },
        "font_sizes": {"title": 48, "emi_amount": 96, "due": 36, "phone": 32},
    },
    "bank": {
        "template": TEMPLATE_FILES["bank"],
        "boxes": {
            "logo": (80, 80, 160, 160, "left"),
            "bank_name": (260, 100, WIDTH - 320, 80, "left"),
            "branch": (260, 190, WIDTH - 320, 60, "left"),
            "ifsc": (260, 260, WIDTH - 320, 60, "left"),
            "reminder": (80, HEIGHT - 100, WIDTH - 160, 60, "left"),
        },
        "font_sizes": {"bank_name": 48, "branch": 36, "ifsc": 34, "reminder": 32},
    },
}


# ----- Utility functions -----
def load_font(preferred: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    """
    Try project font, then system fallback, then ImageFont.load_default()
    """
    if preferred:
        p = FONTS_DIR / preferred
        try:
            if p.exists():
                return ImageFont.truetype(str(p), size)
        except Exception as e:
            logger.warning(f"Could not load font {p}: {e}")

    # try common system fonts
    for sysf in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(sysf, size)
        except Exception:
            continue

    logger.warning("Falling back to ImageFont.load_default()")
    return ImageFont.load_default()


def text_size(draw: ImageDraw.Draw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    """
    Return (width, height) of text. Prefer draw.textbbox (Pillow >= 8), fallback to font.getsize.
    """
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        return int(w), int(h)
    except Exception:
        try:
            return font.getsize(text)
        except Exception:
            return (len(text) * 8, 16)


def wrap_text_to_lines(draw: ImageDraw.Draw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    """
    Wrap text into lines that fit max_width using greedy word accumulation.
    Returns list of lines.
    """
    words = str(text).split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for w in words[1:]:
        trial = current + " " + w
        w_pixel, _ = text_size(draw, trial, font)
        if w_pixel <= max_width:
            current = trial
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return lines


def fit_and_wrap_text(draw: ImageDraw.Draw, text: str, box_w: int, box_h: int,
                      preferred_font: Optional[str], start_size: int, min_size: int = 12) -> Tuple[ImageFont.ImageFont, List[str]]:
    """
    Try font sizes from start_size down to min_size to wrap text to fit within box_w and fit within box_h.
    Returns chosen font and lines list.
    """
    size = start_size
    while size >= min_size:
        font = load_font(preferred_font, size)
        lines = wrap_text_to_lines(draw, text, font, box_w)
        line_h = text_size(draw, "Ay", font)[1]  # approx line height
        total_h = line_h * len(lines)
        if total_h <= box_h:
            return font, lines
        size -= 2
    # fallback: smallest font, truncated lines
    font = load_font(preferred_font, min_size)
    lines = wrap_text_to_lines(draw, text, font, box_w)
    # If still too tall, try to truncate and append ellipsis
    line_h = text_size(draw, "Ay", font)[1]
    max_lines = max(1, box_h // line_h)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        # try adding ellipsis to last line
        last = lines[-1]
        # shorten last line until it fits with "..."
        while text_size(draw, last + "...", font)[0] > box_w and len(last) > 0:
            last = last[:-1]
        lines[-1] = last + "..."
    return font, lines


def normalize_logo_path(path_str: str) -> str:
    """
    Normalize CSV bank_logo_path. Strip leading slashes and try assets/logos fallback.
    """
    if not path_str or str(path_str).strip() == "":
        return ""
    p = str(path_str).strip()
    # remove leading slash/backslash common in some CSVs
    if p.startswith("/") or p.startswith("\\"):
        p = p.lstrip("/\\")
    candidate = Path(p)
    if candidate.exists():
        return str(candidate)
    # try logos dir with basename
    cand2 = LOGOS_DIR / candidate.name
    if cand2.exists():
        return str(cand2)
    # not found
    return ""


# ----- Card drawing functions -----
def draw_text_lines(overlay_draw: ImageDraw.Draw, lines: List[str], font: ImageFont.ImageFont,
                    x: int, y: int, box_w: int, box_h: int, align: str = "left"):
    """
    Draw lines inside the provided box starting at (x,y). align can be 'left' or 'center'.
    """
    line_h = text_size(overlay_draw, "Ay", font)[1]
    total_h = line_h * len(lines)
    # vertical centering in the box
    y0 = y + max(0, (box_h - total_h) // 2)
    for i, line in enumerate(lines):
        w, h = text_size(overlay_draw, line, font)
        if align == "center":
            x_draw = x + max(0, (box_w - w) // 2)
        else:
            x_draw = x
        overlay_draw.text((x_draw, y0 + i * line_h), line, font=font, fill=TEXT_COLOR)


def generate_card_for_row(row: pd.Series, card_type: str):
    """
    Generic renderer using LAYOUTS metadata. card_type in ("loan","emi","bank")
    """
    layout = LAYOUTS[card_type]
    template_path: Path = layout["template"]
    out_name = f"{str(row.get('id') or row.get('Id') or row.get('ID') or 'unknown')}_{card_type}.png"
    out_path = OUTPUT_DIR / out_name

    # load template or create blank background if missing
    if template_path.exists():
        base = Image.open(template_path).convert("RGBA")
        # optionally resize template to expected WIDTHxHEIGHT if not matching
        if base.size != (WIDTH, HEIGHT):
            base = base.resize((WIDTH, HEIGHT), Image.LANCZOS)
    else:
        logger.warning(f"Template missing for {card_type}: {template_path}. Using plain background.")
        base = Image.new("RGBA", (WIDTH, HEIGHT), (255, 255, 255, 255))

    # create transparent overlay to draw text and logos (so template remains visible)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    boxes = layout["boxes"]
    fontsizes = layout.get("font_sizes", {})

    try:
        if card_type == "loan":
            # emi_id
            x, y, w_box, h_box, align = boxes["emi_id"]
            font, lines = fit_and_wrap_text(draw, f"Emi-ID - {row.get('id')}", w_box, h_box, DEFAULT_FONT_NAME, fontsizes.get("emi_id", 64))
            draw_text_lines(draw, lines, font, x, y, w_box, h_box, align)

            # name
            x, y, w_box, h_box, align = boxes["name"]
            name_text = f"Name - {row.get('name', '')}"
            font, lines = fit_and_wrap_text(draw, name_text, w_box, h_box, DEFAULT_FONT_NAME, fontsizes.get("name", 72))
            draw_text_lines(draw, lines, font, x, y, w_box, h_box, align)

            # amount
            x, y, w_box, h_box, align = boxes["amount"]
            amt = row.get("loan_amount", "")
            amount_text = f"Amount - Rs.{int(float(amt)):,}" if amt else "Amount - N/A"
            font, lines = fit_and_wrap_text(draw, amount_text, w_box, h_box, DEFAULT_FONT_NAME, fontsizes.get("amount", 64))
            draw_text_lines(draw, lines, font, x, y, w_box, h_box, align)

        elif card_type == "emi":
            # title (static)
            x, y, w_box, h_box, align = boxes["title"]
            font, lines = fit_and_wrap_text(draw, "EMI Amount", w_box, h_box, DEFAULT_FONT_NAME, fontsizes.get("title", 48))
            draw_text_lines(draw, lines, font, x, y, w_box, h_box, align)

            # EMI amount
            x, y, w_box, h_box, align = boxes["emi_amount"]
            amt = row.get("emi_amount", "")
            emi_text = f"{int(float(amt)):,}" if amt else "N/A"
            font, lines = fit_and_wrap_text(draw, emi_text, w_box, h_box, DEFAULT_FONT_NAME, fontsizes.get("emi_amount", 96))
            draw_text_lines(draw, lines, font, x, y, w_box, h_box, align)

            # due date
            x, y, w_box, h_box, align = boxes["due"]
            due_text = f"Due on {row.get('due_date','N/A')}"
            font, lines = fit_and_wrap_text(draw, due_text, w_box, h_box, DEFAULT_FONT_NAME, fontsizes.get("due", 36))
            draw_text_lines(draw, lines, font, x, y, w_box, h_box, align)

            # phone
            x, y, w_box, h_box, align = boxes["phone"]
            phone_text = f"Contact: {row.get('phone_number','')}"
            font, lines = fit_and_wrap_text(draw, phone_text, w_box, h_box, DEFAULT_FONT_NAME, fontsizes.get("phone", 32))
            draw_text_lines(draw, lines, font, x, y, w_box, h_box, align)

        elif card_type == "bank":
            # logo
            lx, ly, lw, lh, _ = boxes["logo"]
            logo_path = normalize_logo_path(row.get("bank_logo_path", ""))
            logo_img = None
            if logo_path:
                try:
                    logo_img = Image.open(logo_path).convert("RGBA")
                    logo_img = logo_img.resize((lw, lh), Image.LANCZOS)
                except Exception as e:
                    logger.warning(f"Failed to open logo {logo_path}: {e}")
                    logo_img = None
            if not logo_img:
                # placeholder
                logo_img = Image.new("RGBA", (lw, lh), (255, 255, 255, 0))
                ld = ImageDraw.Draw(logo_img)
                ld.ellipse((0, 0, lw, lh), fill=(255, 255, 255, 255))

            overlay.paste(logo_img, (lx, ly), logo_img)

            # bank name
            x, y, w_box, h_box, align = boxes["bank_name"]
            bank_name = row.get("bank_name", "N/A")
            font, lines = fit_and_wrap_text(draw, bank_name, w_box, h_box, DEFAULT_FONT_NAME, fontsizes.get("bank_name", 48))
            draw_text_lines(draw, lines, font, x, y, w_box, h_box, align)

            # branch
            x, y, w_box, h_box, align = boxes["branch"]
            branch = row.get("branch_name", "")
            font, lines = fit_and_wrap_text(draw, branch, w_box, h_box, DEFAULT_FONT_NAME, fontsizes.get("branch", 36))
            draw_text_lines(draw, lines, font, x, y, w_box, h_box, align)

            # IFSC
            x, y, w_box, h_box, align = boxes["ifsc"]
            ifsc = row.get("ifsc", "")
            font, lines = fit_and_wrap_text(draw, f"IFSC: {ifsc}" if ifsc else "IFSC: N/A", w_box, h_box, DEFAULT_FONT_NAME, fontsizes.get("ifsc", 34))
            draw_text_lines(draw, lines, font, x, y, w_box, h_box, align)

            # reminder
            x, y, w_box, h_box, align = boxes["reminder"]
            reminder = "For queries call: " + (row.get("phone_number", "N/A"))
            font, lines = fit_and_wrap_text(draw, reminder, w_box, h_box, DEFAULT_FONT_NAME, fontsizes.get("reminder", 32))
            draw_text_lines(draw, lines, font, x, y, w_box, h_box, align)

        # composite overlay above template
        composed = Image.alpha_composite(base, overlay).convert("RGBA")
        composed.save(out_path)
        logger.info(f"Generated {card_type} card: {out_path}")
    except Exception as e:
        logger.exception(f"Error generating {card_type} card for id={row.get('id')}: {e}")
        raise


# ----- Main batch runner -----
def main():
    if not CUSTOMER_CSV.exists():
        logger.error(f"Customer CSV not found: {CUSTOMER_CSV}")
        print(f"Customer CSV not found: {CUSTOMER_CSV}", file=sys.stderr)
        sys.exit(1)

    try:
        df = pd.read_csv(CUSTOMER_CSV, dtype=str).fillna("")
    except Exception as e:
        logger.exception(f"Failed to read CSV {CUSTOMER_CSV}: {e}")
        print(f"Failed to read CSV {CUSTOMER_CSV}: {e}", file=sys.stderr)
        sys.exit(1)

    # normalize columns to lowercase keys
    df.rename(columns={c: c.strip().lower() for c in df.columns}, inplace=True)

    total = len(df)
    success = 0
    failures = 0

    for idx, s in df.iterrows():
        # s is a Series with lowercase keys
        try:
            # bring keys used earlier to expected names (id, name, etc.)
            row = s  # Series
            # Normalize bank_logo_path field
            if "bank_logo_path" in row:
                row["bank_logo_path"] = normalize_logo_path(row["bank_logo_path"])

            generate_card_for_row(row, "loan")
            generate_card_for_row(row, "emi")
            generate_card_for_row(row, "bank")
            success += 1
        except Exception as e:
            logger.error(f"Failed for customer at row {idx} id={row.get('id')}: {e}")
            failures += 1
            # continue

    logger.info(f"Card generation completed. Total: {total}, Success: {success}, Failures: {failures}")
    print(f"Done. Total: {total}, Success: {success}, Failures: {failures}")


if __name__ == "__main__":
    main()
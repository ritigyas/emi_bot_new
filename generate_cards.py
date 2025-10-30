#!/usr/bin/env python3
"""
generate_cards.py - Final version with overlap fixes.

Creates design-standard templates and generates per-customer cards (loan, emi, bank)
using Pillow + pandas.

Outputs:
 - Templates: assets/templates/{loan|emi|bank}_card_template.png
 - Generated cards per row: assets/generated/{id}_loan.png, {id}_emi.png, {id}_bank.png
 - Logs: logs/card_generation.log
"""
import os
import sys
import math
import logging
import requests
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any

import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ------------------- CONFIG -------------------
PROJECT_ROOT = Path(".")
ASSETS = PROJECT_ROOT / "assets"
TEMPLATES_DIR = ASSETS / "templates"
LOGOS_DIR = ASSETS / "logos"
FONTS_DIR = ASSETS / "fonts"
GENERATED_DIR = ASSETS / "generated"
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"

# Assumes customers_master.csv is present in the data directory
CUSTOMER_CSV = DATA_DIR / "customers_master.csv" 
LOG_PATH = LOG_DIR / "card_generation.log"

# Preferred Font and Fallbacks
FONT_FILENAME = "Montserrat-SemiBold.ttf"
FONT_URL = "https://github.com/googlefonts/Montserrat/raw/main/fonts/ttf/Montserrat-SemiBold.ttf"
FONT_FALLBACKS_SYSTEM = ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf")

WIDTH, HEIGHT = 1280, 720
PRIMARY_COLOR = (82, 27, 123)  # Saarathi purple (#521B7B)
LIGHT_PURPLE = (120, 80, 160)
TEXT_COLOR = (255, 255, 255, 255)  # white
DARK_TEXT_COLOR = (30, 30, 30, 255)  # for light backgrounds
ACCENT_COLOR = (255, 204, 0)  # Gold accent for highlights

TEMPLATE_FILENAMES = {
    "loan": TEMPLATES_DIR / "loan_card_template.png",
    "emi": TEMPLATES_DIR / "emi_card_template.png",
    "bank": TEMPLATES_DIR / "bank_card_template.png",
}

# Ensure directories exist
for d in (TEMPLATES_DIR, LOGOS_DIR, FONTS_DIR, GENERATED_DIR, DATA_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Setup logging
logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("cardgen")
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
logger.addHandler(console)

# ------------------- UTILITIES -------------------
def download_font_if_not_exists(font_name: str, url: str, target_dir: Path) -> bool:
    """Downloads a font from a URL if it doesn't exist locally."""
    font_path = target_dir / font_name
    if font_path.exists():
        return True
    logger.info(f"Attempting to download font from {url} to {font_path}")
    try:
        response = requests.get(url, stream=True, timeout=15)
        response.raise_for_status()
        with open(font_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        logger.info(f"Successfully downloaded {font_name}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download font {font_name} from {url}: {e}")
        return False


def load_font(preferred: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    """Try local font, then downloaded font, then fallbacks, then default."""
    try:
        if preferred:
            p = FONTS_DIR / preferred
            if p.exists():
                return ImageFont.truetype(str(p), size)
    except Exception as e:
        logger.debug(f"Failed to load preferred local font {preferred}: {e}")

    if preferred == FONT_FILENAME and FONT_URL:
        if download_font_if_not_exists(FONT_FILENAME, FONT_URL, FONTS_DIR):
            try:
                return ImageFont.truetype(str(FONTS_DIR / FONT_FILENAME), size)
            except Exception as e:
                logger.debug(f"Failed to load downloaded font {FONT_FILENAME}: {e}")

    for sysf in FONT_FALLBACKS_SYSTEM:
        try:
            return ImageFont.truetype(str(sysf), size)
        except Exception:
            continue

    logger.warning("Falling back to ImageFont.load_default()")
    return ImageFont.load_default()


def text_size(draw: ImageDraw.Draw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    """Return (width, height) using textbbox or font.getsize fallback."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])
    except Exception:
        try:
            return font.getsize(text)
        except Exception:
            return (len(text) * max(8, getattr(font, "size", 16) // 2), getattr(font, "size", 16))


def create_vertical_gradient(w: int, h: int, top_color: Tuple[int, int, int], bottom_color: Tuple[int, int, int]) -> Image.Image:
    """Generates a smooth vertical gradient."""
    base = Image.new("RGB", (w, h), top_color)
    top = Image.new("RGB", (w, h), bottom_color)
    mask = Image.new("L", (w, h))
    mask_data = []
    for y in range(h):
        mask_data.extend([int(255 * (y / max(1, h - 1)))] * w)
    mask.putdata(mask_data)
    blended = Image.composite(top, base, mask)
    return blended


def create_background(w=WIDTH, h=HEIGHT) -> Image.Image:
    """Create a purple gradient background."""
    top_color = (200, 180, 230)
    bottom_color = PRIMARY_COLOR
    grad = create_vertical_gradient(w, h, top_color, bottom_color)
    return grad.convert("RGBA")


def format_currency(value: str) -> str:
    """Formats a string/float value into Indian Rupee currency with commas."""
    try:
        v = float(value)
        return f"₹{int(round(v)):,}"
    except Exception:
        return "N/A"

def normalize_logo_path(path_str: str) -> str:
    """Finds the correct path for a logo, checking absolute, relative, and LOGOS_DIR."""
    if not path_str or str(path_str).strip() == "":
        return ""
    p = str(path_str).strip()
    candidate = Path(p)
    if candidate.exists():
        return str(candidate)
    candidate2 = LOGOS_DIR / candidate.name
    if candidate2.exists():
        return str(candidate2)
    return ""


# ------------------- TEMPLATE CREATION (Cleaned - Static elements only) -------------------
def create_loan_template(save_path: Path):
    bg = create_background(WIDTH, HEIGHT)
    draw = ImageDraw.Draw(bg)

    card_margin = 80
    card_width = WIDTH - 2 * card_margin
    card_height = HEIGHT - 2 * card_margin
    card_x = card_margin
    card_y = card_margin + 20

    # Rounded rectangle background for the card
    draw.rounded_rectangle(
        (card_x, card_y, card_x + card_width, card_y + card_height),
        radius=30,
        fill=PRIMARY_COLOR
    )

    text_area_x = card_x + 50
    
    # Labels (ONLY static labels/placeholders)
    # Adjusted position for "EMI Loan Card" to give space to Emi-ID
    emi_loan_card_font = load_font(FONT_FILENAME, 48)
    draw.text((card_x + card_width // 2, card_y + 40), "EMI Loan Card", fill=TEXT_COLOR, font=emi_loan_card_font, anchor="ms")

    # Adjusted Y coordinates for labels to prevent overlap with dynamic content
    name_label_font = load_font(FONT_FILENAME, 32)
    draw.text((text_area_x, card_y + 180), "Customer Name:", fill=ACCENT_COLOR, font=name_label_font)

    amount_label_font = load_font(FONT_FILENAME, 32)
    draw.text((text_area_x, card_y + 370), "Total Loan Amount:", fill=ACCENT_COLOR, font=amount_label_font)

    bg.save(save_path, "PNG")
    logger.info(f"Created loan template: {save_path}")


def create_emi_template(save_path: Path):
    """Creates a clean EMI template with header and footer bars."""
    bg = create_background(WIDTH, HEIGHT)
    draw = ImageDraw.Draw(bg)

    card_margin_x = 90
    card_margin_y = 70
    card_width = WIDTH - 2 * card_margin_x
    card_height = HEIGHT - 2 * card_margin_y

    # Main card body
    draw.rounded_rectangle(
        (card_margin_x, card_margin_y, card_margin_x + card_width, card_margin_y + card_height),
        radius=30,
        fill=PRIMARY_COLOR
    )

    inner_pad_x = 60
    inner_content_x = card_margin_x + inner_pad_x

    # EMI Details Header Box (Label only)
    emi_label_font = load_font(FONT_FILENAME, 36)
    emi_label_text = "Monthly EMI Amount"
    tw, th = text_size(draw, emi_label_text, emi_label_font)
    
    # Position the header box and label clearly at the top of the card's content area
    header_box_y = card_margin_y + 50 # Adjusted Y
    draw.rounded_rectangle(
        (inner_content_x, header_box_y, inner_content_x + tw + 40, header_box_y + th + 20),
        radius=15,
        fill=LIGHT_PURPLE
    )
    draw.text((inner_content_x + 20, header_box_y + 10), emi_label_text, fill=TEXT_COLOR, font=emi_label_font)

    # Contact Bar (Empty bar, data will be drawn dynamically)
    # Ensure this bar is at the bottom, not interfering with central content
    draw.rounded_rectangle((card_margin_x, HEIGHT - card_margin_y - 60, WIDTH - card_margin_x, HEIGHT - card_margin_y), radius=20, fill=(0, 0, 0, 150))

    bg.save(save_path, "PNG")
    logger.info(f"Created emi template: {save_path}")


def create_bank_template(save_path: Path):
    bg = create_background(WIDTH, HEIGHT)
    draw = ImageDraw.Draw(bg)

    card_margin_x = 90
    card_margin_y = 70
    card_width = WIDTH - 2 * card_margin_x
    card_height = HEIGHT - 2 * card_margin_y

    # Main white card body
    draw.rounded_rectangle((card_margin_x, card_margin_y, card_margin_x + card_width, card_margin_y + card_height), radius=30, fill=(255, 255, 255, 255))

    inner_pad_x = 60
    inner_content_x = card_margin_x + inner_pad_x

    # Logo Placeholder
    logo_size = 120
    logo_x = inner_content_x
    logo_y = card_margin_y + 50
    draw.rounded_rectangle((logo_x, logo_y, logo_x + logo_size, logo_y + logo_size), radius=20, fill=(200, 200, 200, 255))
    logo_text_font = load_font(FONT_FILENAME, 28)
    draw.text((logo_x + logo_size // 2, logo_y + logo_size // 2), "LOGO", fill=DARK_TEXT_COLOR, font=logo_text_font, anchor="ms")

    # Fixed Labels - Adjusted for better spacing
    bank_name_font = load_font(FONT_FILENAME, 48)
    draw.text((logo_x + logo_size + 40, logo_y + 20), "Bank Name:", fill=PRIMARY_COLOR, font=bank_name_font) # Added colon for clarity

    branch_font = load_font(FONT_FILENAME, 32)
    draw.text((logo_x + logo_size + 40, logo_y + 80), "Branch Location:", fill=DARK_TEXT_COLOR, font=branch_font) # Added colon

    # Account info labels - These are now static labels in the template
    acc_label_y_start = logo_y + logo_size + 80 # Starting Y for the block of account info

    _draw_text(draw, "IFSC:", FONT_FILENAME, 32, inner_content_x, acc_label_y_start, DARK_TEXT_COLOR, align='ls')
    _draw_text(draw, "Account Holder:", FONT_FILENAME, 32, inner_content_x, acc_label_y_start + 70, DARK_TEXT_COLOR, align='ls')
    _draw_text(draw, "Account No:", FONT_FILENAME, 32, inner_content_x, acc_label_y_start + 140, DARK_TEXT_COLOR, align='ls')

    bg.save(save_path, "PNG")
    logger.info(f"Created bank template: {save_path}")


def ensure_templates():
    """Ensures all template files exist before generation starts."""
    if not TEMPLATE_FILENAMES["loan"].exists():
        create_loan_template(TEMPLATE_FILENAMES["loan"])
    if not TEMPLATE_FILENAMES["emi"].exists():
        create_emi_template(TEMPLATE_FILENAMES["emi"])
    if not TEMPLATE_FILENAMES["bank"].exists():
        create_bank_template(TEMPLATE_FILENAMES["bank"])
    logger.info(f"Templates present in {TEMPLATES_DIR}")


# ------------------- DRAWING HELPERS -------------------
def _draw_text(draw: ImageDraw.Draw, text: str, font_name: str, size: int, x: int, y: int, color: Tuple[int, int, int, int], align: str = "ls"):
    """Draws text with specified size, position, color, and anchor alignment."""
    fnt = load_font(font_name, size)
    draw.text((x, y), text, fill=color, font=fnt, anchor=align)

# ------------------- CARD GENERATION -------------------
def generate_card_for_row(row: Dict[str, Any]):
    cid = row.get("id") or row.get("customer_id") or "unknown"
    
    # --- Shared Coordinates ---
    card_margin_x = 90
    card_margin_y = 70
    card_width = WIDTH - 2 * card_margin_x
    card_x = card_margin_x
    card_y = card_margin_y
    center_x = card_margin_x + card_width // 2
    inner_pad_x = 60
    inner_content_x = card_margin_x + inner_pad_x
    
    # ---------- LOAN (Fixed Overlap) ----------
    loan_tpl = Image.open(TEMPLATE_FILENAMES["loan"]).convert("RGBA")
    loan_out = loan_tpl.copy()
    draw = ImageDraw.Draw(loan_out)

    text_start_x = card_x + 50 # Start of dynamic content
    
    # Emi-ID (Center top) - Adjusted Y to be below "EMI Loan Card" title
    _draw_text(draw, f"Emi-ID - {row.get('emi_id', cid)}", FONT_FILENAME, 36,
               center_x, card_y + 110, TEXT_COLOR, align='ms') # Increased Y from 100 to 110
               
    # Name (Below "Customer Name:" label)
    _draw_text(draw, row.get("name", "N/A"), FONT_FILENAME, 60,
               text_start_x, card_y + 235, TEXT_COLOR, align='ls') # Adjusted Y from 205 to 235
    
    # Loan Amount (Below "Total Loan Amount:" label)
    _draw_text(draw, format_currency(row.get("loan_amount", "")), FONT_FILENAME, 60,
               text_start_x, card_y + 425, TEXT_COLOR, align='ls') # Adjusted Y from 395 to 425

    loan_out.save(GENERATED_DIR / f"{cid}_loan.png", "PNG")
    logger.info(f"Saved loan card: {cid}_loan.png")

    # ---------- EMI (Fixed Overlap - Single amount/date) ----------
    emi_tpl = Image.open(TEMPLATE_FILENAMES["emi"]).convert("RGBA")
    emi_out = emi_tpl.copy()
    draw = ImageDraw.Draw(emi_out)

    # Calculate content area for EMI details to avoid footer/header
    content_top_y = card_margin_y + 120 # Below the "Monthly EMI Amount" box
    content_bottom_y = HEIGHT - card_margin_y - 60 # Above the contact bar
    content_height = content_bottom_y - content_top_y
    
    # 1. EMI AMOUNT (Main focus, centered within the available content area)
    emi_amount = format_currency(row.get("emi_amount", ""))
    emi_amount_y = content_top_y + content_height * 0.35 # Position higher in the content area
    
    _draw_text(draw, emi_amount, FONT_FILENAME, 100,
               center_x, emi_amount_y, TEXT_COLOR, align='ms') # Large Text

    # 2. DUE DATE (Below the EMI amount, with proper spacing)
    due_text = f"Due on {row.get('due_date', 'N/A')}"
    due_date_y = emi_amount_y + 120 # Increased spacing from 90 to 120
    
    _draw_text(draw, due_text, FONT_FILENAME, 40,
               center_x, due_date_y, ACCENT_COLOR, align='ms') # Smaller Accent Text

    # 3. CONTACT INFO (On the bottom bar, vertically centered)
    phone_number = row.get('phone_number', '+91 XXXX XXXXX')
    contact_text = f"Contact for support: {phone_number}"
    contact_y = HEIGHT - card_margin_y - 30 # Y position is center of the bottom bar
    
    _draw_text(draw, contact_text, FONT_FILENAME, 30,
               WIDTH // 2, contact_y, TEXT_COLOR, align='ms')

    emi_out.save(GENERATED_DIR / f"{cid}_emi.png", "PNG")
    logger.info(f"Saved emi card: {cid}_emi.png")

    # ---------- BANK (Fixed Overlap) ----------
    bank_tpl = Image.open(TEMPLATE_FILENAMES["bank"]).convert("RGBA")
    bank_out = bank_tpl.copy()
    draw = ImageDraw.Draw(bank_out)

    logo_size = 120
    logo_x = inner_content_x
    logo_y = card_margin_y + 50
    
    # Logo placement
    logo_path = normalize_logo_path(row.get("bank_logo_path", ""))
    if logo_path:
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_img = logo_img.resize((logo_size, logo_size), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
            bank_out.paste(logo_img, (logo_x, logo_y), logo_img)
        except Exception as e:
            logger.warning(f"Failed to paste logo {logo_path} for id={cid}: {e}. Drawing placeholder.")
            _draw_text(draw, "LOGO", FONT_FILENAME, 28, logo_x + logo_size // 2, logo_y + logo_size // 2, DARK_TEXT_COLOR, align='ms')
    
    # Bank Details (Dynamic content positioned next to the labels)
    # The labels "Bank Name:" and "Branch Location:" are now part of the template
    # We need to draw the *values* next to these labels.
    
    # Calculate starting X for dynamic bank/branch details to align with the labels
    bank_name_label_font = load_font(FONT_FILENAME, 48)
    branch_name_label_font = load_font(FONT_FILENAME, 32)
    
    # Measure label text to determine where to place dynamic content
    bank_name_label_width, _ = text_size(draw, "Bank Name:", bank_name_label_font)
    branch_name_label_width, _ = text_size(draw, "Branch Location:", branch_name_label_font)
    
    # X position for dynamic text, slightly offset from the end of the longest label
    dynamic_text_x_offset = logo_x + logo_size + 40 + max(bank_name_label_width, branch_name_label_width) + 15 

    # Bank Name Value
    _draw_text(draw, row.get("bank_name", "N/A"), FONT_FILENAME, 48,
               dynamic_text_x_offset, logo_y + 20, PRIMARY_COLOR, align='ls')

    # Branch Name Value
    _draw_text(draw, row.get("branch_name", "N/A"), FONT_FILENAME, 32,
               dynamic_text_x_offset, logo_y + 80, DARK_TEXT_COLOR, align='ls')
    
    # Account Info (Dynamic content positioned next to the labels)
    acc_block_y = logo_y + logo_size + 80
    
    # Measure "IFSC:", "Account Holder:", "Account No:" labels to align values
    ifsc_label_font = load_font(FONT_FILENAME, 32)
    ifsc_label_width, _ = text_size(draw, "IFSC:", ifsc_label_font)
    acc_holder_label_width, _ = text_size(draw, "Account Holder:", ifsc_label_font)
    acc_no_label_width, _ = text_size(draw, "Account No:", ifsc_label_font)
    
    dynamic_acc_text_x_offset = inner_content_x + max(ifsc_label_width, acc_holder_label_width, acc_no_label_width) + 15
    
    _draw_text(draw, row.get('ifsc', 'N/A'), FONT_FILENAME, 32,
               dynamic_acc_text_x_offset, acc_block_y, DARK_TEXT_COLOR, align='ls')
               
    _draw_text(draw, row.get('account_holder', row.get('name', 'N/A')), FONT_FILENAME, 32,
               dynamic_acc_text_x_offset, acc_block_y + 70, DARK_TEXT_COLOR, align='ls')
               
    _draw_text(draw, row.get('account_number', 'XXXXXXXXXXXX'), FONT_FILENAME, 32,
               dynamic_acc_text_x_offset, acc_block_y + 140, DARK_TEXT_COLOR, align='ls')

    # Bottom reminder bar - Adjusted Y for vertical centering within the bar
    contact_text = f"For queries call: {row.get('phone_number', '+91 XXXX XXXXX')}"
    contact_bar_center_y = HEIGHT - card_margin_y - 30 # Y position is center of the bottom bar
    _draw_text(draw, contact_text, FONT_FILENAME, 30,
               WIDTH // 2, contact_bar_center_y, TEXT_COLOR, align='ms')

    bank_out.save(GENERATED_DIR / f"{cid}_bank.png", "PNG")
    logger.info(f"Saved bank card: {cid}_bank.png")


# ------------------- MAIN -------------------
def main():
    logger.info("Starting card generation")
    ensure_templates()

    if not CUSTOMER_CSV.exists():
        logger.error(f"Customer CSV not found: {CUSTOMER_CSV}. Please ensure it is in the '{DATA_DIR}' directory.")
        print(f"Customer CSV not found: {CUSTOMER_CSV}", file=sys.stderr)
        return

    try:
        df = pd.read_csv(CUSTOMER_CSV, dtype=str).fillna("")
    except Exception as e:
        logger.exception(f"Failed to read CSV: {e}")
        print("Failed to read CSV", e, file=sys.stderr)
        return

    if df.empty:
        logger.warning("CSV contains no rows")
        print("CSV contains no rows")
        return

    # Normalize column names to lowercase
    df.rename(columns={c: c.strip().lower() for c in df.columns}, inplace=True)

    total = len(df)
    success = 0
    failures = 0

    for idx, raw_row in df.iterrows():
        try:
            row = {k.strip().lower(): (v if v is not None else "") for k, v in raw_row.items()}
            # Normalize logo path before use
            if "bank_logo_path" in row:
                row["bank_logo_path"] = normalize_logo_path(row["bank_logo_path"])
            generate_card_for_row(row)
            success += 1
        except Exception as e:
            logger.exception(f"Failed to generate cards for row {idx} (ID: {row.get('id', 'N/A')}): {e}")
            failures += 1
            continue

    logger.info(f"Generation finished. Total: {total}, Success: {success}, Failures: {failures}")
    print(f"Done. Total: {total}, Success: {success}, Failures: {failures}. Check '{GENERATED_DIR}' for images and '{LOG_DIR}' for logs.")


if __name__ == "__main__":
    main()

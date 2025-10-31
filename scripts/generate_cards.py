import argparse
import logging
import sys
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import requests

# ---------- CONFIG ----------
PROJECT_ROOT = Path(".")
ASSETS = PROJECT_ROOT / "assets"
TEMPLATES_DIR = ASSETS / "templates"
LOGOS_DIR = ASSETS / "logos"
FONTS_DIR = ASSETS / "fonts"
GENERATED_DIR = ASSETS / "generated"
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"

DEFAULT_CSV = DATA_DIR / "customers_master.csv"
LOG_PATH = LOG_DIR / "card_generation.log"

FONT_FILENAME = "Montserrat-SemiBold.ttf"
FONT_URL = "https://github.com/googlefonts/Montserrat/raw/main/fonts/ttf/Montserrat-SemiBold.ttf"
FONT_FALLBACKS_SYSTEM = ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf")

WIDTH, HEIGHT = 1280, 720
PRIMARY_COLOR = (82, 27, 123)  # purple
LIGHT_PURPLE = (120, 80, 160)
TEXT_COLOR = (255, 255, 255, 255)
DARK_TEXT_COLOR = (30, 30, 30, 255)
ACCENT_COLOR = (255, 204, 0)

TEMPLATE_FILENAMES = {
    "loan": TEMPLATES_DIR / "loan_card_template.png",
    "emi": TEMPLATES_DIR / "emi_card_template.png",
    "bank": TEMPLATES_DIR / "bank_card_template.png",
}

for d in (TEMPLATES_DIR, LOGOS_DIR, FONTS_DIR, GENERATED_DIR, DATA_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("cardgen")
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
logger.addHandler(console)

def download_font_if_not_exists(font_name: str, url: str, target_dir: Path) -> bool:
    font_path = target_dir / font_name
    if font_path.exists():
        return True
    logger.info(f"Downloading font {font_name} from {url}")
    try:
        r = requests.get(url, stream=True, timeout=15)
        r.raise_for_status()
        with open(font_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        logger.info("Font downloaded")
        return True
    except Exception as e:
        logger.warning(f"Font download failed: {e}")
        return False


def load_font(preferred: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    if preferred:
        local = FONTS_DIR / preferred
        try:
            if local.exists():
                return ImageFont.truetype(str(local), size)
        except Exception:
            pass

    if preferred == FONT_FILENAME and FONT_URL:
        if download_font_if_not_exists(FONT_FILENAME, FONT_URL, FONTS_DIR):
            try:
                return ImageFont.truetype(str(FONTS_DIR / FONT_FILENAME), size)
            except Exception:
                pass

    for sysf in FONT_FALLBACKS_SYSTEM:
        try:
            return ImageFont.truetype(sysf, size)
        except Exception:
            continue

    logger.warning("Falling back to PIL default font")
    return ImageFont.load_default()


def create_vertical_gradient(w: int, h: int, top_color: Tuple[int, int, int], bottom_color: Tuple[int, int, int]) -> Image.Image:
    base = Image.new("RGB", (w, h), top_color)
    top = Image.new("RGB", (w, h), bottom_color)
    mask = Image.new("L", (w, h))
    mask_data = []
    for y in range(h):
        mask_data.extend([int(255 * (y / max(1, h - 1)))] * w)
    mask.putdata(mask_data)
    blended = Image.composite(top, base, mask)
    return blended.convert("RGBA")


def create_background(w=WIDTH, h=HEIGHT) -> Image.Image:
    top_color = (230, 220, 240)
    bottom_color = PRIMARY_COLOR
    return create_vertical_gradient(w, h, top_color, bottom_color)


def format_currency(value: str) -> str:
    try:
        v = float(value)
        return f"₹{int(round(v)):,}"
    except Exception:
        return "N/A"


def normalize_logo_path(path_str: str) -> str:
    if not path_str or str(path_str).strip() == "":
        return ""
    p = Path(str(path_str).strip())
    if p.exists():
        return str(p)
    alt = LOGOS_DIR / p.name
    if alt.exists():
        return str(alt)
    return ""


def text_size(draw: ImageDraw.Draw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])
    except Exception:
        try:
            return font.getsize(text)
        except Exception:
            return (len(text) * 8, getattr(font, "size", 16))


def create_empty_template(save_path: Path):
    bg = create_background(WIDTH, HEIGHT)
    bg.save(save_path, "PNG")
    logger.info(f"Created empty template: {save_path}")

def ensure_templates(force: bool = False):
    if force or not TEMPLATE_FILENAMES["loan"].exists():
        create_empty_template(TEMPLATE_FILENAMES["loan"])
    if force or not TEMPLATE_FILENAMES["emi"].exists():
        create_empty_template(TEMPLATE_FILENAMES["emi"])
    if force or not TEMPLATE_FILENAMES["bank"].exists():
        create_empty_template(TEMPLATE_FILENAMES["bank"])
    logger.info(f"Templates ready in {TEMPLATES_DIR} (force={force})")


def generate_card_for_row(row: Dict[str, Any]):
    cid = row.get("id") or row.get("customer_id") or "unknown"

    card_margin_x = 90
    card_margin_y = 70
    card_width = WIDTH - 2 * card_margin_x
    center_x = card_margin_x + card_width // 2
    left_x = card_margin_x + 30

    # Fonts
    title_font = load_font(FONT_FILENAME, 48)
    id_font = load_font(FONT_FILENAME, 44)
    label_font = load_font(FONT_FILENAME, 32)
    value_font = load_font(FONT_FILENAME, 40)
    small_font = load_font(FONT_FILENAME, 48)

    # ----- LOAN -----
    loan_tpl = Image.open(TEMPLATE_FILENAMES["loan"]).convert("RGBA")
    out_loan = loan_tpl.copy()
    draw = ImageDraw.Draw(out_loan)

    draw.text((center_x - 370, card_margin_y + 170), f"Emi-ID - {row.get('emi_id', cid)}", fill=TEXT_COLOR, font=id_font, anchor="ms")

    name_y = card_margin_y + 180
    draw.text((left_x + 300, name_y + 60), row.get("name", "N/A"), fill=TEXT_COLOR, font=value_font, anchor="ls")

    loan_y = name_y + 130
    draw.text((left_x + 350, loan_y +120), format_currency(row.get("loan_amount", "")), fill=TEXT_COLOR, font=value_font, anchor="ls")

    out_loan.save(GENERATED_DIR / f"{cid}_loan.png", "PNG")
    logger.info(f"Saved loan card {cid}_loan.png")

    # ----- EMI -----
    emi_tpl = Image.open(TEMPLATE_FILENAMES["emi"]).convert("RGBA")
    out_emi = emi_tpl.copy()
    draw = ImageDraw.Draw(out_emi)

    # header_w = 850
    # header_h = 60
    # header_x = left_x
    # header_y = card_margin_y + 30

    emi_amount = format_currency(row.get("emi_amount", ""))
    draw.text((center_x  , card_margin_y + 240), emi_amount, fill=TEXT_COLOR, font=load_font(FONT_FILENAME, 110), anchor="ms")

    due_text = f"Due on {row.get('due_date', 'N/A')}"
    draw.text((center_x, card_margin_y + 400), due_text, fill=ACCENT_COLOR, font=load_font(FONT_FILENAME, 36), anchor="ms")

    bar_y0 = HEIGHT - card_margin_y - 70
    bar_y1 = HEIGHT - card_margin_y - 10
    draw.rounded_rectangle((card_margin_x, bar_y0, card_margin_x + card_width, bar_y1), radius=12, fill=(0, 0, 0, 160))
    phone = row.get("phone_number", "+91 XXXXXXXXXX")
    draw.text((center_x, (bar_y0 + bar_y1) // 2), f"Contact Number : {phone}", fill=TEXT_COLOR, font=small_font, anchor="mm")

    out_emi.save(GENERATED_DIR / f"{cid}_emi.png", "PNG")
    logger.info(f"Saved emi card {cid}_emi.png")

    # ----- BANK -----
    bank_tpl = Image.open(TEMPLATE_FILENAMES["bank"]).convert("RGBA")
    out_bank = bank_tpl.copy()
    draw = ImageDraw.Draw(out_bank)

    panel_x0 = left_x
    panel_y0 = card_margin_y + 30
    panel_w = WIDTH - 2 * left_x
    panel_h = 340
    draw.rounded_rectangle((panel_x0, panel_y0, panel_x0 + panel_w, panel_y0 + panel_h), radius=20, fill=(255, 255, 255, 255))

    # logo_width = 450
    # logo_height = 200
    # logo_x = panel_x0 + 30
    # logo_y = panel_y0 + 20
    # logo_path = normalize_logo_path(row.get("bank_logo_path", ""))

    # if logo_path:
    #     try:
    #         logo_img = Image.open(logo_path).convert("RGBA")
    #         resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    #         logo_img = logo_img.resize((logo_width, logo_height), resample)
    #         out_bank.paste(logo_img, (panel_x0 + 30, panel_y0 + 20), logo_img)
    #     except Exception:
    #         draw.rounded_rectangle((panel_x0 + 30, panel_y0 + 20, panel_x0 + 30 + logo_width, panel_y0 + 20 + logo_height),
    #                                radius=12, fill=(220, 220, 220, 255))
    #         draw.text((panel_x0 + 30 + logo_width // 2, panel_y0 + 20 + logo_height // 2), "LOGO",
    #                   fill=DARK_TEXT_COLOR, font=load_font(FONT_FILENAME, 24), anchor="ms")
    # else:
    #     draw.rounded_rectangle((panel_x0 + 30, panel_y0 + 20, panel_x0 + 30 + logo_width, panel_y0 + 20 + logo_height),
    #                            radius=12, fill=(220, 220, 220, 255))
    #     draw.text((panel_x0 + 30 + logo_width // 2, panel_y0 + 20 + logo_height // 2), "LOGO",
    #               fill=DARK_TEXT_COLOR, font=load_font(FONT_FILENAME, 24), anchor="ms")
    text_x_start = panel_x0 + 30 + 450 + 30
    draw.text((text_x_start-480, panel_y0 + 20 + 80), "Bank Name:", fill=DARK_TEXT_COLOR, font=load_font(FONT_FILENAME, 28), anchor="ls")
    draw.text((text_x_start - 280, panel_y0 + 20 + 80), row.get("bank_name", "N/A"), fill=PRIMARY_COLOR, font=load_font(FONT_FILENAME, 36), anchor="ls")

    draw.text((text_x_start-480, panel_y0 + 20 + 120), "Branch:", fill=DARK_TEXT_COLOR, font=load_font(FONT_FILENAME, 24), anchor="ls")
    draw.text((text_x_start -380, panel_y0 + 20 + 120), row.get("branch_name", "N/A"), fill=DARK_TEXT_COLOR, font=load_font(FONT_FILENAME, 28), anchor="ls")

    acc_y = panel_y0 + 20 + 200 + 0
    draw.text((panel_x0 + 30, acc_y), "IFSC:", fill=DARK_TEXT_COLOR, font=load_font(FONT_FILENAME, 24), anchor="ls")
    draw.text((panel_x0 + 100, acc_y), row.get("ifsc", "N/A"), fill=DARK_TEXT_COLOR, font=load_font(FONT_FILENAME, 24), anchor="ls")

    draw.text((panel_x0 + 30, acc_y + 50), "Account Holder:", fill=DARK_TEXT_COLOR, font=load_font(FONT_FILENAME, 24), anchor="ls")
    draw.text((panel_x0 + 250, acc_y + 50), row.get("account_holder", row.get("name", "N/A")), fill=DARK_TEXT_COLOR, font=load_font(FONT_FILENAME, 24), anchor="ls")

    draw.text((panel_x0 + 30, acc_y + 110), "Account Number:", fill=DARK_TEXT_COLOR, font=load_font(FONT_FILENAME, 24), anchor="ls")
    draw.text((panel_x0 + 260, acc_y + 110), row.get("account_number", "XXXXXXXXXXXX"), fill=DARK_TEXT_COLOR, font=load_font(FONT_FILENAME, 24), anchor="ls")

    bar_y0 = panel_y0 + panel_h + 100
    bar_y1 = bar_y0 + 80
    draw.rounded_rectangle((panel_x0, bar_y0, panel_x0 + panel_w, bar_y1), radius=12, fill=(PRIMARY_COLOR[0], PRIMARY_COLOR[1], PRIMARY_COLOR[2], 230))
    phone = row.get("phone_number", "+91 XXXXXXXXXX")
    draw.text((panel_x0 + panel_w // 2, (bar_y0 + bar_y1) // 2), f"Contact Number : {phone}", fill=TEXT_COLOR, font=load_font(FONT_FILENAME, 26), anchor="mm")

    out_bank.save(GENERATED_DIR / f"{cid}_bank.png", "PNG")
    logger.info(f"Saved bank card {cid}_bank.png")


# ---------- MAIN ----------
def main(csv_path: Path, force_templates: bool = False):
    logger.info("Starting generation")
    ensure_templates(force_templates)

    if not csv_path.exists():
        logger.error(f"Customer CSV not found: {csv_path}")
        print(f"Customer CSV not found: {csv_path}", file=sys.stderr)
        return

    try:
        df = pd.read_csv(csv_path, dtype=str).fillna("")
    except Exception as e:
        logger.exception("Failed to read CSV")
        print("Failed to read CSV:", e, file=sys.stderr)
        return

    if df.empty:
        logger.warning("CSV contains no rows")
        print("CSV contains no rows")
        return

    df.rename(columns={c: c.strip().lower() for c in df.columns}, inplace=True)

    total = len(df)
    success = 0
    failures = 0

    for idx, raw_row in df.iterrows():
        try:
            row = {k.strip().lower(): (v if v is not None else "") for k, v in raw_row.items()}
            if "bank_logo_path" in row:
                row["bank_logo_path"] = normalize_logo_path(row["bank_logo_path"])
            generate_card_for_row(row)
            success += 1
        except Exception as e:
            logger.exception(f"Failed for row {idx}: {e}")
            failures += 1

    logger.info(f"Done. Total: {total}, Success: {success}, Failures: {failures}")
    print(f"Done. Total: {total}, Success: {success}, Failures: {failures}. Check {GENERATED_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate cards from CSV")
    parser.add_argument("--csv", type=str, default=str(DEFAULT_CSV), help="Path to customers CSV")
    parser.add_argument("--force-templates", action="store_true", help="Recreate empty templates")
    args = parser.parse_args()
    main(Path(args.csv), args.force_templates)
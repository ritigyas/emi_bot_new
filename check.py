#!/usr/bin/env python3
"""
Quick debug tool for card generation layout / assets.

Saves assets/generated/debug_loan.png, debug_emi.png, debug_bank.png
with visible box outlines and CSV values printed in high-contrast color.
"""

from pathlib import Path
import sys
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(".")
OUTPUT_DIR = PROJECT_ROOT / "assets" / "generated"
TEMPLATES_DIR = PROJECT_ROOT / "assets" / "templates"
LOGOS_DIR = PROJECT_ROOT / "assets" / "logos"
FONTS_DIR = PROJECT_ROOT / "assets" / "fonts"
CUSTOMER_CSV = PROJECT_ROOT / "data" / "customers_master.csv"

WIDTH, HEIGHT = 1280, 720
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Layout boxes (should match those in your main script)
LAYOUTS_DEBUG = {
    "loan": {
        "template": TEMPLATES_DIR / "loan.png",
        "boxes": {
            "emi_id": (0, 20, WIDTH, 100, "center"),
            "name": (80, 140, WIDTH - 160, 140, "left"),
            "amount": (80, 320, WIDTH - 160, 140, "left"),
        }
    },
    "emi": {
        "template": TEMPLATES_DIR / "emi.png",
        "boxes": {
            "title": (80, 40, WIDTH - 160, 60, "left"),
            "emi_amount": (80, 120, WIDTH - 160, 180, "left"),
            "due": (80, 320, WIDTH - 160, 80, "left"),
            "phone": (80, HEIGHT - 100, WIDTH - 160, 60, "left"),
        }
    },
    "bank": {
        "template": TEMPLATES_DIR / "bank.png",
        "boxes": {
            "logo": (80, 80, 160, 160, "left"),
            "bank_name": (260, 100, WIDTH - 320, 80, "left"),
            "branch": (260, 190, WIDTH - 320, 60, "left"),
            "ifsc": (260, 260, WIDTH - 320, 60, "left"),
            "reminder": (80, HEIGHT - 100, WIDTH - 160, 60, "left"),
        }
    }
}

# helper font (use default if not available)
def load_font(size=36):
    try:
        p = FONTS_DIR / "Montserrat-SemiBold.ttf"
        if p.exists():
            return ImageFont.truetype(str(p), size)
    except Exception:
        pass
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()

def debug_card(row, card_type):
    layout = LAYOUTS_DEBUG[card_type]
    tpl = layout["template"]
    if tpl.exists():
        base = Image.open(tpl).convert("RGBA")
        if base.size != (WIDTH, HEIGHT):
            base = base.resize((WIDTH, HEIGHT))
    else:
        print(f"[WARN] Template missing: {tpl} -> using plain white background")
        base = Image.new("RGBA", (WIDTH, HEIGHT), (255,255,255,255))

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (255,255,255,0))
    draw = ImageDraw.Draw(overlay)
    font = load_font(36)

    # Draw semi-transparent boxes + outlines and labels
    for name, (x, y, w, h, align) in layout["boxes"].items():
        # semi-transparent fill for visibility
        draw.rectangle([x, y, x+w, y+h], fill=(255,255,0,60), outline=(255,0,0,200), width=3)
        # sample content
        if card_type == "loan":
            sample_map = {
                "emi_id": f"Emi-ID - {row.get('id','')}",
                "name": f"Name - {row.get('name','')}",
                "amount": f"Amount - Rs.{row.get('loan_amount','')}"
            }
        elif card_type == "emi":
            sample_map = {
                "title": "EMI Amount",
                "emi_amount": f"{row.get('emi_amount','')}",
                "due": f"Due on {row.get('due_date','')}",
                "phone": f"Contact: {row.get('phone_number','')}"
            }
        else:
            sample_map = {
                "logo": "LOGO",
                "bank_name": f"{row.get('bank_name','')}",
                "branch": f"{row.get('branch_name','')}",
                "ifsc": f"IFSC: {row.get('ifsc','')}",
                "reminder": f"For queries call: {row.get('phone_number','')}"
            }
        text = sample_map.get(name, name)
        # draw text in black for contrast
        draw.text((x+6, y+6), text, fill=(0,0,0,255), font=font)

    composed = Image.alpha_composite(base.convert("RGBA"), overlay)
    out_path = OUTPUT_DIR / f"debug_{card_type}.png"
    composed.save(out_path)
    print(f"Saved debug image: {out_path}")

def main():
    if not CUSTOMER_CSV.exists():
        print("CSV missing:", CUSTOMER_CSV)
        sys.exit(1)
    df = pd.read_csv(CUSTOMER_CSV, dtype=str).fillna("")
    print("CSV columns:", list(df.columns))
    if len(df) == 0:
        print("CSV has no rows")
        sys.exit(1)

    # show first row
    row = df.iloc[0].to_dict()
    print("First row preview:")
    for k, v in row.items():
        print(f"  {k} = {v}")

    # debug each card type
    debug_card(row, "loan")
    debug_card(row, "emi")
    debug_card(row, "bank")
    print("Debug images generated in:", OUTPUT_DIR)

if __name__ == "__main__":
    main()
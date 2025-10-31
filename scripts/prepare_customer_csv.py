import pandas as pd, os, re, datetime, logging

RAW_PATH = "data/customers_raw.csv"
OUT_PATH = "data/customers_master.csv"
LOG_PATH = "logs/data_validation.log"
DEFAULT_LOGO = "assets/logos/default.png"

os.makedirs("logs", exist_ok=True)

logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s %(message)s")

def validate_phone(phone):
    return bool(re.match(r"^\+91\d{10}$", str(phone).strip()))

def validate_date(date_str):
    try:
        datetime.datetime.strptime(date_str, "%d-%b-%Y")
        return True
    except Exception:
        return False

def prepare_customer_csv():
    df = pd.read_csv(RAW_PATH)
    df.columns = [c.strip().lower() for c in df.columns]

    required_cols = [
        "id","name","language","loan_amount","emi_amount","due_date",
        "bank_name","branch_name","ifsc","bank_logo_path","phone_number"
    ]
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    valid_langs = {"hindi","tamil","telugu","kannada"}
    valid_rows = []
    for _, r in df.iterrows():
        errors = []
        if not isinstance(r["name"], str) or not r["name"].replace(" ", "").isalpha():
            errors.append("Invalid name")
        if r["language"] not in valid_langs:
            errors.append("Invalid language")
        if not str(r["loan_amount"]).isdigit() or int(r["loan_amount"]) <= 0:
            errors.append("Invalid loan_amount")
        if not str(r["emi_amount"]).isdigit() or int(r["emi_amount"]) <= 0:
            errors.append("Invalid emi_amount")
        if not validate_date(str(r["due_date"])):
            errors.append("Invalid due_date")
        if not os.path.exists(str(r["bank_logo_path"])):
            r["bank_logo_path"] = DEFAULT_LOGO
        if not validate_phone(r["phone_number"]):
            errors.append("Invalid phone_number")

        if errors:
            logging.info(f"Row {r['id']} skipped: {errors}")
            continue
        valid_rows.append(r)

    clean_df = pd.DataFrame(valid_rows)
    clean_df.to_csv(OUT_PATH, index=False)
    print(f"✅ Cleaned CSV saved: {OUT_PATH} ({len(clean_df)} valid rows)")

if __name__ == "__main__":
    prepare_customer_csv()

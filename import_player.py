# """
# ╔══════════════════════════════════════════════════════════════╗
# ║         CricBid — Excel Player Importer                      ║
# ║  Reads your Excel file and inserts players into auction.db   ║
# ╚══════════════════════════════════════════════════════════════╝
#
# HOW TO USE:
# 1. Install openpyxl:   pip install openpyxl
# 2. Put this file in the same folder as your app.py  (D:\New_Things\cricbid\)
# 3. Set EXCEL_FILE below to your Excel filename
# 4. Set the COLUMN_MAP to match your Excel column headers
# 5. Run:  python import_players.py
# """

import sqlite3
import os
import sys

# ─────────────────────────────────────────────────────────────
#  STEP 1 — Set your Excel filename here
# ─────────────────────────────────────────────────────────────
EXCEL_FILE = r'./player.xlsx'          # ← change this to your file name

# ─────────────────────────────────────────────────────────────
#  STEP 2 — Map YOUR Excel column headers to the DB fields
#
#  Left side  = DB field name  (don't change these)
#  Right side = your Excel column header exactly as it appears
#               Set to None if your file doesn't have that column
# ─────────────────────────────────────────────────────────────
COLUMN_MAP = {
    'name':         'NAME',                                                 # REQUIRED — player's full name
    'type':         'What is your strongest skill in cricket?',             # Batsman / Bowler / Fielder / All-Rounder / Wicket-Keeper
    'department':   'DEPARTMENT',                                           # R&D / QA / Development etc.
    'base_price':   'BASE_PRICE',                                                     # number e.g. 100, 150, 200  (set None to use default)
    'photo':        None,                                                   # set to column name if you have photo paths, else None
}

# ─────────────────────────────────────────────────────────────
#  STEP 3 — Default values (used when a column is missing/empty)
# ─────────────────────────────────────────────────────────────
DEFAULTS = {
    'type':         'All-Rounder',
    'department':   'Development',
    'base_price':   500000,
    'photo':        '',
}

# Valid values — any value not in these lists gets replaced with the default
VALID_TYPES = [
    'Batsman', 'Bowler', 'Fielder', 'All-Rounder', 'Wicket-Keeper'
]
VALID_DEPARTMENTS = [
    'R&D', 'QA', 'Development', 'DevOps', 'Design',
    'Data Science', 'Management', 'Sales', 'Marketing',
    'HR', 'Finance', 'Support'
]

# ─────────────────────────────────────────────────────────────
#  STEP 4 — DB file path (same folder as app.py by default)
# ─────────────────────────────────────────────────────────────
DB_FILE = 'auction.db'

# ══════════════════════════════════════════════════════════════
#  IMPORT LOGIC — no need to edit below
# ══════════════════════════════════════════════════════════════

def clean_type(val):
    if not val:
        return DEFAULTS['type']
    val = str(val).strip()
    # Case-insensitive match
    for vt in VALID_TYPES:
        if vt.lower() == val.lower():
            return vt
    # Partial match
    val_low = val.lower()
    if 'bat'   in val_low: return 'Batsman'
    if 'bowl'  in val_low: return 'Bowler'
    if 'field' in val_low: return 'Fielder'
    if 'all'   in val_low: return 'All-Rounder'
    if 'keep'  in val_low or 'wicket' in val_low or 'wk' in val_low: return 'Wicket-Keeper'
    print(f"  ⚠  Unknown type '{val}' → using '{DEFAULTS['type']}'")
    return DEFAULTS['type']

def clean_dept(val):
    if not val:
        return DEFAULTS['department']
    val = str(val).strip()
    for vd in VALID_DEPARTMENTS:
        if vd.lower() == val.lower():
            return vd
    # If not in list, keep as-is (custom department)
    return val

def clean_price(val):
    try:
        price = int(float(str(val).replace(',', '').strip()))
        return max(50, price)   # minimum base price = 50
    except (ValueError, TypeError):
        return DEFAULTS['base_price']

def get_cell(row, headers, col_name):
    """Get cell value from row by column name. Returns None if col not mapped or missing."""
    if col_name is None:
        return None
    mapped = COLUMN_MAP.get(col_name)
    if mapped is None or mapped not in headers:
        return None
    idx = headers.index(mapped)
    if idx >= len(row):
        return None
    val = row[idx]
    return str(val).strip() if val is not None else None

def run_import():
    # ── Check dependencies ──────────────────────────────────────
    try:
        import openpyxl
    except ImportError:
        print("❌  openpyxl is not installed.")
        print("    Run:  pip install openpyxl")
        sys.exit(1)

    # ── Check files ─────────────────────────────────────────────
    if not os.path.exists(EXCEL_FILE):
        print(f"❌  Excel file not found: {EXCEL_FILE}")
        print(f"    Make sure the file is in: {os.path.abspath('.')}")
        sys.exit(1)

    if not os.path.exists(DB_FILE):
        print(f"❌  Database not found: {DB_FILE}")
        print(f"    Make sure you're running this from the cricbid folder")
        sys.exit(1)

    # ── Load Excel ──────────────────────────────────────────────
    print(f"\n📂  Loading {EXCEL_FILE} ...")
    wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    if not rows:
        print("❌  Excel file is empty.")
        sys.exit(1)

    # First row = headers
    raw_headers = [str(h).strip() if h is not None else '' for h in rows[0]]
    data_rows   = rows[1:]

    print(f"    Found columns: {raw_headers}")
    print(f"    Found {len(data_rows)} data rows\n")

    # ── Validate column mapping ─────────────────────────────────
    print("🗺   Column mapping check:")
    for db_field, excel_col in COLUMN_MAP.items():
        if excel_col is None:
            print(f"    {db_field:15s} ← (not mapped, will use default: {DEFAULTS.get(db_field, '')})")
        elif excel_col in raw_headers:
            print(f"    {db_field:15s} ← '{excel_col}' ✅")
        else:
            if db_field == 'name':
                print(f"    {db_field:15s} ← '{excel_col}' ❌  COLUMN NOT FOUND — REQUIRED!")
                print(f"\n    Available columns: {raw_headers}")
                print(f"    Update COLUMN_MAP in this script to match your column names.")
                sys.exit(1)
            else:
                print(f"    {db_field:15s} ← '{excel_col}' ⚠  not found, using default")

    print()

    # ── Connect DB ─────────────────────────────────────────────
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row

    # ── Preview first 3 rows ────────────────────────────────────
    print("👀  Preview (first 3 rows):")
    for i, row in enumerate(data_rows[:3]):
        name = get_cell(row, raw_headers, 'name') or ''
        ptype = clean_type(get_cell(row, raw_headers, 'type'))
        dept  = clean_dept(get_cell(row, raw_headers, 'department'))
        price = clean_price(get_cell(row, raw_headers, 'base_price'))
        print(f"    {i+1}. {name:25s} | {ptype:15s} | {dept:15s} | ₹{price}")

    print()
    answer = input("▶  Proceed with import? (yes/no): ").strip().lower()
    if answer not in ('yes', 'y'):
        print("Cancelled.")
        db.close()
        sys.exit(0)

    # ── Import ──────────────────────────────────────────────────
    print("\n⏳  Importing players...\n")

    inserted  = 0
    skipped   = 0
    duplicate = 0
    errors    = 0

    for i, row in enumerate(data_rows, start=2):  # start=2 because row 1 is header

        # Skip completely empty rows
        if all(v is None or str(v).strip() == '' for v in row):
            skipped += 1
            continue

        # Get name (required)
        name = get_cell(row, raw_headers, 'name')
        if not name or name == 'None':
            print(f"    Row {i}: ⚠  Skipping — no name")
            skipped += 1
            continue

        # Get other fields
        ptype = clean_type(get_cell(row, raw_headers, 'type'))
        dept  = clean_dept(get_cell(row, raw_headers, 'department'))
        price_raw = get_cell(row, raw_headers, 'base_price')
        price = clean_price(price_raw) if price_raw else DEFAULTS['base_price']
        photo_raw = get_cell(row, raw_headers, 'photo')
        photo = photo_raw if photo_raw and photo_raw != 'None' else ''

        # Check duplicate name
        existing = db.execute('SELECT id FROM players WHERE name=?', (name,)).fetchone()
        if existing:
            print(f"    Row {i}: ⚠  '{name}' already exists (ID {existing['id']}) — skipping")
            duplicate += 1
            continue

        # Insert
        try:
            db.execute(
                'INSERT INTO players (name, type, department, photo, base_price) VALUES (?,?,?,?,?)',
                (name, ptype, dept, photo, price)
            )
            print(f"    Row {i}: ✅  {name:25s} | {ptype:15s} | {dept:15s} | ₹{price}")
            inserted += 1
        except Exception as e:
            print(f"    Row {i}: ❌  Error inserting '{name}': {e}")
            errors += 1

    db.commit()
    db.close()

    # ── Summary ─────────────────────────────────────────────────
    print(f"""
╔══════════════════════════════════╗
║         Import Complete!         ║
╠══════════════════════════════════╣
║  ✅  Inserted   : {inserted:>4}             ║
║  ⚠   Duplicates : {duplicate:>4} (skipped)   ║
║  ⚪  Empty rows : {skipped:>4} (skipped)   ║
║  ❌  Errors     : {errors:>4}             ║
╚══════════════════════════════════╝

Players are now in {DB_FILE}
Start your app and they will appear in the Players section.
""")

if __name__ == '__main__':
    run_import()
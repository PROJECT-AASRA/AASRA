r"""
AASRA Demo Data Importer
Imports external disaster and telemetry datasets from D:\demo into SQLite (disaster.db).
Creates or updates 5 dedicated tables:
- flood_history (107 records)
- historical_disasters (3,946 records)
- rainfall_history (7,208 records)
- river_levels (440 records)
- uttarakhand_landslides (5,523 records)
- danger_levels (13 records)
"""

import os
import re
import html
import sqlite3
import pandas as pd
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "disaster.db"
DUMP_PATH = BASE_DIR / "disaster_dump.sql"
DEMO_DIR = Path(r"D:\demo")


def clean_col_name(c: str) -> str:
    """Sanitize column name for SQLite compatibility."""
    c = html.unescape(str(c))
    c = c.replace('"', '').replace("'", "")
    c = re.sub(r"[^\w\s]", "_", c)
    c = re.sub(r"\s+", "_", c)
    c = re.sub(r"_+", "_", c)
    return c.strip("_").lower()


def get_unique_columns(raw_cols):
    """Deduplicate sanitized column names."""
    cleaned = [clean_col_name(c) for c in raw_cols]
    seen = {}
    deduped = []
    for c in cleaned:
        if not c:
            c = "unnamed"
        if c in seen:
            seen[c] += 1
            deduped.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            deduped.append(c)
    return deduped


def import_demo_data(demo_folder: Path = DEMO_DIR) -> dict:
    if not demo_folder.exists():
        raise FileNotFoundError(f"Folder '{demo_folder}' does not exist!")

    datasets = [
        {
            "file": "flood_history.csv.xls",
            "table": "flood_history",
            "sep": ",",
            "skiprows": 0,
            "encoding": "utf-8",
        },
        {
            "file": "historical_disasters.csv.xls",
            "table": "historical_disasters",
            "sep": "\t",
            "skiprows": 1,
            "encoding": "utf-8",
        },
        {
            "file": "rainfall_history.csv.xls",
            "table": "rainfall_history",
            "sep": ",",
            "skiprows": 0,
            "encoding": "utf-8",
        },
        {
            "file": "river_levels.csv.xls",
            "table": "river_levels",
            "sep": ",",
            "skiprows": 0,
            "encoding": "utf-8",
        },
        {
            "file": "uttarakhand_landslides.csv",
            "table": "uttarakhand_landslides",
            "sep": ",",
            "skiprows": 0,
            "encoding": "utf-8-sig",
        },
        {
            "file": "uttarakhand_danger_level_qgis.csv",
            "table": "danger_levels",
            "sep": ",",
            "skiprows": 0,
            "encoding": "utf-8",
        },
    ]

    print("==================================================")
    print("  PROJECT AASRA - IMPORTING DEMO DATASETS TO SQLITE")
    print("==================================================")
    print(f"Source Folder   : {demo_folder}")
    print(f"Target Database : {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    results = {}

    for item in datasets:
        fpath = demo_folder / item["file"]
        tname = item["table"]
        print(f"\nProcessing '{item['file']}' -> Table '{tname}'...")

        if not fpath.exists():
            print(f"  [ERROR] File not found: {fpath}")
            continue

        try:
            df = pd.read_csv(
                fpath,
                sep=item["sep"],
                skiprows=item["skiprows"],
                encoding=item["encoding"],
                low_memory=False,
            )
            df.columns = get_unique_columns(df.columns)

            # Write to SQLite
            df.to_sql(tname, con=conn, if_exists="replace", index=False)

            # Verify row count
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {tname}")
            count = cur.fetchone()[0]

            results[tname] = {
                "file": item["file"],
                "rows": count,
                "columns": len(df.columns),
                "status": "SUCCESS",
            }
            print(f"  [SUCCESS] {count} rows, {len(df.columns)} columns saved into table '{tname}'.")
        except Exception as e:
            results[tname] = {"file": item["file"], "status": f"FAILED: {e}"}
            print(f"  [FAILED] {e}")

    # Create convenience views for flexible querying of danger levels
    try:
        cur = conn.cursor()
        cur.execute("DROP VIEW IF EXISTS danger_level")
        cur.execute("DROP VIEW IF EXISTS uttarakhand_danger_levels")
        cur.execute("DROP VIEW IF EXISTS uttarakhand_danger_level_qgis")
        cur.execute("CREATE VIEW danger_level AS SELECT * FROM danger_levels")
        cur.execute("CREATE VIEW uttarakhand_danger_levels AS SELECT * FROM danger_levels")
        cur.execute("CREATE VIEW uttarakhand_danger_level_qgis AS SELECT * FROM danger_levels")
        conn.commit()
    except Exception as e:
        print(f"  [WARNING] Could not create convenience views: {e}")

    conn.close()

    # Re-export disaster_dump.sql
    print("\n--------------------------------------------------")
    print("Updating SQL Dump file (disaster_dump.sql)...")
    try:
        conn = sqlite3.connect(str(DB_PATH))
        with open(str(DUMP_PATH), "w", encoding="utf-8") as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")
        conn.close()
        dump_size_kb = DUMP_PATH.stat().st_size / 1024
        print(f"SQL Dump updated successfully ({dump_size_kb:.2f} KB).")
    except Exception as e:
        print(f"Warning updating SQL dump: {e}")

    print("==================================================")
    print("  DATA IMPORT COMPLETED")
    print("==================================================")
    return results


if __name__ == "__main__":
    import_demo_data()

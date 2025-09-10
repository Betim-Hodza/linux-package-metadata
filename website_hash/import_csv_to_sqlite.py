#!/usr/bin/env python3
"""
Import a huge CSV into a SQLite DB and create indexes.
Run once (or whenever the CSV changes).
"""

import csv
import sqlite3
import sys
from pathlib import Path

CSV_PATH = Path("data.csv")          # <-- your source file
DB_PATH  = Path("data.db")           # <-- will be created/overwritten

COLUMNS = ["name", "version", "sha256", "file", "url"]
TABLE   = "files"

def create_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    # Drop old table (optional)
    cur.execute(f"DROP TABLE IF EXISTS {TABLE}")

    # Create a table with TEXT columns (all strings)
    cols_sql = ", ".join(f"{c} TEXT" for c in COLUMNS)
    cur.execute(f"CREATE TABLE {TABLE} ({cols_sql})")

    # Indexes for fast search & sorting
    cur.execute(f"CREATE INDEX idx_name    ON {TABLE}(name)")
    cur.execute(f"CREATE INDEX idx_version ON {TABLE}(version)")
    cur.execute(f"CREATE INDEX idx_sha256  ON {TABLE}(sha256)")
    cur.execute(f"CREATE INDEX idx_file    ON {TABLE}(file)")
    cur.execute(f"CREATE INDEX idx_url     ON {TABLE}(url)")
    conn.commit()

def import_csv(conn: sqlite3.Connection):
    cur = conn.cursor()
    batch = []
    batch_size = 10_000          # tune for your RAM/IO

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # sanity‑check columns
        missing = set(COLUMNS) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV missing columns: {missing}")

        for i, row in enumerate(reader, start=1):
            batch.append(tuple(row[col] for col in COLUMNS))
            if len(batch) >= batch_size:
                cur.executemany(f"INSERT INTO {TABLE} VALUES ({','.join('?'*len(COLUMNS))})", batch)
                conn.commit()
                batch.clear()
                print(f"Inserted {i:,} rows...", end="\r")
        # final remainder
        if batch:
            cur.executemany(f"INSERT INTO {TABLE} VALUES ({','.join('?'*len(COLUMNS))})", batch)
            conn.commit()
    print(f"\n✅ Finished importing {i:,} rows into {DB_PATH}")

def main():
    if not CSV_PATH.is_file():
        sys.exit(f"❌ CSV file not found: {CSV_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)
        import_csv(conn)
    finally:
        conn.close()

if __name__ == "__main__":
    main()

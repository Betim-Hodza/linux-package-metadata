# import_one_csv.py
import csv, sqlite3, pathlib, sys

def import_csv(csv_path: pathlib.Path, db_path: pathlib.Path):
    cols = ["name", "version", "sha256", "file", "url"]
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS files")
    cur.execute(f"CREATE TABLE files ({', '.join(c+' TEXT' for c in cols)})")
    # create the same indexes as before
    for c in cols:
        cur.execute(f"CREATE INDEX idx_{c} ON files({c})")
    conn.commit()

    batch = []
    batch_sz = 10_000
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for i, row in enumerate(rdr, 1):
            batch.append(tuple(row[c] for c in cols))
            if len(batch) >= batch_sz:
                cur.executemany(f"INSERT INTO files VALUES ({','.join('?'*len(cols))})", batch)
                conn.commit()
                batch.clear()
                print(f"\r{csv_path.name}: {i:,} rows imported …", end="")
        if batch:
            cur.executemany(f"INSERT INTO files VALUES ({','.join('?'*len(cols))})", batch)
            conn.commit()
    print(f"\n✅ {csv_path.name} → {db_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python import_one_csv.py <csv_path> <db_path>")
    import_csv(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
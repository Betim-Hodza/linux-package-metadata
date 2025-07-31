import csv
import random

CSV_FILE = "combined_packages.csv"

def select_random_row(csv_file):
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # Skip header
        rows = list(reader)

    if not rows:
        print("⚠️ No data rows found.")
        return

    random_row = random.choice(rows)
    print(dict(zip(header, random_row)))  # Pretty print as dict

if __name__ == "__main__":
    select_random_row(CSV_FILE)

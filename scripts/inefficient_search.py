import csv
import sys

CSV_FILE = "combined_packages.csv"

def search_csv(search_term, csv_file):
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if row and row[0] == search_term:
                print(dict(zip(header, row)))
                return
    print(f"❌ No match found for: {search_term}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python search_combined_csv.py <search_term>")
        sys.exit(1)

    search_term = sys.argv[1]
    search_csv(search_term, CSV_FILE)

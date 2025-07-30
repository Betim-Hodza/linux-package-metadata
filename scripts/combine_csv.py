#!/usr/bin/env python3
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import csv
import glob
import os
import argparse
from pathlib import Path
from collections import defaultdict

def get_distribution_from_path(filepath):
    """Extract distribution name from file path."""
    path = Path(filepath)
    # Get parent directory name (e.g., 'rocky', 'ubuntu', 'centos')
    return path.parent.name

def combine_all_into_single_csv(output_file="combined_all_packages.csv"):
    """Combine all CSV files into a single file."""
    input_files = sorted(glob.glob("./output/*/*_packages.csv"))
    if not input_files:
        print("❌ No matching CSV files found.")
        return

    print(f"🔍 Found {len(input_files)} CSV files to combine")
    
    header_written = False
    total_rows = 0
    
    with open(output_file, "w", newline="", encoding="utf-8") as outfile:
        writer = None
        for filepath in input_files:
            print(f"📄 Processing: {filepath}")
            with open(filepath, "r", encoding="utf-8") as infile:
                reader = csv.reader(infile)
                try:
                    header = next(reader)
                except StopIteration:
                    print(f"⚠️ Skipped empty file: {filepath}")
                    continue

                if not header_written:
                    writer = csv.writer(outfile)
                    writer.writerow(header)
                    header_written = True

                file_rows = 0
                for row in reader:
                    writer.writerow(row)
                    file_rows += 1
                    total_rows += 1
                
                print(f"   ✓ Added {file_rows} packages")

    print(f"✅ Combined {len(input_files)} files with {total_rows} total packages into {output_file}")

def combine_by_distribution():
    """Combine CSV files into one file per distribution."""
    input_files = sorted(glob.glob("./output/*/*_packages.csv"))
    if not input_files:
        print("❌ No matching CSV files found.")
        return

    # Group files by distribution
    files_by_dist = defaultdict(list)
    for filepath in input_files:
        dist = get_distribution_from_path(filepath)
        files_by_dist[dist].append(filepath)

    print(f"🔍 Found files for {len(files_by_dist)} distributions")
    
    for dist, files in files_by_dist.items():
        output_file = f"combined_{dist}_packages.csv"
        print(f"\n📦 Combining {dist} files into {output_file}")
        
        header_written = False
        total_rows = 0
        
        with open(output_file, "w", newline="", encoding="utf-8") as outfile:
            writer = None
            for filepath in sorted(files):
                print(f"   📄 Processing: {os.path.basename(filepath)}")
                with open(filepath, "r", encoding="utf-8") as infile:
                    reader = csv.reader(infile)
                    try:
                        header = next(reader)
                    except StopIteration:
                        print(f"   ⚠️ Skipped empty file: {filepath}")
                        continue

                    if not header_written:
                        writer = csv.writer(outfile)
                        writer.writerow(header)
                        header_written = True

                    file_rows = 0
                    for row in reader:
                        writer.writerow(row)
                        file_rows += 1
                        total_rows += 1
                    
                    print(f"      ✓ Added {file_rows} packages")
        
        print(f"   ✅ Created {output_file} with {total_rows} packages")

def list_available_files():
    """List all available CSV files organized by distribution."""
    input_files = sorted(glob.glob("./output/*/*_packages.csv"))
    if not input_files:
        print("❌ No CSV files found.")
        return

    files_by_dist = defaultdict(list)
    for filepath in input_files:
        dist = get_distribution_from_path(filepath)
        files_by_dist[dist].append(filepath)

    print("📋 Available CSV files:")
    for dist, files in sorted(files_by_dist.items()):
        print(f"\n📦 {dist.upper()}:")
        for filepath in sorted(files):
            filename = os.path.basename(filepath)
            # Get file size
            size = os.path.getsize(filepath)
            size_str = f"{size:,} bytes" if size < 1024*1024 else f"{size/(1024*1024):.1f} MB"
            print(f"   • {filename} ({size_str})")
    
    print(f"\n📊 Total: {len(input_files)} files across {len(files_by_dist)} distributions")

def main():
    parser = argparse.ArgumentParser(
        description="Combine CSV package files from different Linux distributions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --all                    # Combine all files into one CSV
  %(prog)s --by-distribution        # Create one CSV per distribution
  %(prog)s --list                   # List available files
  %(prog)s --all --output custom.csv # Combine all with custom filename

Licensed under the Apache License, Version 2.0
See: http://www.apache.org/licenses/LICENSE-2.0
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all', action='store_true',
                       help='Combine all CSV files into a single file')
    group.add_argument('--by-distribution', action='store_true',
                       help='Create one combined CSV per distribution')
    group.add_argument('--list', action='store_true',
                       help='List all available CSV files')
    
    parser.add_argument('--output', '-o', default='combined_all_packages.csv',
                        help='Output filename for --all mode (default: combined_all_packages.csv)')
    
    args = parser.parse_args()
    
    if args.list:
        list_available_files()
    elif args.all:
        combine_all_into_single_csv(args.output)
    elif args.by_distribution:
        combine_by_distribution()

if __name__ == "__main__":
    main()

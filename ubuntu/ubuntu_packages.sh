#!/bin/bash

# Set the base URL components
UBUNTU_COMPONENTS=("main" "restricted" "universe" "multiverse")

# Set the temporary directory
TEMP_DIR="temp"
mkdir -p "$TEMP_DIR"

# Set the output directory
OUTPUT_DIR="packages"
mkdir -p "$OUTPUT_DIR"

# Initialize CSV files with headers
echo "name,version,sha256,url" > "$OUTPUT_DIR/packages.csv"
echo "name,version,sha256,file,url" > "$OUTPUT_DIR/files.csv"

# Files for intermediate URLs
LETTERS_FILE="$TEMP_DIR/letters.txt"
SUBFOLDERS_FILE="$TEMP_DIR/subfolders.txt"
URLS_FILE="$TEMP_DIR/urls.txt"

> "$LETTERS_FILE"
> "$SUBFOLDERS_FILE"
> "$URLS_FILE"

# Collect letter URLs sequentially
for component in "${UBUNTU_COMPONENTS[@]}"; do
  base_url="https://mirrors.kernel.org/ubuntu/pool/${component}"
  
  # Get folders (letters)
  folders=$(curl -s -L "$base_url" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/' | grep -v '^\.$' | grep -v '^\.\.$' | grep -v '^?')
  
  for folder in $folders; do
    echo "$base_url/$folder" >> "$LETTERS_FILE"
  done
done

# Function to get subfolders (package directories) from a letter URL
get_subfolders() {
  local letter_url="$1"
  
  # Get subfolders
  subfolders=$(curl -s -L "$letter_url" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/' | grep -v '^\.$' | grep -v '^\.\.$' | grep -v '^?')
  
  local lines=""
  for subfolder in $subfolders; do
    lines+="$letter_url/$subfolder"$'\n'
  done
  
  # Append with locking
  flock -x 202
  printf "%s" "$lines" >> "$SUBFOLDERS_FILE"
  flock -u 202
}

# Export function and variables
export -f get_subfolders
export SUBFOLDERS_FILE

# Setup lock for subfolders file
exec 202>>"$SUBFOLDERS_FILE"

# Parallelize getting subfolders
cat "$LETTERS_FILE" | xargs -P 100 -I {} bash -c 'get_subfolders "{}"'

# Function to get package URLs from a subfolder URL
get_packages() {
  local subfolder_url="$1"
  
  # Get packages
  packages=$(curl -s -L "$subfolder_url" | grep -oE '<a href="[^"]+\.deb">[^<]+\.deb</a>' | sed -r 's/<a href="([^"]+\.deb)">[^<]+\.deb<\/a>/\1/')
  
  local lines=""
  for package in $packages; do
    lines+="$subfolder_url/$package"$'\n'
  done
  
  # Append with locking
  flock -x 203
  printf "%s" "$lines" >> "$URLS_FILE"
  flock -u 203
}

# Export function and variables
export -f get_packages
export URLS_FILE

# Setup lock for URLs file
exec 203>>"$URLS_FILE"

# Parallelize getting packages
cat "$SUBFOLDERS_FILE" | xargs -P 100 -I {} bash -c 'get_packages "{}"'

# Function to process a single package URL
process_package() {
  local PACKAGE_URL="$1"
  local PACKAGE=$(basename "$PACKAGE_URL")
  local PACKAGE_FILE="$TEMP_DIR/$PACKAGE"
  
  # Download the package
  wget -q -O "$PACKAGE_FILE" "$PACKAGE_URL"
  
  # Extract name and version (assuming standard naming: name_version_arch.deb)
  PACKAGE_NAME=$(echo "$PACKAGE" | cut -d '_' -f 1)
  PACKAGE_VERSION=$(echo "$PACKAGE" | cut -d '_' -f 2)
  
  local PACKAGE_DIR="$TEMP_DIR/$PACKAGE_NAME-$PACKAGE_VERSION-$$"  # Add PID to avoid collisions
  
  mkdir -p "$PACKAGE_DIR"
  dpkg-deb -x "$PACKAGE_FILE" "$PACKAGE_DIR"
  
  # Calculate SHA-256 sum of the package file
  local PACKAGE_SHA256SUM=$(sha256sum "$PACKAGE_FILE" | cut -d ' ' -f 1)
  
  # Append package metadata with locking to handle concurrency
  flock -x 200
  echo "$PACKAGE_NAME,$PACKAGE_VERSION,$PACKAGE_SHA256SUM,$PACKAGE_URL" >> "$OUTPUT_DIR/packages.csv"
  flock -u 200
  
  # Loop through all files in the package
  while IFS= read -r -d '' FILE; do
    local FILE_SHA256SUM=$(sha256sum "$FILE" | cut -d ' ' -f 1)
    local RELATIVE_FILE="${FILE#$PACKAGE_DIR/}"  # Make file path relative to package root
    
    # Append file metadata with locking
    flock -x 201
    echo "$PACKAGE_NAME,$PACKAGE_VERSION,$FILE_SHA256SUM,$RELATIVE_FILE,$PACKAGE_URL" >> "$OUTPUT_DIR/files.csv"
    flock -u 201
  done < <(find "$PACKAGE_DIR" -type f -print0)
  
  # Cleanup
  rm "$PACKAGE_FILE"
  rm -rf "$PACKAGE_DIR"
}

# Export the function for xargs
export -f process_package
export TEMP_DIR OUTPUT_DIR

# Setup file descriptors for locking (assuming flock is available)
exec 200>>"$OUTPUT_DIR/packages.csv"
exec 201>>"$OUTPUT_DIR/files.csv"

# Process URLs in parallel using xargs (adjust -P for number of parallel processes, e.g., 10)
cat "$URLS_FILE" | xargs -P 100 -I {} bash -c 'process_package "{}"'

# Cleanup
rm "$LETTERS_FILE" "$SUBFOLDERS_FILE" "$URLS_FILE"
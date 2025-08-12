#!/bin/bash

XARGS_PROCESSES=50
# -1: not downloaded, 0: downloaded but hash isnt saved, 1: downloaded and saved hash
STATE=("-1" "0" "1")

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
LETTERS_FILE="temp/letters.txt"
SUBFOLDERS_FILE="temp/subfolders.txt"
URLS_FILE="temp/urls.csv"

# Collect letter URLs sequentially
for component in "${UBUNTU_COMPONENTS[@]}"; do
  base_url="https://mirrors.kernel.org/ubuntu/pool/${component}"

  # Get folders (letters)
  folders=$(curl -s -L "$base_url" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+</a>/\1/' | grep -v '^.' | grep -v '^\.\.' | grep -v '^?')
  
  for folder in $folders; do
    echo "$base_url/$folder" >> "$LETTERS_FILE"
  done
done

# Function to get subfolders (package directories) from a letter URL
get_subfolders() 
{
  local letter_url="$1"

  # get subfolders from letter
  subfolders=$(curl -s -L "$letter_url" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+</a>/\1/' | grep -v '^.' | grep -v '^\.\.' | grep -v '^?')
  
  local lines=""
  for subfolder in $subfolders; do
    lines+="$letter_url/$subfolder\n"
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
cat "$LETTERS_FILE" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_subfolders "{}"'

# Function to get package URLs from a subfolder URL
get_packages() 
{
  local subfolder_url="$1"
  
  # get packages
  packages=$(curl -s -L "$subfolder_url" | grep -oE '<a href="[^"]+.deb">[^<]+.deb</a>' | sed -r 's/<a href="([^"]+.deb)">[^<]+.deb</a>/\1/')
  
  local lines=""
  # mark packages as not worked on yet
  for package in $packages; do
    lines+="$subfolder_url/$package,${STATE[0]}\n"
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
cat "$SUBFOLDERS_FILE" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_packages "{}"'

# Function to process a single package URL
process_package() 
{
  local PACKAGE_URL="$1"
  local STATUS="$2"
  local PACKAGE=$(basename "$PACKAGE_URL")
  local PACKAGE_FILE="temp/$PACKAGE"
  local UNIQUE_ID=$(uuidgen || echo "$$-RANDOM")
  local PACKAGE_DIR="temp/$PACKAGE-$UNIQUE_ID"

  # only process files that havent been processed 0 or -1
  if [ "$STATUS" != "${STATE[2]}" ]; then
    return
  fi

  # Download the package
  if ! wget -q -O "$PACKAGE_FILE" "$PACKAGE_URL"; then
    echo "Error: Failed to download $PACKAGE_URL" >&2

    # state remains at -1 to indicate we have no downloaded the package
    return
  fi

  # Update status to -1 -> 0 (in progress)
  sed -i "s|$PACKAGE_URL,${STATE[0]}|$PACKAGE_URL,${STATE[1]}|g" "$URLS_FILE"

  # Extract name and version (assuming standard naming: name_version_arch.deb)
  local PACKAGE_NAME=$(echo "$PACKAGE" | cut -d '_' -f 1)
  local PACKAGE_VERSION=$(echo "$PACKAGE" | cut -d '_' -f 2)

  mkdir -p "$PACKAGE_DIR" || { echo "Error: Failed to create $PACKAGE_DIR" >&2; return; }

  if ! dpkg-deb -x "$PACKAGE_FILE" "$PACKAGE_DIR" 2>/dev/null; then
    echo "Error: failed to extract $PACKAGE_FILE" >&2
    rm -f "$PACKAGE_FILE"
    rm -rf "$PACKAGE_DIR"

    # if we fail to extract, remain at 0 as its a failed status
    return
  fi

  # Calculate SHA-256 sum of the package file
  local PACKAGE_SHA256SUM=$(sha256sum "$PACKAGE_FILE" | cut -d ' ' -f 1)

  # Append package metadata
  echo "$PACKAGE_NAME,$PACKAGE_VERSION,$PACKAGE_SHA256SUM,$PACKAGE_URL" >> "$OUTPUT_DIR/packages.csv"

  # Loop through all files in the package
  while IFS= read -r -d '' FILE; do
    local FILE_SHA256SUM=$(sha256sum "$FILE" | cut -d ' ' -f 1)
    local RELATIVE_FILE="${FILE#$PACKAGE_DIR/}"
    echo "$PACKAGE_NAME,$PACKAGE_VERSION,$FILE_SHA256SUM,$RELATIVE_FILE,$PACKAGE_URL" >> "$OUTPUT_DIR/files.csv"
  done < <(find "$PACKAGE_DIR" -type f -print0)

  # Cleanup
  rm "$PACKAGE_FILE"
  rm -rf "$PACKAGE_DIR"
  # Update status from 0 -> 1 (obtained hash)
  sed -i "s|$PACKAGE_URL,${STATE[1]}|$PACKAGE_URL,${STATE[2]}|g" "$URLS_FILE"
}

# Export the function for xargs
export -f process_package
export TEMP_DIR
export OUTPUT_DIR

# Process URLs in parallel using xargs
cat "$URLS_FILE" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'process_package "{}"'

# Cleanup
rm "$LETTERS_FILE" "$SUBFOLDERS_FILE" "$URLS_FILE"
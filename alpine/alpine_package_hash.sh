#!/bin/bash

# Set the base URL components
ALPINE_VERSIONS=("v3.0" "v3.1" "v3.10" "v3.11" "v3.12" "v3.13" "v3.14" "v3.15" "v3.16" "v3.17" "v3.18" "v3.19" "v3.2" "v3.20" "v3.21" "v3.22" "v3.3" "v3.4" "v3.5" "v3.6" "v3.7" "v3.8" "v3.9" "latest-stable" "edge")

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
SUBFOLDERS_FILE="$TEMP_DIR/subfolders.txt"
URLS_FILE="$TEMP_DIR/urls.txt"

> "$SUBFOLDERS_FILE"
> "$URLS_FILE"



# Function to get subfolders (package directories) from a letter URL
get_subfolders() {
  # Collect URLs sequentially for each version
  for version in "${ALPINE_VERSIONS[@]}"; do
    base_url="hhttps://mirrors.edge.kernel.org/alpine/${version}/main/x86_64/"
    
    # Get folders (letters)
    folders=$(curl -s -L "$base_url" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/' | grep -v '^\.$' | grep -v '^\.\.$' | grep -v '^?')
    
    local lines=""
    for folder in $folders; do
      lines+="$letter_url/$folder"$'\n'
    done
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
  packages=$(curl -s -L "$subfolder_url" | grep -oE '<a href="[^"]+\.apk">[^<]+\.apk</a>' | sed -r 's/<a href="([^"]+\.apk)">[^<]+\.apk<\/a>/\1/')
  
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

Function to process a single package URL
process_package() {
  local PACKAGE_URL="$1"
  local PACKAGE=$(basename "$PACKAGE_URL")
  local PACKAGE_FILE="$TEMP_DIR/$PACKAGE"
  local UNIQUE_ID=$(uuidgen || echo "$$-$RANDOM")  # Use uuidgen or fallback to PID+RANDOM
  local PACKAGE_DIR="$TEMP_DIR/$PACKAGE-$UNIQUE_ID"
  
  # Download the package
  if ! wget -q -O "$PACKAGE_FILE" "$PACKAGE_URL"; then
    echo "Error: Failed to download $PACKAGE_URL" >&2
    return 
  fi
  
  # Extract name, version, and release (format: name-version-release.apk)
  PACKAGE_BASENAME=$(echo "$PACKAGE" | sed -r 's/(.+)-([^-]+-r[0-9]+)\.apk/\1/')
  PACKAGE_VERSION=$(echo "$PACKAGE" | sed -r 's/(.+)-([^-]+-r[0-9]+)\.apk/\2/')
  
  # Create temporary directory
  mkdir -p "$PACKAGE_DIR" || { echo "Error: Failed to create $PACKAGE_DIR" >&2; return 1; }
  
  # Extract package with bsdtar (works best with alpine)
  if ! bsdtar -x -f "$PACKAGE_FILE" -C "$PACKAGE_DIR" 2>/dev/null; then
    echo "Error: Failed to extract $PACKAGE_FILE" >&2
    rm -f "$PACKAGE_FILE"
    rm -rf "$PACKAGE_DIR"
    return 
  fi
  
  # Calculate SHA-256 sum of the package file
  local PACKAGE_SHA256SUM=$(sha256sum "$PACKAGE_FILE" | cut -d ' ' -f 1)
  
  # Append package metadata with locking
  flock -x 200
  echo "$PACKAGE_BASENAME,$PACKAGE_VERSION,$PACKAGE_SHA256SUM,$PACKAGE_URL" >> "$OUTPUT_DIR/packages.csv"
  flock -u 200
  
  # Loop through all files in the package, excluding metadata files
  while IFS= read -r -d '' FILE; do
    # Skip Arch-specific metadata files
    [[ "$FILE" =~ \.PKGINFO$|\.MTREE$|\.INSTALL$ ]] && continue
    
    local FILE_SHA256SUM=$(sha256sum "$FILE" | cut -d ' ' -f 1)
    local RELATIVE_FILE="${FILE#$PACKAGE_DIR/}"
    
    # Append file metadata with locking
    flock -x 201
    echo "$PACKAGE_BASENAME,$PACKAGE_VERSION,$FILE_SHA256SUM,$RELATIVE_FILE,$PACKAGE_URL" >> "$OUTPUT_DIR/files.csv"
    flock -u 201
  done < <(find "$PACKAGE_DIR" -type f -print0)
  
  # Cleanup
  rm -f "$PACKAGE_FILE"
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
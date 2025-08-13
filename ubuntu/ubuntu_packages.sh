#!/bin/bash

# GLOBALS
XARGS_PROCESSES=10
UBUNTU_COMPONENTS=("main" "restricted" "universe" "multiverse")
TEMP_DIR="temp"
OUTPUT_DIR="output"

log() 
{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

# Function to get subfolders (package directories) from a letter URL
get_subfolders() 
{
  local letter_url="$1"
  
  # Get subfolders
  subfolders=$(curl -s -L "$letter_url" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/' | grep -v '^\.$' | grep -v '^\.\.$' | grep -v '^?')
  
  local lines=""
  for subfolder in $subfolders; do
    lines+="$letter_url$subfolder"$'\n'
  done
  
  # Append with locking
  flock -x 202
  printf "%s" "$lines" >> "$SUBFOLDERS_FILE"
  flock -u 202
}

# Function to get package URLs from a subfolder URL
get_packages() 
{
  local subfolder_url="$1"
  
  # Get packages
  packages=$(curl -s -L "$subfolder_url" | grep -oE '<a href="[^"]+\.deb">[^<]+\.deb</a>' | sed -r 's/<a href="([^"]+\.deb)">[^<]+\.deb<\/a>/\1/')
  
  local lines=""
  for package in $packages; do
    lines+="$subfolder_url$package,-1"$'\n'
  done
  
  # Append with locking
  flock -x 203
  printf "%s" "$lines" >> "$URLS_FILE"
  flock -u 203

  log "urls.csv contain $(wc -l output/urls.csv) lines"
}


# Function to process a single package URL
process_package() 
{
  local LINE="$1"
  local PACKAGE_URL=$(echo "$LINE" | cut -d, -f1)
  local STATE=$(echo "$LINE" | cut -d, -f2)
  local PACKAGE=$(basename "$PACKAGE_URL")
  local PACKAGE_FILE="$TEMP_DIR/$PACKAGE"
  local UNIQUE_ID=$(uuidgen || echo "$$-$RANDOM")  # Use uuidgen or fallback to PID+RANDOM
  local PACKAGE_DIR="$TEMP_DIR/$PACKAGE-$UNIQUE_ID"
  
  # Download the package
  if ! wget -q -O "$PACKAGE_FILE" "$PACKAGE_URL"; then
    log "Error: Failed to download $PACKAGE_URL"
    return 
  fi
  
  # Update state to processing
  update_state "$PACKAGE_URL" 0

  # Extract name and version (assuming standard naming: name_version_arch.deb)
  PACKAGE_NAME=$(echo "$PACKAGE" | cut -d '_' -f 1)
  PACKAGE_VERSION=$(echo "$PACKAGE" | cut -d '_' -f 2)
  
  mkdir -p "$PACKAGE_DIR" || { echo "Error: Failed to create $PACKAGE_DIR" >&2; update_state "$PACKAGE_URL" -1; return; }
  
  if ! dpkg-deb -x "$PACKAGE_FILE" "$PACKAGE_DIR" 2>/dev/null; then
    log "Error: failed to extract $PACKAGE_FILE reverting state of $PACKAGE_URL to -1" 
    rm -f "$PACKAGE_FILE"
    rm -rf "$PACKAGE_DIR"
    update_state "$PACKAGE_URL" -1

    return
  fi
  
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
  
  # Update state to completed
  update_state "$PACKAGE_URL" 1
  
  # Cleanup
  rm "$PACKAGE_FILE"
  rm -rf "$PACKAGE_DIR"
}

update_state() 
{
  local PACKAGE_URL="$1"
  local STATE="$2"

  # Update state in URLs file using update_state.py (just so much easier T_T)
  python3 update_state.py -u "$PACKAGE_URL" -s "$STATE" -c "./$OUTPUT_DIR/urls.csv"
}

export -f log

echo "Please go grab a coffee or just leave this running idle on your server because this WILL take a looooonggg time"


# check if our dirs exist (if they do we resume)
if [[ -d "$TEMP_DIR" ]] && [[ -d "$OUTPUT_DIR" ]] && [[ -s "$OUTPUT_DIR/urls.csv" ]]; then

  log "Resuming script"

  export -f process_package
  export -f update_state
  export TEMP_DIR OUTPUT_DIR

  # Process URLs in parallel using xargs (adjust -P for number of parallel processes, e.g., 10)
  cat "$URLS_FILE" | cut -d, -f1 | xargs -P "$XARGS_PROCESSES" -I {} bash -c "process_package {}"

  PROCESSED_PACKAGES=$(wc -l < "$OUTPUT_DIR/packages.csv")
  HASHED_FILES=$(wc -l < "$OUTPUT_DIR/files.csv")
  log "Finished processing $((PROCESSED_PACKAGES - 1)) packages with $((HASHED_FILES - 1)) hashed files"
  
  exit 0
fi
mkdir -p "$TEMP_DIR"
mkdir -p "$OUTPUT_DIR"


# Initialize CSV files with headers
echo "name,version,sha256,url" > "$OUTPUT_DIR/packages.csv"
echo "name,version,sha256,file,url" > "$OUTPUT_DIR/files.csv"
echo "urls,state" > "$OUTPUT_DIR/urls.csv"

# Files for intermediate URLs
LETTERS_FILE="$TEMP_DIR/letters.txt"
SUBFOLDERS_FILE="$TEMP_DIR/subfolders.txt"
URLS_FILE="$OUTPUT_DIR/urls.csv"

log "Created temp/output dirs, initialized csv, and files"

# Check if urls.csv exists
if [ ! -f "$URLS_FILE" ]; then
  # Collect letter URLs sequentially
  for component in "${UBUNTU_COMPONENTS[@]}"; do
    base_url="https://mirrors.kernel.org/ubuntu/pool/${component}"
    
    # Get folders (letters)
    folders=$(curl -s -L "$base_url" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/' | grep -v '^\.$' | grep -v '^\.\.$' | grep -v '^?')
    
    for folder in $folders; do
      echo "$base_url/$folder" >> "$LETTERS_FILE"
    done
  done

  log "Obtained letter URLS"  
  log "Getting subfolders..."

  # Setup lock for subfolders file
  exec 202>>"$SUBFOLDERS_FILE"

  # Export function and variables
  export -f get_subfolders
  export SUBFOLDERS_FILE

  # Parallelize getting subfolders
  cat "$LETTERS_FILE" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_subfolders "{}"'

  log "Obtained subfolders"
  log "Obtaining final URLS..."

  # Setup lock for URLs file
  exec 203>>"$URLS_FILE"

  export -f get_packages
  export URLS_FILE

  # Parallelize getting packages
cat "$SUBFOLDERS_FILE" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_packages "{}"'

  log "Obtained final URLS"
fi

log "Processing Packages"

# Setup file descriptors for locking (assuming flock is available)
exec 200>>"$OUTPUT_DIR/packages.csv"
exec 201>>"$OUTPUT_DIR/files.csv"

export -f process_package
export -f update_state
export TEMP_DIR OUTPUT_DIR

# Process URLs in parallel using xargs (adjust -P for number of parallel processes, e.g., 10)
cat "$URLS_FILE" | cut -d, -f1 | xargs -P "$XARGS_PROCESSES" -I {} bash -c "process_package {}"

PROCESSED_PACKAGES=$(wc -l < "$OUTPUT_DIR/packages.csv")
HASHED_FILES=$(wc -l < "$OUTPUT_DIR/files.csv")
log "Finished processing $((PROCESSED_PACKAGES - 1)) packages with $((HASHED_FILES - 1)) hashed files"

#!/bin/bash

# Set the base URL
base_url="https://mirrors.kernel.org/ubuntu/pool/universe"

# Set the temporary directory
TEMP_DIR="temp"
mkdir -p "$TEMP_DIR"
# Set the output directory
output_dir="packages"
mkdir -p "$output_dir"

# Loop through all the folders in the universe pool
for folder in $(curl -s  -L "$base_url" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/'); do
  # Loop through all the subfolders in the current folder
  for subfolder in $(curl -s -L "$base_url/$folder" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/'); do
    # Download all the packages in the current subfolder
    for PACKAGE in $(curl -s  -L "$base_url/$folder/$subfolder" | grep -oE '<a href="[^"]+\.deb">[^<]+\.deb</a>' | sed -r 's/<a href="([^"]+\.deb)">[^<]+\.deb<\/a>/\1/'); do
      # Download the package
      PACKAGE_URL="$base_url/$folder/$subfolder/$PACKAGE"
      PACKAGE_FILE="$TEMP_DIR/$PACKAGE"
      wget -q -O "$PACKAGE_FILE" "$PACKAGE_URL"

      # get name and ver and extract deb file
      PACKAGE_NAME=$(echo "$PACKAGE" | cut -d '_' -f 1)
      PACKAGE_VERSION=$(echo "$PACKAGE" | cut -d '_' -f 2)
    
      PACKAGE_DIR="$TEMP_DIR/$PACKAGE_NAME-$PACKAGE_VERSION"
      mkdir -p "$PACKAGE_DIR"
      
      dpkg-deb -x "$PACKAGE_FILE" "$PACKAGE_DIR"

      # Calculate the SHA-256 sum for all files in the package
      SHA256SUMS=()
      FILE_PATHS=()
      for FILE in $(find "$PACKAGE_DIR" -type f); do
        SHA256SUM=$(sha256sum "$FILE" | cut -d ' ' -f 1)
        SHA256SUMS+=("$SHA256SUM")
        FILE_PATHS+=("$FILE")
      done

      # Save package metdata
      echo "$PACKAGE_NAME,$PACKAGE_VERSION,${SHA256SUMS[@]},${FILE_PATHS[@]},$PACKAGE_URL" >> "$OUTPUT_DIR/packages.csv"

      rm "$PACKAGE_FILE"
      rm -rf "$PACKAGE_DIR"

    done
  done
done

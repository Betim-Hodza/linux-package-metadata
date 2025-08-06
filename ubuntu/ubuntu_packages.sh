#!/bin/bash

# Set the base URL
UBUNTU_COMPONENTS=("main" "restricted" "universe" "multiverse")

# Set the temporary directory
TEMP_DIR="temp"
mkdir -p "$TEMP_DIR"
# Set the output directory
OUTPUT_DIR="packages"
mkdir -p "$OUTPUT_DIR"

for component in "${UBUNTU_COMPONENTS[@]}"; do
  base_url="https://mirrors.kernel.org/ubuntu/pool/${component}"
  # Loop through all the folders in the universe pool
  for folder in $(curl -s  -L "$base_url" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/'); do
    # Loop through all the subfolders in the current folder
    for subfolder in $(curl -s -L "$base_url/$folder" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/'); do
      # Download all the packages in the current subfolder
      PACKAGES=$(curl -s  -L "$base_url/$folder/$subfolder" | grep -oE '<a href="[^"]+\.deb">[^<]+\.deb</a>' | sed -r 's/<a href="([^"]+\.deb)">[^<]+\.deb<\/a>/\1/')
      PACKAGES=($PACKAGES)

      # Split the list of packages into batches of 10
      for ((i=0; i<${#PACKAGES[@]}; i+=10)); do
        BATCH=("${PACKAGES[@]:$i:10}")

        # Process the batch of packages in the background
        (
          for PACKAGE in "${BATCH[@]}"; do
            PACKAGE_URL="$base_url/$folder/$subfolder/$PACKAGE"
            PACKAGE_FILE="$TEMP_DIR/$PACKAGE"
            wget -q -O "$PACKAGE_FILE" "$PACKAGE_URL"

            PACKAGE_NAME=$(echo "$PACKAGE" | cut -d '_' -f 1)
            PACKAGE_VERSION=$(echo "$PACKAGE" | cut -d '_' -f 2)

            PACKAGE_DIR="$TEMP_DIR/$PACKAGE_NAME-$PACKAGE_VERSION"
            mkdir -p "$PACKAGE_DIR"

            dpkg-deb -x "$PACKAGE_FILE" "$PACKAGE_DIR"

            # Calculate the SHA-256 sum of the package file
            PACKAGE_SHA256SUM=$(sha256sum "$PACKAGE_FILE" | cut -d ' ' -f 1)

            # Save the package metadata
            echo "$PACKAGE_NAME,$PACKAGE_VERSION,$PACKAGE_SHA256SUM,$PACKAGE_URL" >> "$OUTPUT_DIR/packages.csv"

            # Loop through all the files in the package
            for FILE in $(find "$PACKAGE_DIR" -type f); do
              # Calculate the SHA-256 sum of the file
              FILE_SHA256SUM=$(sha256sum "$FILE" | cut -d ' ' -f 1)

              # Save the file metadata
              echo "$PACKAGE_NAME,$PACKAGE_VERSION,$FILE_SHA256SUM,$FILE,$PACKAGE_URL" >> "$OUTPUT_DIR/files.csv"
            done

            rm "$PACKAGE_FILE"
            rm -rf "$PACKAGE_DIR"
          done
        ) &
      done
      wait
    done
  done
done

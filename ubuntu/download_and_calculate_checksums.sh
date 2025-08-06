#!/bin/bash

# Default configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/../output/ubuntu"
TEMP_DIR="${SCRIPT_DIR}/../temp/ubuntu"
UBUNTU_RELEASES=("jammy" "jammy-updates" "noble" "noble-updates")
UBUNTU_COMPONENTS=("main" "restricted" "universe" "multiverse")
ARCHITECTURES=("amd64" "arm64")
GENERATE_CSV=true


# Create the output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Loop through all the components
for component in "${UBUNTU_COMPONENTS[@]}"; do
    # Set the base URL
    base_url="http://mirrors.kernel.org/ubuntu/pool/${component}"
    for folder in $(curl -s "$base_url" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/'); do
    # Loop through all the subfolders in the current folder
        for subfolder in $(curl -s "$base_url/$folder" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/'); do
            # Download all the packages in the current subfolder
            for package in $(curl -s "$base_url/$folder/$subfolder" | grep -oE '<a href="[^"]+\.deb">[^<]+\.deb</a>' | sed -r 's/<a href="([^"]+\.deb)">[^<]+\.deb<\/a>/\1/'); do
                # Download the package
                package_url="$base_url/$folder/$subfolder/$package"
                package_file="$OUTPUT_DIR/$package"
                wget -q -O "$package_file" "$package_url"
            done
        done
    done
done



# Loop through all the releases
# for release in "${UBUNTU_RELEASES[@]}"; do
#   # Loop through all the architectures
#   for arch in "${ARCHITECTURES[@]}"; do
#     # Set the base URL
#     if [[ "$arch" == "arm64" ]]; then
#       base_url="http://ports.ubuntu.com/ubuntu-ports"
#     else
#       base_url="http://mirrors.kernel.org/ubuntu/pool/"
#     fi
#     http://mirrors.kernel.org/ubuntu/pool/universe/z/zeroinstall-injector/0install_2.16-2_amd64.deb
#     https://mirrors.edge.kernel.org/ubuntu/pool/main/liba/libaal/libaal-dev_1.0.5-6_amd64.deb

#     # Loop through all the components
#     for component in "${UBUNTU_COMPONENTS[@]}"; do
#       # Download the package index
#       package_index_url="${base_url}/${component}/ /Packages.gz"
#       package_index_file="${TEMP_DIR}/Packages_${release}_${component}_${arch}.gz"
#       if [ ! -f "$package_index_file" ]; then
#         wget -q -O "$package_index_file" "$package_index_url"
#       fi

#       # Extract the package index
#       gunzip -c "$package_index_file" > "${package_index_file%.gz}"

#       # Loop through all the packages in the package index
#       while IFS= read -r line; do
#         # Extract the package name and version
#         if [[ "$line" =~ ^Package: ]]; then
#           package_name=$(echo "$line" | cut -d ' ' -f 2)
#         elif [[ "$line" =~ ^Version: ]]; then
#           package_version=$(echo "$line" | cut -d ' ' -f 2)
#         elif [[ "$line" =~ ^Filename: ]]; then
#           package_filename=$(echo "$line" | cut -d ' ' -f 2)
#           package_url="${base_url}/${package_filename}"
#           package_file="${TEMP_DIR}/${package_filename}"
#           if [ ! -f "$package_file" ]; then
#             wget -q -O "$package_file" "$package_url"
#           fi

#           # Extract the package
#           dpkg-deb -x "$package_file" "${TEMP_DIR}/${package_name}_${package_version}_${arch}"

#           # Calculate the SHA-256 sum of the files in the package
#           while IFS= read -r file; do
#             sha256sum=$(sha256sum "$file" | cut -d ' ' -f 1)
#             echo "$package_name $package_version $sha256sum"
#           done < <(find "${TEMP_DIR}/${package_name}_${package_version}_${arch}" -type f)

#           # Store the metadata
#           echo "$package_name,$package_version,$sha256sum,$component,$arch,$package_url" >> "${OUTPUT_DIR}/ubuntu/metadata.csv"
#         fi
#       done < "${package_index_file%.gz}"
#     done
#   done
# done

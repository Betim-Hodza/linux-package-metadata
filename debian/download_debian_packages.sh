#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/../output/debian"
TEMP_DIR="${SCRIPT_DIR}/../temp/debian"

mkdir -p "$OUTPUT_DIR" "$TEMP_DIR"

DEBIAN_RELEASES=("bullseye" "bookworm" "trixie" "sid")
DEBIAN_COMPONENTS=("main" "contrib" "non-free" "non-free-firmware")
ARCHITECTURES=("amd64" "arm64")

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

download_packages_file() {
    local release="$1"
    local component="$2"
    local arch="$3"
    
    local url="http://deb.debian.org/debian/dists/${release}/${component}/binary-${arch}/Packages.gz"
    local output_file="${TEMP_DIR}/Packages_${release}_${component}_${arch}.gz"
    
    log "Downloading: $url"
    
    if curl -f -L -o "$output_file" "$url"; then
        log "Successfully downloaded: $output_file"
        
        local uncompressed="${output_file%.gz}"
        if gunzip -c "$output_file" > "$uncompressed"; then
            log "Decompressed: $uncompressed"
            rm "$output_file"
            return 0
        else
            log "Failed to decompress: $output_file"
            return 1
        fi
    else
        log "Failed to download: $url (trying alternate mirror)"
        
        local alt_url="http://ftp.debian.org/debian/dists/${release}/${component}/binary-${arch}/Packages.gz"
        if curl -f -L -o "$output_file" "$alt_url"; then
            log "Successfully downloaded from alternate mirror: $output_file"
            
            local uncompressed="${output_file%.gz}"
            if gunzip -c "$output_file" > "$uncompressed"; then
                log "Decompressed: $uncompressed"
                rm "$output_file"
                return 0
            else
                log "Failed to decompress: $output_file"
                return 1
            fi
        else
            log "Failed to download from both mirrors: $release/$component/$arch"
            return 1
        fi
    fi
}

download_release_file() {
    local release="$1"
    local url="http://deb.debian.org/debian/dists/${release}/Release"
    local output_file="${TEMP_DIR}/Release_${release}"
    
    log "Downloading Release file: $url"
    
    if curl -f -L -o "$output_file" "$url"; then
        log "Successfully downloaded Release file: $output_file"
        return 0
    else
        log "Failed to download Release file: $url"
        return 1
    fi
}

main() {
    log "Starting Debian package download"
    
    for release in "${DEBIAN_RELEASES[@]}"; do
        log "Processing Debian $release"
        
        download_release_file "$release" || continue
        
        for component in "${DEBIAN_COMPONENTS[@]}"; do
            # Skip non-free-firmware for older releases
            if [[ "$component" == "non-free-firmware" && "$release" != "bookworm" && "$release" != "trixie" && "$release" != "sid" ]]; then
                continue
            fi
            
            for arch in "${ARCHITECTURES[@]}"; do
                (
                    download_packages_file "$release" "$component" "$arch"
                ) &
                
                if (( $(jobs -r | wc -l) >= 8 )); then
                    wait
                fi
            done
        done
    done
    
    wait
    
    log "Debian package download completed"
    log "Files downloaded to: $TEMP_DIR"
    
    # Generate CSV files for each release
    for release in "${DEBIAN_RELEASES[@]}"; do
        log "Generating CSV for Debian $release"
        python3 "${SCRIPT_DIR}/parse_debian_packages.py" --release "$release" || log "Failed to generate CSV for Debian $release"
    done
    
    log "CSV generation completed"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
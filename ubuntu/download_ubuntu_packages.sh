#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/../output/ubuntu"
TEMP_DIR="${SCRIPT_DIR}/../temp/ubuntu"

mkdir -p "$OUTPUT_DIR" "$TEMP_DIR"

UBUNTU_RELEASES=("jammy" "mantic" "noble")
UBUNTU_COMPONENTS=("main" "restricted" "universe" "multiverse")
ARCHITECTURES=("amd64" "arm64")

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

download_packages_file() {
    local release="$1"
    local component="$2"
    local arch="$3"
    
    local base_url
    if [[ "$arch" == "arm64" ]]; then
        base_url="http://ports.ubuntu.com/ubuntu-ports"
    else
        base_url="http://archive.ubuntu.com/ubuntu"
    fi
    
    local url="${base_url}/dists/${release}/${component}/binary-${arch}/Packages.gz"
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
        log "Failed to download: $url"
        return 1
    fi
}

download_release_file() {
    local release="$1"
    local url="http://archive.ubuntu.com/ubuntu/dists/${release}/Release"
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
    log "Starting Ubuntu package download"
    
    for release in "${UBUNTU_RELEASES[@]}"; do
        log "Processing Ubuntu $release"
        
        download_release_file "$release" || continue
        
        for component in "${UBUNTU_COMPONENTS[@]}"; do
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
    
    log "Ubuntu package download completed"
    log "Files downloaded to: $TEMP_DIR"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
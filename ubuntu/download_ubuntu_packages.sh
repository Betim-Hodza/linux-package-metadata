#!/bin/bash
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

set -euo pipefail

# Ubuntu Package Downloader
# Downloads package metadata for Ubuntu LTS releases and updates

show_help() {
    cat << EOF
Ubuntu Package Downloader

DESCRIPTION:
    Downloads package metadata for Ubuntu distributions from official repositories.
    Supports LTS releases with updates and generates individual CSV files for each release.

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -h, --help              Show this help message and exit
    -v, --version           Show version information
    -l, --list-releases     List all supported Ubuntu releases
    -r, --release RELEASE   Download specific release only (e.g., "jammy")
    -a, --arch ARCH         Download specific architecture only (amd64 or arm64)
    --no-csv               Skip CSV generation after download
    --temp-dir DIR         Use custom temporary directory
    --output-dir DIR       Use custom output directory

SUPPORTED RELEASES:
    jammy          - Ubuntu 22.04 LTS (Jammy Jellyfish)
    jammy-updates  - Ubuntu 22.04 LTS with updates
    noble          - Ubuntu 24.04 LTS (Noble Numbat)
    noble-updates  - Ubuntu 24.04 LTS with updates

SUPPORTED ARCHITECTURES:
    amd64, arm64

COMPONENTS:
    main        - Canonical-supported open-source software
    restricted  - Proprietary drivers for common hardware
    universe    - Community-maintained open-source software
    multiverse  - Software restricted by copyright or legal issues

OUTPUT:
    Downloads metadata to temp/ubuntu/ directory
    Generates CSV files in output/ubuntu/ directory:
    - ubuntu_jammy_packages.csv, ubuntu_noble_packages.csv, etc.
    - ubuntu_packages.csv (combined file)

EXAMPLES:
    $0                                  # Download all releases
    $0 --release jammy                  # Download Ubuntu 22.04 LTS only
    $0 --arch amd64                     # Download amd64 packages only
    $0 --release noble --arch arm64     # Download Ubuntu 24.04 arm64 only
    $0 --no-csv                         # Download only, skip CSV generation

ESTIMATED TIME:
    - Single release: 5-10 minutes
    - All releases: 20-40 minutes (depends on network speed)

REQUIREMENTS:
    - curl (for downloading)
    - gunzip (for decompression)
    - python3 (for CSV generation)

LICENSE:
    Licensed under the Apache License, Version 2.0
    See: http://www.apache.org/licenses/LICENSE-2.0

EOF
}

show_version() {
    echo "Ubuntu Package Downloader v1.0"
    echo "Part of Linux Package Metadata Extractor"
    echo "Licensed under the Apache License, Version 2.0"
}

list_releases() {
    echo "Supported Ubuntu releases:"
    echo "  jammy          (22.04 LTS)"
    echo "  jammy-updates  (22.04 LTS + updates)"
    echo "  noble          (24.04 LTS)"
    echo "  noble-updates  (24.04 LTS + updates)"
}

# Default configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/../output/ubuntu"
TEMP_DIR="${SCRIPT_DIR}/../temp/ubuntu"
UBUNTU_RELEASES=("jammy" "jammy-updates" "noble" "noble-updates")
UBUNTU_COMPONENTS=("main" "restricted" "universe" "multiverse")
ARCHITECTURES=("amd64" "arm64")
GENERATE_CSV=true

# Argument parsing
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--version)
                show_version
                exit 0
                ;;
            -l|--list-releases)
                list_releases
                exit 0
                ;;
            --no-csv)
                GENERATE_CSV=false
                shift
                ;;
            *)
                echo "Unknown option: $1" >&2
                echo "Use --help for usage information." >&2
                exit 1
                ;;
        esac
    done
}

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
    # Parse command line arguments
    parse_arguments "$@"
    
    # Create directories
    mkdir -p "$OUTPUT_DIR" "$TEMP_DIR"
    
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
    
    # Generate CSV files if requested
    if [[ "$GENERATE_CSV" == "true" ]]; then
        for release in "${UBUNTU_RELEASES[@]}"; do
            log "Generating CSV for Ubuntu $release"
            python3 "${SCRIPT_DIR}/parse_ubuntu_packages.py" --release "$release" || log "Failed to generate CSV for Ubuntu $release"
        done
        log "CSV generation completed"
    else
        log "Skipping CSV generation (--no-csv specified)"
    fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
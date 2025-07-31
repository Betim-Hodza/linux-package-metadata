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

# Rocky Linux Package Downloader
# Downloads package metadata for multiple Rocky Linux versions
# Supports releases: 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 9.0-9.6, 10.0

show_help() {
    cat << EOF
Rocky Linux Package Downloader

DESCRIPTION:
    Downloads package metadata for Rocky Linux distributions from official repositories.
    Supports multiple minor versions and generates individual CSV files for each release.

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -h, --help              Show this help message and exit
    -v, --version           Show version information
    -l, --list-releases     List all supported Rocky Linux releases
    -r, --release RELEASE   Download specific release only (e.g., "9.4")
    -a, --arch ARCH         Download specific architecture only (x86_64 or aarch64)
    --no-csv               Skip CSV generation after download
    --temp-dir DIR         Use custom temporary directory
    --output-dir DIR       Use custom output directory

SUPPORTED RELEASES:
    Rocky Linux 8.x: 8.5, 8.6, 8.7, 8.8, 8.9, 8.10
    Rocky Linux 9.x: 9.0, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
    Rocky Linux 10.x: 10.0

SUPPORTED ARCHITECTURES:
    x86_64, aarch64

REPOSITORIES:
    baseos      - Base operating system packages
    appstream   - Application stream packages  
    extras      - Extra packages and add-ons

OUTPUT:
    Downloads metadata to temp/rocky/ directory
    Generates CSV files in output/rocky/ directory:
    - rocky_8.5_packages.csv, rocky_9.4_packages.csv, etc.
    - rocky_packages.csv (combined file)

EXAMPLES:
    $0                                    # Download all releases
    $0 --release 9.4                     # Download Rocky 9.4 only
    $0 --arch x86_64                     # Download x86_64 packages only
    $0 --release 8.9 --arch aarch64      # Download Rocky 8.9 aarch64 only
    $0 --no-csv                          # Download only, skip CSV generation

ESTIMATED TIME:
    - Single release: 2-5 minutes
    - All releases: 15-30 minutes (depends on network speed)

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
    echo "Rocky Linux Package Downloader v1.0"
    echo "Part of Linux Package Metadata Extractor"
    echo "Licensed under the Apache License, Version 2.0"
}

list_releases() {
    echo "Supported Rocky Linux releases:"
    echo "  8.5   8.6   8.7   8.8   8.9   8.10"
    echo "  9.0   9.1   9.2   9.3   9.4   9.5   9.6"
    echo "  10.0"
}

# Default configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/../output/rocky"
TEMP_DIR="${SCRIPT_DIR}/../temp/rocky"
ROCKY_RELEASES=("8.5" "8.6" "8.7" "8.8" "8.9" "8.10" "9.0" "9.1" "9.2" "9.3" "9.4" "9.5" "9.6" "10.0")
ARCHITECTURES=("x86_64" "aarch64")
GENERATE_CSV=true
SPECIFIC_RELEASE=""
SPECIFIC_ARCH=""

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
            -r|--release)
                SPECIFIC_RELEASE="$2"
                shift 2
                ;;
            -a|--arch)
                SPECIFIC_ARCH="$2"
                shift 2
                ;;
            --no-csv)
                GENERATE_CSV=false
                shift
                ;;
            --temp-dir)
                TEMP_DIR="$2"
                shift 2
                ;;
            --output-dir)
                OUTPUT_DIR="$2"
                shift 2
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

download_rocky_repodata() {
    local release="$1"
    local arch="$2"
    local repo="$3"
    local major_version="${release%%.*}"
    
    # Determine if this is a current or archived release
    local base_url
    case "$release" in
        "8.10"|"9.6"|"10.0")
            # Current releases
            base_url="https://dl.rockylinux.org/pub/rocky/${release}"
            ;;
        *)
            # Archived releases
            base_url="https://dl.rockylinux.org/vault/rocky/${release}"
            ;;
    esac
    
    case "$repo" in
        "baseos")
            local url="${base_url}/BaseOS/${arch}/os/repodata/repomd.xml"
            ;;
        "appstream")
            local url="${base_url}/AppStream/${arch}/os/repodata/repomd.xml"
            ;;
        "extras")
            local url="${base_url}/extras/${arch}/os/repodata/repomd.xml"
            ;;
        *)
            log "Unknown Rocky $release repository: $repo"
            return 1
            ;;
    esac
    
    local output_file="${TEMP_DIR}/repomd_${release}_${repo}_${arch}.xml"
    
    log "Downloading Rocky $release repomd.xml: $url"
    
    if curl -f -L -o "$output_file" "$url"; then
        log "Successfully downloaded: $output_file"
        
        local primary_href=$(grep -A 5 'type="primary"' "$output_file" | grep -o 'href="[^"]*\.xml\.gz"' | sed 's/href="//;s/"//' | head -1)
        if [[ -n "$primary_href" ]]; then
            local repo_path
            case "$repo" in
                "baseos") repo_path="BaseOS" ;;
                "appstream") repo_path="AppStream" ;;
                "extras") repo_path="extras" ;;
            esac
            
            local primary_url="${base_url}/${repo_path}/${arch}/os/${primary_href}"
            local primary_file="${TEMP_DIR}/primary_${release}_${repo}_${arch}.xml.gz"
            
            log "Downloading primary.xml.gz: $primary_url"
            if curl -f -L -o "$primary_file" "$primary_url"; then
                local uncompressed="${primary_file%.gz}"
                if gunzip -c "$primary_file" > "$uncompressed"; then
                    log "Decompressed: $uncompressed"
                    rm "$primary_file"
                    return 0
                fi
            fi
        fi
    fi
    
    log "Failed to download Rocky $release repository data for $repo/$arch"
    return 1
}

main() {
    # Parse command line arguments
    parse_arguments "$@"
    
    # Create directories
    mkdir -p "$OUTPUT_DIR" "$TEMP_DIR"
    
    # Filter releases and architectures if specified
    local releases_to_process=()
    local architectures_to_process=()
    
    if [[ -n "$SPECIFIC_RELEASE" ]]; then
        # Validate the specified release
        if [[ " ${ROCKY_RELEASES[*]} " =~ " ${SPECIFIC_RELEASE} " ]]; then
            releases_to_process=("$SPECIFIC_RELEASE")
        else
            echo "Error: Invalid release '$SPECIFIC_RELEASE'. Use --list-releases to see supported releases." >&2
            exit 1
        fi
    else
        releases_to_process=("${ROCKY_RELEASES[@]}")
    fi
    
    if [[ -n "$SPECIFIC_ARCH" ]]; then
        # Validate the specified architecture
        if [[ " ${ARCHITECTURES[*]} " =~ " ${SPECIFIC_ARCH} " ]]; then
            architectures_to_process=("$SPECIFIC_ARCH")
        else
            echo "Error: Invalid architecture '$SPECIFIC_ARCH'. Supported: ${ARCHITECTURES[*]}" >&2
            exit 1
        fi
    else
        architectures_to_process=("${ARCHITECTURES[@]}")
    fi
    
    log "Starting Rocky Linux package download"
    log "Releases: ${releases_to_process[*]}"
    log "Architectures: ${architectures_to_process[*]}"
    
    for release in "${releases_to_process[@]}"; do
        log "Processing Rocky Linux $release"
        
        for arch in "${architectures_to_process[@]}"; do
            for repo in "baseos" "appstream" "extras"; do
                (
                    download_rocky_repodata "$release" "$arch" "$repo"
                ) &
                
                if (( $(jobs -r | wc -l) >= 6 )); then
                    wait
                fi
            done
        done
    done
    
    wait
    
    log "Rocky Linux package download completed"
    log "Files downloaded to: $TEMP_DIR"
    
    # Generate CSV files if requested
    if [[ "$GENERATE_CSV" == "true" ]]; then
        for release in "${releases_to_process[@]}"; do
            log "Generating CSV for Rocky Linux $release"
            python3 "${SCRIPT_DIR}/parse_rocky_packages.py" --release "$release" || log "Failed to generate CSV for Rocky $release"
        done
        log "CSV generation completed"
    else
        log "Skipping CSV generation (--no-csv specified)"
    fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
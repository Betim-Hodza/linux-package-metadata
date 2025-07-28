#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/../output/rocky"
TEMP_DIR="${SCRIPT_DIR}/../temp/rocky"

mkdir -p "$OUTPUT_DIR" "$TEMP_DIR"

ROCKY_RELEASES=("8" "9" "10")
ARCHITECTURES=("x86_64" "aarch64")

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

download_rocky_repodata() {
    local release="$1"
    local arch="$2"
    local repo="$3"
    local base_url="https://dl.rockylinux.org/pub/rocky/${release}"
    
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
        
        local primary_href=$(grep -o 'href="[^"]*primary[^"]*\.xml\.gz"' "$output_file" | sed 's/href="//;s/"//' | head -1)
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
    log "Starting Rocky Linux package download"
    
    for release in "${ROCKY_RELEASES[@]}"; do
        log "Processing Rocky Linux $release"
        
        for arch in "${ARCHITECTURES[@]}"; do
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
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
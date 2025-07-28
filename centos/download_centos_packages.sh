#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/../output/centos"
TEMP_DIR="${SCRIPT_DIR}/../temp/centos"

mkdir -p "$OUTPUT_DIR" "$TEMP_DIR"

CENTOS_RELEASES=("7" "8" "9")
ARCHITECTURES=("x86_64" "aarch64")

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

download_centos7_repodata() {
    local arch="$1"
    local repo="$2"
    local base_url="http://vault.centos.org/7.9.2009"
    
    case "$repo" in
        "os")
            local url="${base_url}/os/${arch}/repodata/repomd.xml"
            ;;
        "updates")
            local url="${base_url}/updates/${arch}/repodata/repomd.xml"
            ;;
        "extras")
            local url="${base_url}/extras/${arch}/repodata/repomd.xml"
            ;;
        *)
            log "Unknown CentOS 7 repository: $repo"
            return 1
            ;;
    esac
    
    local output_file="${TEMP_DIR}/repomd_7_${repo}_${arch}.xml"
    
    log "Downloading CentOS 7 repomd.xml: $url"
    
    if curl -f -L -o "$output_file" "$url"; then
        log "Successfully downloaded: $output_file"
        
        local primary_href=$(grep -o 'href="[^"]*primary[^"]*\.xml\.gz"' "$output_file" | sed 's/href="//;s/"//' | head -1)
        if [[ -n "$primary_href" ]]; then
            local primary_url="${base_url}/${repo}/${arch}/${primary_href}"
            local primary_file="${TEMP_DIR}/primary_7_${repo}_${arch}.xml.gz"
            
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
    
    log "Failed to download CentOS 7 repository data for $repo/$arch"
    return 1
}

download_centos89_repodata() {
    local release="$1"
    local arch="$2"
    local repo="$3"
    local base_url
    
    if [[ "$release" == "8" ]]; then
        base_url="http://vault.centos.org/8.5.2111"
    else
        base_url="http://mirror.stream.centos.org/9-stream"
    fi
    
    case "$repo" in
        "baseos")
            local url="${base_url}/BaseOS/${arch}/os/repodata/repomd.xml"
            ;;
        "appstream")
            local url="${base_url}/AppStream/${arch}/os/repodata/repomd.xml"
            ;;
        "extras")
            if [[ "$release" == "8" ]]; then
                local url="${base_url}/extras/${arch}/os/repodata/repomd.xml"
            else
                local url="${base_url}/extras-common/repodata/repomd.xml"
            fi
            ;;
        *)
            log "Unknown CentOS $release repository: $repo"
            return 1
            ;;
    esac
    
    local output_file="${TEMP_DIR}/repomd_${release}_${repo}_${arch}.xml"
    
    log "Downloading CentOS $release repomd.xml: $url"
    
    if curl -f -L -o "$output_file" "$url"; then
        log "Successfully downloaded: $output_file"
        
        local primary_href=$(grep -o 'href="[^"]*primary[^"]*\.xml\.gz"' "$output_file" | sed 's/href="//;s/"//' | head -1)
        if [[ -n "$primary_href" ]]; then
            local repo_path
            case "$repo" in
                "baseos") repo_path="BaseOS" ;;
                "appstream") repo_path="AppStream" ;;
                "extras") 
                    if [[ "$release" == "8" ]]; then
                        repo_path="extras"
                    else
                        repo_path="extras-common"
                    fi
                    ;;
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
    
    log "Failed to download CentOS $release repository data for $repo/$arch"
    return 1
}

main() {
    log "Starting CentOS package download"
    
    for release in "${CENTOS_RELEASES[@]}"; do
        log "Processing CentOS $release"
        
        for arch in "${ARCHITECTURES[@]}"; do
            if [[ "$release" == "7" ]]; then
                for repo in "os" "updates" "extras"; do
                    (
                        download_centos7_repodata "$arch" "$repo"
                    ) &
                    
                    if (( $(jobs -r | wc -l) >= 6 )); then
                        wait
                    fi
                done
            else
                for repo in "baseos" "appstream" "extras"; do
                    (
                        download_centos89_repodata "$release" "$arch" "$repo"
                    ) &
                    
                    if (( $(jobs -r | wc -l) >= 6 )); then
                        wait
                    fi
                done
            fi
        done
    done
    
    wait
    
    log "CentOS package download completed"
    log "Files downloaded to: $TEMP_DIR"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
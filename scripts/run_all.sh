#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}/.."
OUTPUT_DIR="${ROOT_DIR}/output"
TEMP_DIR="${ROOT_DIR}/temp"
FINAL_OUTPUT_DIR="${ROOT_DIR}/final_output"

mkdir -p "$OUTPUT_DIR" "$TEMP_DIR" "$FINAL_OUTPUT_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

run_distro() {
    local distro="$1"
    local has_download="$2"
    
    log "Starting $distro package extraction"
    
    if [[ "$has_download" == "true" ]]; then
        if [[ -x "${ROOT_DIR}/${distro}/download_${distro}_packages.sh" ]]; then
            log "Running $distro download script"
            if ! "${ROOT_DIR}/${distro}/download_${distro}_packages.sh"; then
                log "ERROR: $distro download failed"
                return 1
            fi
        else
            log "WARNING: $distro download script not found or not executable"
        fi
    fi
    
    if [[ -x "${ROOT_DIR}/${distro}/parse_${distro}_packages.py" ]]; then
        log "Running $distro parser"
        if ! python3 "${ROOT_DIR}/${distro}/parse_${distro}_packages.py"; then
            log "ERROR: $distro parser failed"
            return 1
        fi
    else
        log "ERROR: $distro parser not found or not executable"
        return 1
    fi
    
    log "Completed $distro package extraction"
    return 0
}

run_all_distros() {
    local pids=()
    local results=()
    
    # Distributions with download scripts
    for distro in ubuntu debian centos rocky; do
        (
            if run_distro "$distro" "true"; then
                echo "SUCCESS:$distro" > "/tmp/result_$distro"
            else
                echo "FAILED:$distro" > "/tmp/result_$distro"
            fi
        ) &
        pids+=("$!")
    done
    
    # Distributions with only parser scripts (direct download)
    for distro in fedora alpine arch amazonlinux; do
        (
            if run_distro "$distro" "false"; then
                echo "SUCCESS:$distro" > "/tmp/result_$distro"
            else
                echo "FAILED:$distro" > "/tmp/result_$distro"
            fi
        ) &
        pids+=("$!")
    done
    
    # Wait for all background processes
    for pid in "${pids[@]}"; do
        wait "$pid"
    done
    
    # Collect results
    local failed_distros=()
    for distro in ubuntu debian centos rocky fedora alpine arch amazonlinux; do
        if [[ -f "/tmp/result_$distro" ]]; then
            result=$(cat "/tmp/result_$distro")
            if [[ "$result" == "FAILED:$distro" ]]; then
                failed_distros+=("$distro")
            fi
            rm -f "/tmp/result_$distro"
        else
            failed_distros+=("$distro")
        fi
    done
    
    if [[ ${#failed_distros[@]} -gt 0 ]]; then
        log "FAILED distributions: ${failed_distros[*]}"
        return 1
    else
        log "ALL distributions completed successfully"
        return 0
    fi
}

collate_outputs() {
    log "Collating all CSV outputs"
    
    # Copy individual distribution CSVs
    for output_file in "${OUTPUT_DIR}"/*/*.csv; do
        if [[ -f "$output_file" ]]; then
            filename=$(basename "$output_file")
            cp "$output_file" "${FINAL_OUTPUT_DIR}/${filename}"
            log "Copied $output_file to final output"
        fi
    done
    
    # Create a combined CSV with all packages
    local combined_csv="${FINAL_OUTPUT_DIR}/all_packages.csv"
    local header_written=false
    
    for csv_file in "${FINAL_OUTPUT_DIR}"/*.csv; do
        if [[ -f "$csv_file" && "$(basename "$csv_file")" != "all_packages.csv" ]]; then
            if [[ "$header_written" == "false" ]]; then
                head -1 "$csv_file" > "$combined_csv"
                header_written=true
            fi
            tail -n +2 "$csv_file" >> "$combined_csv"
        fi
    done
    
    if [[ -f "$combined_csv" ]]; then
        local total_packages=$(tail -n +2 "$combined_csv" | wc -l)
        log "Created combined CSV with $total_packages total packages: $combined_csv"
    fi
}

cleanup_temp() {
    if [[ -d "$TEMP_DIR" ]]; then
        log "Cleaning up temporary files"
        rm -rf "$TEMP_DIR"
    fi
}

generate_summary() {
    local summary_file="${FINAL_OUTPUT_DIR}/extraction_summary.txt"
    
    {
        echo "Linux Package Metadata Extraction Summary"
        echo "==========================================="
        echo "Generated on: $(date)"
        echo ""
        echo "Distribution CSV Files:"
        
        for csv_file in "${FINAL_OUTPUT_DIR}"/*.csv; do
            if [[ -f "$csv_file" ]]; then
                filename=$(basename "$csv_file")
                if [[ "$filename" != "all_packages.csv" ]]; then
                    package_count=$(tail -n +2 "$csv_file" | wc -l 2>/dev/null || echo "0")
                    echo "- $filename: $package_count packages"
                fi
            fi
        done
        
        echo ""
        if [[ -f "${FINAL_OUTPUT_DIR}/all_packages.csv" ]]; then
            total_packages=$(tail -n +2 "${FINAL_OUTPUT_DIR}/all_packages.csv" | wc -l 2>/dev/null || echo "0")
            echo "Total packages across all distributions: $total_packages"
        fi
        
        echo ""
        echo "CSV Format:"
        echo "package,version,sha256,sha512,component,architecture,deb_url,license,purl,release"
        
    } > "$summary_file"
    
    log "Generated summary: $summary_file"
}

main() {
    log "Starting Linux package metadata extraction"
    log "Root directory: $ROOT_DIR"
    log "Output directory: $FINAL_OUTPUT_DIR"
    
    # Check Python dependencies
    if ! python3 -c "import requests, xml.etree.ElementTree" 2>/dev/null; then
        log "ERROR: Missing Python dependencies. Please install requirements: pip3 install -r requirements.txt"
        exit 1
    fi
    
    # Run all distributions in parallel
    if ! run_all_distros; then
        log "ERROR: Some distributions failed. Check logs above."
        exit 1
    fi
    
    # Collate outputs
    collate_outputs
    
    # Generate summary
    generate_summary
    
    # Optional cleanup
    if [[ "${CLEANUP_TEMP:-true}" == "true" ]]; then
        cleanup_temp
    fi
    
    log "Linux package metadata extraction completed successfully"
    log "Final outputs available in: $FINAL_OUTPUT_DIR"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
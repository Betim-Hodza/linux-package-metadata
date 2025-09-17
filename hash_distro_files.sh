#!/usr/bin/env bash

#  Safety flags
set -euo pipefail               # abort on error, treat unset vars as errors
IFS=$'\n\t'                     # sane field separator for loops

#  GLOBAL CONSTANTS
XARGS_PROCESSES=10                     # how many parallel workers
UBUNTU_COMPONENTS=("main" "restricted" "universe" "multiverse")
DEBIAN_COMPONENTS=("main" "non-free")
CENTOS_VERSIONS=("9-stream" "10-stream")
ROCKY_VERSIONS=("8.5" "8.6" "8.7" "8.8" "8.9" "8.10" "9.0" "9.1" "9.2" "9.3" "9.4" "9.5" "9.6" "10.0")
FEDORA_TYPE=("archive")
FEDORA_VERSIONS=("38" "39" "40" "41" "42")
ALPINE_VERSIONS=("v3.18" "v3.19" "v3.2" "v3.20" "v3.21" "v3.22" "latest-stable" "edge")
ALPINE_COMPONENTS=("main" "release" "community")
TEMP_DIR="temp"
OUTPUT_DIR="output"
DISTRO="NULL"

# Network and retry settings
MAX_RETRIES=3
TIMEOUT=30
RETRY_DELAY=5

#  Logging helper (time‑stamped)
log() {
  printf '[%(%Y-%m-%d %H:%M:%S)T] %s\n' -1 "$*" >&2
}
export -f log

#  Resolve script root (absolute paths)
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# These will be overwritten later per‑distro
TEMP_DIR="${SCRIPT_ROOT}/${TEMP_DIR}"
OUTPUT_DIR="${SCRIPT_ROOT}/${OUTPUT_DIR}"
export OUTPUT_DIR TEMP_DIR MAX_RETRIES TIMEOUT RETRY_DELAY

#  Helper – open lock files (called after we know the distro)
open_locks() {
  # make sure the directories exist before we try to open files inside them
  mkdir -p "$TEMP_DIR" "$OUTPUT_DIR"

  # 200 – packages.csv   (write‑only, shared by all workers)
  exec 200>>"${OUTPUT_DIR}/packages.csv"

  # 201 – files.csv      (write‑only, shared by all workers)
  exec 201>>"${OUTPUT_DIR}/files.csv"

  # 202 – subfolders list (read‑only for the discovery phase)
  exec 202>>"${TEMP_DIR}/subfolders.txt"

  # 203 – urls.csv (append‑only, used by add_url)
  exec 203>>"${OUTPUT_DIR}/urls.csv"

  # 204 – urls.csv (read/write, used by set_state)
  exec 204>>"${OUTPUT_DIR}/urls.csv"
}
export -f open_locks

#  Functions

#  add_url – append a new URL with state = -1 (not‑started)
add_url() {
  local url=$1
  flock -x 203 -c "printf '%s,-1\n' \"$url\" >> \"${OUTPUT_DIR}/urls.csv\""
}
export -f add_url

#  set_state – update the state column for a given URL
#  (uses an in‑place sed, far faster than rewriting the whole file)
set_state() {
  local url=$1 new_state=$2
  flock -x 204 sed -i -E "s|^(${url}),.*$|\\1,${new_state}|" "${OUTPUT_DIR}/urls.csv"
}
export -f set_state

# Robust curl function with retries and timeouts
curl_robust() {
  local url=$1
  local retries=0
  
  while [ $retries -lt $MAX_RETRIES ]; do
    if curl -s -L --connect-timeout $TIMEOUT --max-time $((TIMEOUT * 2)) --retry 2 --retry-delay $RETRY_DELAY "$url"; then
      return 0
    fi
    retries=$((retries + 1))
    if [ $retries -lt $MAX_RETRIES ]; then
      log "Retry $retries/$MAX_RETRIES for URL: $url"
      sleep $RETRY_DELAY
    fi
  done
  log "ERROR: Failed to fetch after $MAX_RETRIES attempts: $url"
  return 1
}
export -f curl_robust

# Robust wget function with retries and timeouts
wget_robust() {
  local url=$1
  local output=$2
  local retries=0
  
  while [ $retries -lt $MAX_RETRIES ]; do
    if wget -q --timeout=$TIMEOUT --tries=1 --connect-timeout=$TIMEOUT -O "$output" "$url"; then
      # Verify the file was actually downloaded and has content
      if [ -s "$output" ]; then
        return 0
      else
        log "WARNING: Downloaded file is empty: $url"
        rm -f "$output"
      fi
    fi
    retries=$((retries + 1))
    if [ $retries -lt $MAX_RETRIES ]; then
      log "Retry $retries/$MAX_RETRIES for download: $url"
      sleep $RETRY_DELAY
    fi
  done
  log "ERROR: Failed to download after $MAX_RETRIES attempts: $url"
  return 1
}
export -f wget_robust

#  get_subfolders – fetch the list of sub‑folders for a "letter" URL
get_subfolders() {
  local base=$1
  local content
  
  if ! content=$(curl_robust "$base"); then
    log "ERROR: Failed to get subfolders from $base"
    return 1
  fi
  
  echo "$content" |
    grep -oE '<a[^>]* href="([^"]+)"' |
    sed -E 's/.*href="([^"]+)".*/\1/' |
    grep -vE '^\.\.?$' |
    while IFS= read -r sf; do
      printf '%s/%s\n' "$base" "$sf"
    done |
    flock -x 202 cat >> "${TEMP_DIR}/subfolders.txt"
}
export -f get_subfolders

#  get_packages – from a sub‑folder URL, extract package file names
get_packages() {
  local subfolder_url=$1
  local pkgs
  local content

  if ! content=$(curl_robust "$subfolder_url"); then
    log "ERROR: Failed to get packages from $subfolder_url"
    return 1
  fi

  case $DISTRO in
    ubuntu|debian)
      pkgs=$(echo "$content" |
            grep -oE '<a[^>]* href="[^"]+\.deb"' |
            sed -E 's/.*href="([^"]+)".*/\1/')
      ;;
    fedora|rocky|centos)
      pkgs=$(echo "$content" |
            grep -oE '<a[^>]* href="[^"]+\.rpm"' |
            sed -E 's/.*href="([^"]+)".*/\1/')
      ;;
    arch)
      pkgs=$(echo "$content" |
            grep -oE '<a[^>]* href="[^"]+\.zst"' |
            sed -E 's/.*href="([^"]+)".*/\1/')
      ;;
    alpine)
      pkgs=$(echo "$content" |
            grep -oE '<a[^>]* href="[^"]+\.apk"' |
            sed -E 's/.*href="([^"]+)".*/\1/')
      ;;
  esac

  if [ -n "$pkgs" ]; then
    while IFS= read -r p; do
      [ -n "$p" ] && add_url "${subfolder_url}/${p}"
    done <<<"$pkgs"
  fi
}
export -f get_packages

# Check if system has required tools
check_dependencies() {
  local missing_tools=()
  
  case $DISTRO in
    ubuntu|debian)
      command -v dpkg-deb >/dev/null || missing_tools+=("dpkg-deb")
      ;;
    fedora|rocky|centos)
      command -v rpm2cpio >/dev/null || missing_tools+=("rpm2cpio")
      command -v cpio >/dev/null || missing_tools+=("cpio")
      command -v rpm >/dev/null || missing_tools+=("rpm")
      ;;
    arch)
      command -v unzstd >/dev/null || missing_tools+=("unzstd")
      ;;
  esac
  
  command -v sha256sum >/dev/null || missing_tools+=("sha256sum")
  command -v wget >/dev/null || missing_tools+=("wget")
  command -v curl >/dev/null || missing_tools+=("curl")
  command -v uuidgen >/dev/null || missing_tools+=("uuidgen")
  
  if [ ${#missing_tools[@]} -gt 0 ]; then
    log "ERROR: Missing required tools: ${missing_tools[*]}"
    exit 1
  fi
}
export -f check_dependencies

#  process_package – download, unpack, hash archive & files
process_package() {
  local PACKAGE_URL=$1

  # -------------------  Check current state -------------------
  local cur_state
  cur_state=$(grep -m1 -F "$PACKAGE_URL" "${OUTPUT_DIR}/urls.csv" 2>/dev/null | cut -d, -f2 || echo -1)
  [[ $cur_state != -1 ]] || return   # already processed / in‑progress

  # -------------------  Mark as "downloading" -----------------
  set_state "$PACKAGE_URL" 0

  # -------------------  Download the package -----------------
  local PACKAGE=$(basename "$PACKAGE_URL")
  local PACKAGE_FILE="${TEMP_DIR}/${PACKAGE}"

  if ! wget_robust "$PACKAGE_URL" "$PACKAGE_FILE"; then
    log "ERROR: download failed – $PACKAGE_URL"
    set_state "$PACKAGE_URL" -1
    return
  fi

  # -------------------  Unpack & extract name / version -------
  local uniq_id PACKAGE_DIR PACKAGE_NAME PACKAGE_VERSION
  uniq_id=$(uuidgen 2>/dev/null || echo "$$-$RANDOM-$(date +%s)")
  PACKAGE_DIR="${TEMP_DIR}/${PACKAGE}-${uniq_id}"
  mkdir -p "$PACKAGE_DIR"

  case $DISTRO in
    ubuntu|debian)
      PACKAGE_NAME=${PACKAGE%%_*}
      PACKAGE_VERSION=$(echo "$PACKAGE" | cut -d '_' -f 2)
      if ! timeout 60 dpkg-deb -x "$PACKAGE_FILE" "$PACKAGE_DIR" 2>/dev/null; then
        log "ERROR: cannot extract $PACKAGE_FILE"
        rm -f "$PACKAGE_FILE"
        rm -rf "$PACKAGE_DIR"
        set_state "$PACKAGE_URL" -1
        return
      fi
      ;;
    fedora|rocky|centos)
      PACKAGE_NAME=$(rpm2cpio "$PACKAGE_FILE" 2>/dev/null | cpio -it 2>/dev/null | head -n1 | cut -d'-' -f1 2>/dev/null || echo "unknown")
      PACKAGE_VERSION=$(rpm -qp --queryformat '%{VERSION}-%{RELEASE}' "$PACKAGE_FILE" 2>/dev/null || echo "unknown")
      if ! timeout 60 bash -c "rpm2cpio '$PACKAGE_FILE' | cpio -idmv -D '$PACKAGE_DIR' 2>/dev/null"; then
        log "ERROR: cannot extract $PACKAGE_FILE"
        rm -f "$PACKAGE_FILE"
        rm -rf "$PACKAGE_DIR"
        set_state "$PACKAGE_URL" -1
        return
      fi
      ;;
    arch)
      PACKAGE_NAME=$(basename "$PACKAGE" .zst | rev | cut -d'-' -f4- | rev)
      PACKAGE_VERSION=$(basename "$PACKAGE" .zst | rev | cut -d'-' -f3-2 | rev)
      if ! timeout 60 tar -I unzstd -xf "$PACKAGE_FILE" -C "$PACKAGE_DIR" 2>/dev/null; then
        log "ERROR: cannot extract $PACKAGE_FILE"
        rm -f "$PACKAGE_FILE"
        rm -rf "$PACKAGE_DIR"
        set_state "$PACKAGE_URL" -1
        return
      fi
      ;;
    alpine)
      PACKAGE_NAME=$(basename "$PACKAGE" .apk | rev | cut -d'-' -f3- | rev)
      PACKAGE_VERSION=$(basename "$PACKAGE" .apk | rev | cut -d'-' -f2-1 | rev)
      if ! timeout 60 tar -xzf "$PACKAGE_FILE" -C "$PACKAGE_DIR" 2>/dev/null; then
        log "ERROR: cannot extract $PACKAGE_FILE"
        rm -f "$PACKAGE_FILE"
        rm -rf "$PACKAGE_DIR"
        set_state "$PACKAGE_URL" -1
        return
      fi
      ;;
  esac

  # -------------------  Compute archive hash -----------------
  local PKG_SHA
  PKG_SHA=$(sha256sum "$PACKAGE_FILE" | cut -d' ' -f1)

  flock -x 200 -c "printf '%s,%s,%s,%s\n' \"$PACKAGE_NAME\" \"$PACKAGE_VERSION\" \"$PKG_SHA\" \"$PACKAGE_URL\" >> \"${OUTPUT_DIR}/packages.csv\""

  # -------------------   Walk every file & record its hash -----
  while IFS= read -r -d '' f; do
    local FILE_SHA REL_PATH
    FILE_SHA=$(sha256sum "$f" 2>/dev/null | cut -d' ' -f1 || echo "error")
    REL_PATH="${f#$PACKAGE_DIR/}"
    flock -x 201 -c "printf '%s,%s,%s,%s,%s\n' \"$PACKAGE_NAME\" \"$PACKAGE_VERSION\" \"$FILE_SHA\" \"$REL_PATH\" \"$PACKAGE_URL\" >> \"${OUTPUT_DIR}/files.csv\""
  done < <(find "$PACKAGE_DIR" -type f -print0 2>/dev/null)

  # -------------------   Mark as completed & clean up ---------
  set_state "$PACKAGE_URL" 1
  rm -f "$PACKAGE_FILE"
  rm -rf "$PACKAGE_DIR"
  
  log "Completed: $PACKAGE_NAME ($PACKAGE_VERSION)"
}
export -f process_package

# Progress monitoring function
show_progress() {
  while true; do
    sleep 30
    if [ -f "${OUTPUT_DIR}/urls.csv" ]; then
      local total=$(( $(wc -l < "${OUTPUT_DIR}/urls.csv") - 1 ))
      local completed=$(awk -F, '$2==1{c++} END{print c}' "${OUTPUT_DIR}/urls.csv" 2>/dev/null || echo "0")
      local in_progress=$(awk -F, '$2==0{c++} END{print c}' "${OUTPUT_DIR}/urls.csv" 2>/dev/null || echo "0")
      local failed=$(awk -F, '$2==-1{c++} END{print c}' "${OUTPUT_DIR}/urls.csv" 2>/dev/null || echo "0")
      
      if [ "$total" -gt 0 ]; then
        local percent=$((completed * 100 / total))
        log "Progress: $completed/$total ($percent%) completed, $in_progress in progress, $failed failed"
      fi
    fi
  done
}

#  MAIN
log "Script started – $(date '+%Y-%m-%d %H:%M:%S')"
log "It is recommended to run this inside tmux or as a background job."

# ------------------- Argument parsing -------------------
DISTRO=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --distro) DISTRO=$2; shift 2 ;;
    --processes) XARGS_PROCESSES=$2; shift 2 ;;
    --timeout) TIMEOUT=$2; shift 2 ;;
    --retries) MAX_RETRIES=$2; shift 2 ;;
    -h|--help)
      echo "Usage: $0 --distro <ubuntu|debian|fedora|rocky|centos|arch|alpine> [OPTIONS]"
      echo "Options:"
      echo "  --processes N    Number of parallel workers (default: $XARGS_PROCESSES)"
      echo "  --timeout N      Timeout in seconds (default: $TIMEOUT)"
      echo "  --retries N      Max retry attempts (default: $MAX_RETRIES)"
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -z $DISTRO ]]; then
  log "Missing --distro argument"
  exit 1
fi

log "Selected distro: $DISTRO"
log "Parallel workers: $XARGS_PROCESSES"
log "Timeout: ${TIMEOUT}s"
log "Max retries: $MAX_RETRIES"

# ------------------- Check dependencies -----------------
check_dependencies

# ------------------- Set per‑distro directories -------------
case $DISTRO in
  ubuntu)  TEMP_DIR="${SCRIPT_ROOT}/ubuntu/temp";   OUTPUT_DIR="${SCRIPT_ROOT}/ubuntu/output" ;;
  debian)  TEMP_DIR="${SCRIPT_ROOT}/debian/temp";   OUTPUT_DIR="${SCRIPT_ROOT}/debian/output" ;;
  fedora)  TEMP_DIR="${SCRIPT_ROOT}/fedora/temp";   OUTPUT_DIR="${SCRIPT_ROOT}/fedora/output" ;;
  rocky)   TEMP_DIR="${SCRIPT_ROOT}/rocky/temp";    OUTPUT_DIR="${SCRIPT_ROOT}/rocky/output" ;;
  centos)  TEMP_DIR="${SCRIPT_ROOT}/centos/temp";   OUTPUT_DIR="${SCRIPT_ROOT}/centos/output" ;;
  arch)    TEMP_DIR="${SCRIPT_ROOT}/arch/temp";     OUTPUT_DIR="${SCRIPT_ROOT}/arch/output" ;;
  alpine)  TEMP_DIR="${SCRIPT_ROOT}/alpine/temp";   OUTPUT_DIR="${SCRIPT_ROOT}/alpine/output" ;;
  *) log "Unsupported distro: $DISTRO"; exit 1 ;;
esac

export DISTRO TEMP_DIR OUTPUT_DIR

#  Open the lock files now that the directories are known
open_locks

#  Ensure CSV headers exist (files are already opened)
[[ -s "${OUTPUT_DIR}/packages.csv" ]] || echo "name,version,sha256,url" > "${OUTPUT_DIR}/packages.csv"
[[ -s "${OUTPUT_DIR}/files.csv"    ]] || echo "name,version,sha256,file,url" > "${OUTPUT_DIR}/files.csv"
[[ -s "${OUTPUT_DIR}/urls.csv"     ]] || echo "url,state" > "${OUTPUT_DIR}/urls.csv"

# Start progress monitoring in background
show_progress &
PROGRESS_PID=$!

# Set up signal handlers for cleanup
cleanup() {
  log "Cleaning up..."
  kill $PROGRESS_PID 2>/dev/null || true
  
  # Close file descriptors
  exec 200>&- 2>/dev/null || true
  exec 201>&- 2>/dev/null || true
  exec 202>&- 2>/dev/null || true
  exec 203>&- 2>/dev/null || true
  exec 204>&- 2>/dev/null || true
  
  log "Script interrupted"
  exit 1
}
trap cleanup INT TERM

# ------------------- URL discovery (or resume) ------------
if [[ -s "${OUTPUT_DIR}/urls.csv" && $(tail -n +2 "${OUTPUT_DIR}/urls.csv" 2>/dev/null | wc -l) -gt 0 ]]; then
  log "Resuming – URLs already discovered"
else
  log "Starting URL discovery..."
  LETTERS_FILE="${TEMP_DIR}/letters.txt"
  : >"$LETTERS_FILE"

  case $DISTRO in
    ubuntu)
      for comp in "${UBUNTU_COMPONENTS[@]}"; do
        base="https://mirrors.kernel.org/ubuntu/pool/${comp}"
        content=$(curl_robust "$base" || continue)
        echo "$content" |
          grep -oE '<a[^>]* href="([^"]+)"' |
          sed -E 's/.*href="([^"]+)".*/\1/' |
          grep -vE '^\.\.?$' |
          while IFS= read -r f; do echo "$base/$f"; done >> "$LETTERS_FILE"
      done
      ;;
    debian)
      for comp in "${DEBIAN_COMPONENTS[@]}"; do
        base="https://mirrors.edge.kernel.org/debian/pool/${comp}"
        content=$(curl_robust "$base" || continue)
        echo "$content" |
          grep -oE '<a[^>]* href="([^"]+)"' |
          sed -E 's/.*href="([^"]+)".*/\1/' |
          grep -vE '^\.\.?$' |
          while IFS= read -r f; do echo "$base/$f"; done >> "$LETTERS_FILE"
      done
      ;;
    fedora)
      for type in "${FEDORA_TYPE[@]}"; do
        for version in "${FEDORA_VERSIONS[@]}"; do
          # skip archive for versions 41+ (as in original script)
          if [[ "$type" == "archive" && "$version" =~ ^(41|42)$ ]]; then continue; fi
          base_url="https://download-ib01.fedoraproject.org/pub/${type}/fedora/linux/releases/${version}/Everything/x86_64/os/Packages/"
          content=$(curl_robust "$base_url" || continue)
          echo "$content" |
            grep -oE '<a[^>]* href="([^"]+)"' |
            sed -E 's/.*href="([^"]+)".*/\1/' |
            grep -vE '^\.\.?$' |
            while IFS= read -r f; do echo "$base_url/$f"; done >> "$LETTERS_FILE"
        done
      done
      ;;
    rocky)
      for version in "${ROCKY_VERSIONS[@]}"; do
        base_url="https://dfw.mirror.rackspace.com/rocky/${version}/AppStream/x86_64/os/Packages/"
        content=$(curl_robust "$base_url" || continue)
        echo "$content" |
          grep -oE '<a[^>]* href="([^"]+)"' |
          sed -E 's/.*href="([^"]+)".*/\1/' |
          grep -vE '^\.\.?$' |
          while IFS= read -r f; do echo "$base_url/$f"; done >> "$LETTERS_FILE"
      done
      ;;
    centos)
      for version in "${CENTOS_VERSIONS[@]}"; do
        echo "https://dfw.mirror.rackspace.com/centos-stream/${version}/AppStream/x86_64/os/Packages" >> "$LETTERS_FILE"
      done
      ;;
    arch)
      echo "https://mirrors.edge.kernel.org/archlinux/pool/packages" >> "$LETTERS_FILE"
      ;;
    alpine)
      for version in "${ALPINE_VERSIONS[@]}"; do
        for component in "${ALPINE_COMPONENTS[@]}"; do
          echo "https://mirrors.edge.kernel.org/alpine/${version}/${component}/x86_64" >> "$LETTERS_FILE"
        done
      done
      ;;
  esac

  # ------------------- Subfolders -------------------------
  log "Discovering subfolders..."
  if [ -s "$LETTERS_FILE" ]; then
    xargs -a "$LETTERS_FILE" -P "$XARGS_PROCESSES" -I {} bash -c 'get_subfolders "{}" || true'
  fi

  # ------------------- Package URLs -----------------------
  log "Discovering package URLs..."
  if [ -s "${TEMP_DIR}/subfolders.txt" ]; then
    xargs -a "${TEMP_DIR}/subfolders.txt" -P "$XARGS_PROCESSES" -I {} bash -c 'get_packages "{}" || true'
  fi

  log "URL discovery finished – $(tail -n +2 "${OUTPUT_DIR}/urls.csv" 2>/dev/null | wc -l || echo 0) URLs recorded"
fi

# ------------------- Process packages in parallel ----------
log "Starting parallel processing of packages (up to $XARGS_PROCESSES workers)"
if [ -s "${OUTPUT_DIR}/urls.csv" ] && [ "$(tail -n +2 "${OUTPUT_DIR}/urls.csv" 2>/dev/null | wc -l)" -gt 0 ]; then
  tail -n +2 "${OUTPUT_DIR}/urls.csv" | cut -d, -f1 |
    xargs -P "$XARGS_PROCESSES" -I {} bash -c 'process_package "{}" || true'
else
  log "No URLs to process"
fi

# Stop progress monitoring
kill $PROGRESS_PID 2>/dev/null || true

# ------------------- Final summary -------------------------
PKGS=$(( $(wc -l < "${OUTPUT_DIR}/packages.csv" 2>/dev/null || echo 1) - 1 ))
FILES=$(( $(wc -l < "${OUTPUT_DIR}/files.csv" 2>/dev/null || echo 1) - 1 ))
DONE=$(awk -F, '$2==1{c++} END{print c}' "${OUTPUT_DIR}/urls.csv" 2>/dev/null || echo 0)
FAILED=$(awk -F, '$2==-1{c++} END{print c}' "${OUTPUT_DIR}/urls.csv" 2>/dev/null || echo 0)
log "Finished – $PKGS packages, $FILES files, $DONE URLs completed, $FAILED failed"

# ------------------- Clean‑up (close descriptors) ----------
exec 200>&- 2>/dev/null || true
exec 201>&- 2>/dev/null || true
exec 202>&- 2>/dev/null || true
exec 203>&- 2>/dev/null || true
exec 204>&- 2>/dev/null || true

#!/usr/bin/env bash

# GLOBALS
XARGS_PROCESSES=10                     # how many parallel workers
UBUNTU_COMPONENTS=("main" "restricted" "universe" "multiverse")
DEBIAN_COMPONENTS=("main" "non-free")
CENTOS_VERSIONS=("9-stream" "10-stream")
FEDORA_TYPE=("archive" )
ROCKY_VERSIONS=("8.5" "8.6" "8.7" "8.8" "8.9" "8.10" "9.0" "9.1" "9.2" "9.3" "9.4" "9.5" "9.6" "10.0")
FEDORA_VERSIONS=("38" "39" "40" "41" "42")
ALPINE_VERSIONS=("v3.18" "v3.19" "v3.2" "v3.20" "v3.21" "v3.22" "latest-stable" "edge")
ALPINE_COMPONENTS=("main" "release" "community")
TEMP_DIR="temp"
OUTPUT_DIR="output"
DISTRO="NULL"

# Time stamped log func
log() 
{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}
export -f log                         # make it visible to child shells

# Resolve absolute paths once (prevents empty‑variable “/urls.csv”)
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMP_DIR="${SCRIPT_ROOT}/${TEMP_DIR}"
OUTPUT_DIR="${SCRIPT_ROOT}/${OUTPUT_DIR}"
# these vars are used in multiple subfunctions
export OUTPUT_DIR TEMP_DIR

# Initializes urls with the specified mirror (ubuntu, debian, fedora, etc.)
add_url() 
{
  local url=$1
  # New URLs are always inserted with state = -1 (not‑started)
  flock -x 203 -c "printf '%s,-1\n' \"$url\" >> \"${OUTPUT_DIR}/urls.csv\""
}
export -f add_url

# updates new state of a url
# we take in our url.csv read it and basically overwrite it later
set_state() {
  local url=$1 new_state=$2
  flock -x 204 bash -c '
    tmp=$(mktemp) || exit 1
    while IFS=, read -r u s; do
      if [[ "$u" == "'"$url"'" ]]; then
        printf "%s,%s\n" "$u" "'"$new_state"'" >> "$tmp"
      else
        printf "%s,%s\n" "$u" "$s" >> "$tmp"
      fi
    done < "'"${OUTPUT_DIR}/urls.csv"'"
    mv "$tmp" "'"${OUTPUT_DIR}/urls.csv"'"
  '
}
export -f set_state


# from the letter urls we obtain subfolders inside it
get_subfolders() 
{
  local letter_url=$1
  local subfolders
  subfolders=$(curl -s -L "$letter_url" |
               grep -oE '<a href="[^"]+">[^<]+</a>' |
               sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/' |
               grep -vE '^\.$|^\.\.$|^\?')
  for sf in $subfolders; do
    echo "$letter_url/$sf"
  done | flock -x 202 -c 'cat >> "'"${TEMP_DIR}/subfolders.txt"'"'
}
export -f get_subfolders

# from the subfolder url we get the actual package url to download later
get_packages() 
{
  local subfolder_url=$1
  local pkgs

  case $DISTRO in
    "ubuntu"|"debian")
        pkgs=$(curl -s -L "$subfolder_url" |
         grep -oE '<a href="[^"]+\.deb">[^<]+\.deb</a>' |
         sed -r 's/<a href="([^"]+\.deb)">[^<]+<\/a>/\1/')
        for p in $pkgs; do
          add_url "$subfolder_url/$p"
        done
      ;;
    "fedora")
      ;;
    "rocky")
      ;;
    "centos")
      pkgs=$(curl -s -L "$subfolder_url" | 
            grep -oE '<a href="[^"]+\.rpm">[^<]+\.rpm</a>' | 
            sed -r 's/<a href="([^"]+\.rpm)">[^<]+\.rpm<\/a>/\1/')
      for p in $pkgs; do
        add_url "$subfolder_url/$p"
      done
      ;;
    "arch")
      pkgs=$(curl -s -L "$subfolder_url" | 
            grep -oE '<a href="[^"]+\.zst">[^<]+\.zst</a>' | 
            sed -r 's/<a href="([^"]+\.zst)">[^<]+\.zst<\/a>/\1/')
      for p in $pkgs; do
        add_url "$subfolder_url/$p"
      done
      ;;
    "alpine")
      pkgs=$(curl -s -L "$subfolder_url" | 
            grep -oE '<a href="[^"]+\.apk">[^<]+\.apk</a>' | 
            sed -r 's/<a href="([^"]+\.apk)">[^<]+\.apk<\/a>/\1/')
      for p in $pkgs; do
        add_url "$subfolder_url/$p"
      done
      ;;
  esac

}
export -f get_packages

# Downloads packages, hashes them, saves it to urls.csv then throws away package data.
process_package() 
{
  local PACKAGE_URL=$1

  # Get current state from looking up the PURL in our urls.csv
  local cur_state
  cur_state=$(awk -F, -v url="$PACKAGE_URL" '$1==url{print $2}' "${OUTPUT_DIR}/urls.csv")
  
  if [[ $cur_state != -1 ]]; then
    log "Skipping already‑processed $PACKAGE_URL (state=$cur_state)"
    return
  fi

  # start progress of downloading it
  set_state "$PACKAGE_URL" 0
  log "Downloading $PACKAGE_URL"

  # wget our package and store it in a temp file. for any errors revert to -1 state
  local PACKAGE=$(basename "$PACKAGE_URL")
  local PACKAGE_FILE="${TEMP_DIR}/${PACKAGE}"

  if ! wget -q -O "$PACKAGE_FILE" "$PACKAGE_URL"; then
    log "ERROR: download failed – $PACKAGE_URL"
    set_state "$PACKAGE_URL" -1
    return
  fi

  local PACKAGE_NAME
  local PACKAGE_VERSION
  # Give our package a unique id to do the unpacking
  local uniq_id=$(uuidgen 2>/dev/null || echo "$$-$RANDOM")
  local PACKAGE_DIR="${TEMP_DIR}/${PACKAGE}-${uniq_id}"

  # each distro differs in package extraction
  case $DISTRO in
    "ubuntu"|"debian")
      # Extract name / version (assumes name_version_arch.deb)
      PACKAGE_NAME=${PACKAGE%%_*}
      PACKAGE_VERSION=$(echo "$PACKAGE" | cut -d '_' -f 2)

      # Store and unpack
      mkdir -p "$PACKAGE_DIR"
      if ! dpkg-deb -x "$PACKAGE_FILE" "$PACKAGE_DIR" 2>/dev/null; then
        log "ERROR: cannot extract $PACKAGE_FILE"
        rm -f "$PACKAGE_FILE"
        rm -rf "$PACKAGE_DIR"
        set_state "$PACKAGE_URL" -1
        return
      fi
      ;;
    "fedora")
      # Extract name / version (assumes name_version_arch.deb)
      PACKAGE_NAME=$(echo "$PACKAGE" | sed -r 's/(.+)-([0-9][^-]*)-([^-]+)\.[^.]+\.rpm/\1/')
      PACKAGE_VERSION=$(echo "$PACKAGE" | sed -r 's/(.+)-([0-9][^-]*)-([^-]+)\.[^.]+\.rpm/\2/')

      # Store and unpack
      mkdir -p "$PACKAGE_DIR"
      if ! rrpm2cpio "$PACKAGE_FILE" | cpio -idmv; then
        log "ERROR: cannot extract $PACKAGE_FILE"
        rm -f "$PACKAGE_FILE"
        rm -rf "$PACKAGE_DIR"
        set_state "$PACKAGE_URL" -1
        return
      fi
      ;;
    "rocky")
      # Extract name / version (assumes name_version_arch.deb)
      PACKAGE_NAME=$(echo "$PACKAGE" | sed -r 's/(.+)-([0-9][^-]*)-([^-]+)\.[^.]+\.rpm/\1/')
      PACKAGE_VERSION=$(echo "$PACKAGE" | sed -r 's/(.+)-([0-9][^-]*)-([^-]+)\.[^.]+\.rpm/\2-\3/')

      # Store and unpack
      mkdir -p "$PACKAGE_DIR"
      if ! rrpm2cpio "$PACKAGE_FILE" | cpio -idmv; then
        log "ERROR: cannot extract $PACKAGE_FILE"
        rm -f "$PACKAGE_FILE"
        rm -rf "$PACKAGE_DIR"
        set_state "$PACKAGE_URL" -1
        return
      fi
      ;;
    "centos")
      # Extract name, version, and release (format: name-version-release.dist.arch.rpm)
      PACKAGE_NAME=$(echo "$PACKAGE" | sed -r 's/(.+)-([0-9][^-]*)-([^-]+)\.[^.]+\.rpm/\1/')
      PACKAGE_VERSION=$(echo "$PACKAGE" | sed -r 's/(.+)-([0-9][^-]*)-([^-]+)\.[^.]+\.rpm/\2-\3/')

      # Store and unpack
      mkdir -p "$PACKAGE_DIR"
      if ! rrpm2cpio "$PACKAGE_FILE" | cpio -idmv; then
        log "ERROR: cannot extract $PACKAGE_FILE"
        rm -f "$PACKAGE_FILE"
        rm -rf "$PACKAGE_DIR"
        set_state "$PACKAGE_URL" -1
        return
      fi
      ;;
    "arch")
      # Extract name / version (assumes name_version_arch.deb)
      PACKAGE_NAME=$(echo "$PACKAGE" | sed -r 's/(.+)-([0-9][^-]+-[0-9]+)-[^-]+\.pkg\.tar\.zst/\1/')
      PACKAGE_VERSION=$(echo "$PACKAGE" | sed -r 's/(.+)-([0-9][^-]+-[0-9]+)-[^-]+\.pkg\.tar\.zst/\2/')

      # Store and unpack
      mkdir -p "$PACKAGE_DIR"
      if ! tar -x --use-compress-program=unzstd -f "$PACKAGE_FILE" -C "$PACKAGE_DIR" 2>/dev/null; then
        log "ERROR: cannot extract $PACKAGE_FILE"
        rm -f "$PACKAGE_FILE"
        rm -rf "$PACKAGE_DIR"
        set_state "$PACKAGE_URL" -1
        return
      fi
      ;;
    "alpine")
      # Extract name, version, and release (format: name-version-release.apk)
      PACKAGE_NAME=$(echo "$PACKAGE" | sed -r 's/(.+)-([^-]+-r[0-9]+)\.apk/\1/')
      PACKAGE_VERSION=$(echo "$PACKAGE" | sed -r 's/(.+)-([^-]+-r[0-9]+)\.apk/\2/')

      # Give our package a unique id to do the unpacking
      local uniq_id=$(uuidgen 2>/dev/null || echo "$$-$RANDOM")
      local PACKAGE_DIR="${TEMP_DIR}/${PACKAGE}-${uniq_id}"

      # Store and unpack
      mkdir -p "$PACKAGE_DIR"
      if ! tar -xzf "$PACKAGE_FILE" -C "$PACKAGE_DIR" 2>/dev/null; then
        log "ERROR: cannot extract $PACKAGE_FILE"
        rm -f "$PACKAGE_FILE"
        rm -rf "$PACKAGE_DIR"
        set_state "$PACKAGE_URL" -1
        return
      fi
      ;;
  esac
 
  
  # Compute sha256sum of the archive (.deb or .gz)
  local PKG_SHA=$(sha256sum "$PACKAGE_FILE" | cut -d' ' -f1)

  # write to the packages.csv with the hash we got from the package alone
  flock -x 200 -c "printf '%s,%s,%s,%s\n' \
        \"$PACKAGE_NAME\" \"$PACKAGE_VERSION\" \"$PKG_SHA\" \"$PACKAGE_URL\" \
        >> \"${OUTPUT_DIR}/packages.csv\""

  # Traverse every file and calculate its sha256sum 
  # (this is the most cpu intensive task for parallel processing that and I/O) 
  # we also write to the files.csv to save each packages checksum
  while IFS= read -r -d '' f; do
    local FILE_SHA=$(sha256sum "$f" | cut -d' ' -f1)
    local REL_PATH="${f#$PACKAGE_DIR/}"
    flock -x 201 -c "printf '%s,%s,%s,%s,%s\n' \
          \"$PACKAGE_NAME\" \"$PACKAGE_VERSION\" \"$FILE_SHA\" \"$REL_PATH\" \"$PACKAGE_URL\" \
          >> \"${OUTPUT_DIR}/files.csv\""
  done < <(find "$PACKAGE_DIR" -type f -print0)

  # Once everything is completed we mark the state as 1
  set_state "$PACKAGE_URL" 1
  log "Finished $PACKAGE_URL"

  # cleanup
  rm -f "$PACKAGE_FILE"
  rm -rf "$PACKAGE_DIR"
}
export -f process_package

# Main 

log "Script started – $(date '+%Y-%m-%d %H:%M:%S')"

# take in argument for which distro 
if [ "$#" -eq 0 ]; then
    log "Need to pass in distro name or --all (e.g. ubuntu, debian, fedora, rocky, centos, arch, alipine)"
    log "Usage $0 --distro ubuntu || --all  "
    exit 1
fi

log "$2"

case $2 in
  "ubuntu")
    TEMP_DIR="ubuntu/temp"
    OUTPUT_DIR="ubuntu/output"
    DISTRO=$2
    ;;
  "debian")
    TEMP_DIR="debian/temp"
    OUTPUT_DIR="debian/output"
    DISTRO=$2
    ;;
  "fedora")
    TEMP_DIR="fedora/temp"
    OUTPUT_DIR="fedora/output"
    DISTRO=$2
    ;;
  "rocky")
    TEMP_DIR="rocky/temp"
    OUTPUT_DIR="rocky/output"
    DISTRO=$2
    ;;
  "centos")
    TEMP_DIR="centos/temp"
    OUTPUT_DIR="centos/output"
    DISTRO=$2
    ;;
  "arch")
    TEMP_DIR="arch/temp"
    OUTPUT_DIR="arch/output"
    DISTRO=$2
    ;;
  "alpine")
    TEMP_DIR="alpine/temp"
    OUTPUT_DIR="alpine/output"
    DISTRO=$2
    ;;
  *)
    log "Not a supported distro"
    exit 1
    ;;
esac

# going to be used in diff funcs
export DISTRO

# have essential dirs existing
mkdir -p "$TEMP_DIR" "$OUTPUT_DIR"

# Initialise CSV files only once
if [[ ! -s "${OUTPUT_DIR}/packages.csv" ]]; then
  echo "name,version,sha256,url" > "${OUTPUT_DIR}/packages.csv"
fi
if [[ ! -s "${OUTPUT_DIR}/files.csv" ]]; then
  echo "name,version,sha256,file,url" > "${OUTPUT_DIR}/files.csv"
fi
if [[ ! -s "${OUTPUT_DIR}/urls.csv" ]]; then
  echo "url,state" > "${OUTPUT_DIR}/urls.csv"
fi

# If URLs have already been discovered we can resume, otherwise build them
if [[ -s "${OUTPUT_DIR}/urls.csv" && $(tail -n +2 "${OUTPUT_DIR}/urls.csv" | wc -l) -gt 0 ]]; then
  log "Resuming – URLs already discovered"
else
  # -------------------  BUILD LETTER LIST  ----------------------- #
  LETTERS_FILE="${TEMP_DIR}/letters.txt"
  >"$LETTERS_FILE"

  case $DISTRO in
    # ubuntu and debian run similar cause of their mirrors
    "ubuntu")
      for comp in "${UBUNTU_COMPONENTS[@]}"; do
        base="https://mirrors.kernel.org/ubuntu/pool/${comp}"
        folders=$(curl -s -L "$base" |
                  grep -oE '<a href="[^"]+">[^<]+</a>' |
                  sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/' |
                  grep -vE '^\.$|^\.\.$|^\?')
        for f in $folders; do
          echo "$base/$f" >> "$LETTERS_FILE"
        done
      done

      # -------------------  GET SUBFOLDERS  ------------------------ #
      # Open lock for subfolders file (fd 202)
      exec 202>>"${TEMP_DIR}/subfolders.txt"
      cat "$LETTERS_FILE" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_subfolders "{}"'

      # -------------------  GET PACKAGE URLs  ---------------------- #
      # Open lock for URLs file (fd 203) – we will only append here
      exec 203>>"${OUTPUT_DIR}/urls.csv"
      cat "${TEMP_DIR}/subfolders.txt" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_packages "{}"'

      log "URL discovery finished – $(tail -n +2 "${OUTPUT_DIR}/urls.csv" | wc -l) URLs recorded"
      ;;
    "debian")
      for comp in "${DEBIAN_COMPONENTS[@]}"; do
        base="https://mirrors.edge.kernel.org/debian/pool/${comp}"
        folders=$(curl -s -L "$base" |
                  grep -oE '<a href="[^"]+">[^<]+</a>' |
                  sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/' |
                  grep -vE '^\.$|^\.\.$|^\?')
        for f in $folders; do
          echo "$base/$f" >> "$LETTERS_FILE"
        done
      done

      # -------------------  GET SUBFOLDERS  ------------------------ #
      # Open lock for subfolders file (fd 202)
      exec 202>>"${TEMP_DIR}/subfolders.txt"
      cat "$LETTERS_FILE" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_subfolders "{}"'

      # -------------------  GET PACKAGE URLs  ---------------------- #
      # Open lock for URLs file (fd 203) – we will only append here
      exec 203>>"${OUTPUT_DIR}/urls.csv"
      cat "${TEMP_DIR}/subfolders.txt" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_packages "{}"'

      log "URL discovery finished – $(tail -n +2 "${OUTPUT_DIR}/urls.csv" | wc -l) URLs recorded"
      ;;
    "fedora")
      # why cant all distros organize like FEDORA 
      # -------------------  BUILD LETTER LIST  ----------------------- #
      for type in "${FEDORA_TYPE[@]}"; do
        for version in "${FEDORA_VERSIONS[@]}"; do
          if [ "$type" = "archive" ] && { [ "$version" == "41" ] || [ "$version" == "42" ]; } ; then
            continue
          fi
          base_url="https://download-ib01.fedoraproject.org/pub/${type}/fedora/linux/releases/${version}/Everything/x86_64/os/Packages/"
          
          # Get folders (letters)
          folders=$(curl -s -L "$base_url" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/' | grep -v '^\.$' | grep -v '^\.\.$' | grep -v '^?')
          
          for folder in $folders; do
            echo "$base_url/$folder" >> "$LETTERS_FILE"
          done

        done
      done

      # -------------------  GET SUBFOLDERS  ------------------------ #
      # Open lock for subfolders file (fd 202)
      exec 202>>"${TEMP_DIR}/subfolders.txt"
      cat "$LETTERS_FILE" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_subfolders "{}"'

      # -------------------  GET PACKAGE URLs  ---------------------- #
      # Open lock for URLs file (fd 203) – we will only append here
      exec 203>>"${OUTPUT_DIR}/urls.csv"
      cat "${TEMP_DIR}/subfolders.txt" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_packages "{}"'

      log "URL discovery finished – $(tail -n +2 "${OUTPUT_DIR}/urls.csv" | wc -l) URLs recorded"
      ;;
    "rocky")
      # -------------------  BUILD LETTER LIST  ----------------------- #
      for version in "${ROCKY_VERSIONS[@]}"; do
        base_url="https://dfw.mirror.rackspace.com/rocky/${version}/AppStream/x86_64/os/Packages/"
        
        # Get folders (letters)
        folders=$(curl -s -L "$base_url" | grep -oE '<a href="[^"]+">[^<]+</a>' | sed -r 's/<a href="([^"]+)">[^<]+<\/a>/\1/' | grep -v '^\.$' | grep -v '^\.\.$' | grep -v '^?')
        
        for folder in $folders; do
          echo "$base_url/$folder" >> "$LETTERS_FILE"
        done

      done

      # -------------------  GET SUBFOLDERS  ------------------------ #
      # Open lock for subfolders file (fd 202)
      exec 202>>"${TEMP_DIR}/subfolders.txt"
      cat "$LETTERS_FILE" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_subfolders "{}"'

      # -------------------  GET PACKAGE URLs  ---------------------- #
      # Open lock for URLs file (fd 203) – we will only append here
      exec 203>>"${OUTPUT_DIR}/urls.csv"
      cat "${TEMP_DIR}/subfolders.txt" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_packages "{}"'

      log "URL discovery finished – $(tail -n +2 "${OUTPUT_DIR}/urls.csv" | wc -l) URLs recorded"
      ;;
    "centos")
      # ------------------- GET URLS ------------------- #
      # it'll be slow but im so tired of trying to do everything in parallel, blame how its organized
      # Open lock for subfolders file (fd 202)
      exec 202>>"${TEMP_DIR}/subfolders.txt"
      for version in "${CENTOS_VERSIONS[@]}"; do
        echo "https://dfw.mirror.rackspace.com/centos-stream/${version}/AppStream/x86_64/os/Packages" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_subfolders "{}"'
      done
      # -------------------  GET PACKAGE URLs  ---------------------- #
      # Open lock for URLs file (fd 203) – we will only append here
      exec 203>>"${OUTPUT_DIR}/urls.csv"
      cat "${TEMP_DIR}/subfolders.txt" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_packages "{}"'

      log "URL discovery finished – $(tail -n +2 "${OUTPUT_DIR}/urls.csv" | wc -l) URLs recorded"
      ;;
    "arch")
      # -------------------  GET SUBFOLDERS  ------------------------ #
      # Open lock for subfolders file (fd 202)
      exec 202>>"${TEMP_DIR}/subfolders.txt"
      echo "https://mirrors.edge.kernel.org/archlinux/pool/packages" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_subfolders "{}"'

      # -------------------  GET PACKAGE URLs  ---------------------- #
      # Open lock for URLs file (fd 203) – we will only append here
      exec 203>>"${OUTPUT_DIR}/urls.csv"
      cat "${TEMP_DIR}/subfolders.txt" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_packages "{}"'

      log "URL discovery finished – $(tail -n +2 "${OUTPUT_DIR}/urls.csv" | wc -l) URLs recorded"
      ;;
    "alpine")
      # ------------------- GET URLS ------------------- #
      # it'll be slow but im so tired of trying to do everything in parallel, blame how its organized
      # Open lock for subfolders file (fd 202)
      exec 202>>"${TEMP_DIR}/subfolders.txt"
      for version in "${ALPINE_VERSIONS[@]}"; do
        for component in "${ALPINE_COMPONENTS[@]}"; do
          echo "https://mirrors.edge.kernel.org/alpine/${version}/${component}/x86_64" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_subfolders "{}"'
        done
      done
      # -------------------  GET PACKAGE URLs  ---------------------- #
      # Open lock for URLs file (fd 203) – we will only append here
      exec 203>>"${OUTPUT_DIR}/urls.csv"
      cat "${TEMP_DIR}/subfolders.txt" | xargs -P "$XARGS_PROCESSES" -I {} bash -c 'get_packages "{}"'

      log "URL discovery finished – $(tail -n +2 "${OUTPUT_DIR}/urls.csv" | wc -l) URLs recorded"

      ;;
    *)
      log "Not a supported distro"
      exit 1
      ;;
  esac
fi

# Open the lock‑file descriptors that will be used by the workers.
# These stay open for the whole time until script is done
exec 200>>"${OUTPUT_DIR}/packages.csv"
exec 201>>"${OUTPUT_DIR}/files.csv"
exec 204>>"${OUTPUT_DIR}/urls.csv"  

# Download and calculate sha256sum of packages and subfiles in them in parallel
log "Starting parallel processing of packages (up to $XARGS_PROCESSES workers)"
# Feed only the URL column (skip header)
tail -n +2 "${OUTPUT_DIR}/urls.csv" | cut -d, -f1 |
  xargs -P "$XARGS_PROCESSES" -I {} bash -c 'process_package "{}"'


# End result
PKGS=$(( $(wc -l < "${OUTPUT_DIR}/packages.csv") - 1 ))
FILES=$(( $(wc -l < "${OUTPUT_DIR}/files.csv") - 1 ))
DONE=$(awk -F, '$2==1{c++} END{print c}' "${OUTPUT_DIR}/urls.csv")
log "Finished – $PKGS packages, $FILES files, $DONE URLs marked as completed"

rm 200 201 202 203 204

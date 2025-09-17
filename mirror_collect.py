#!/usr/bin/env python3
"""
Mirror URL collector – writes URLs to CSV as soon as they are discovered.
Works for Ubuntu, Debian, CentOS, Rocky, Fedora, Alpine, and Arch mirrors.

goal is to replace the url processing in hash_distros with this since its gross to do in bash
"""

import os
import sys
import csv
import time
import argparse
import logging
import threading
from queue import Queue
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Mirror base URLs (trailing slash for consistency)
UBUNTU_MAIN_URL = "https://mirrors.edge.kernel.org/ubuntu/pool/main/"
UBUNTU_RESTRICTED_URL = "https://mirrors.edge.kernel.org/ubuntu/pool/restricted/"
UBUNTU_UNIVERSE_URL = "https://mirrors.edge.kernel.org/ubuntu/pool/universe/"
UBUNTU_MULTIVERSE_URL = "https://mirrors.edge.kernel.org/ubuntu/pool/multiverse/"

DEBIAN_URL = "https://mirrors.edge.kernel.org/debian/pool/main/"
DEBIAN_NONFREE_URL = "https://mirrors.edge.kernel.org/debian/pool/non-free/"

CENTOS_9_URL = "https://dfw.mirror.rackspace.com/centos-stream/9-stream/AppStream/x86_64/os/Packages/"
CENTOS_10_URL = "https://dfw.mirror.rackspace.com/centos-stream/10-stream/AppStream/x86_64/os/Packages/"

ROCKY_8_5_URL = "https://dl.rockylinux.org/vault/rocky/8.5/AppStream/x86_64/os/Packages/"
ROCKY_8_6_URL = "https://dl.rockylinux.org/vault/rocky/8.6/AppStream/x86_64/os/Packages/"
ROCKY_8_7_URL = "https://dl.rockylinux.org/vault/rocky/8.7/AppStream/x86_64/os/Packages/"
ROCKY_8_8_URL = "https://dl.rockylinux.org/vault/rocky/8.8/AppStream/x86_64/os/Packages/"
ROCKY_8_9_URL = "https://dl.rockylinux.org/vault/rocky/8.9/AppStream/x86_64/os/Packages/"
ROCKY_9_0_URL = "https://dl.rockylinux.org/vault/rocky/9.0/AppStream/x86_64/os/Packages/"
ROCKY_9_1_URL = "https://dl.rockylinux.org/vault/rocky/9.1/AppStream/x86_64/os/Packages/"
ROCKY_9_2_URL = "https://dl.rockylinux.org/vault/rocky/9.2/AppStream/x86_64/os/Packages/"
ROCKY_9_3_URL = "https://dl.rockylinux.org/vault/rocky/9.3/AppStream/x86_64/os/Packages/"
ROCKY_9_4_URL = "https://dl.rockylinux.org/vault/rocky/9.4/AppStream/x86_64/os/Packages/" 
ROCKY_9_5_URL = "https://dl.rockylinux.org/vault/rocky/9.5/AppStream/x86_64/os/Packages/"
ROCKY_9_6_URL = "https://dfw.mirror.rackspace.com/rocky/9.6/AppStream/x86_64/os/Packages/"
ROCKY_10_0_URL = "https://dfw.mirror.rackspace.com/rocky/10.0/AppStream/x86_64/os/Packages/"

FEDORA_38_URL = "https://download-ib01.fedoraproject.org/pub/archive/fedora/linux/releases/38/Everything/x86_64/os/Packages/"
FEDORA_39_URL = "https://download-ib01.fedoraproject.org/pub/archive/fedora/linux/releases/39/Everything/x86_64/os/Packages/"
FEDORA_40_URL = "https://download-ib01.fedoraproject.org/pub/archive/fedora/linux/releases/40/Everything/x86_64/os/Packages/"
FEDORA_41_URL = "https://download-ib01.fedoraproject.org/pub/fedora/linux/releases/41/Everything/x86_64/os/Packages/"
FEDORA_42_URL = "https://download-ib01.fedoraproject.org/pub/fedora/linux/releases/42/Everything/x86_64/os/Packages/"

ALPINE_3_18_M_URL = "https://mirrors.edge.kernel.org/alpine/v3.18/main/x86_64"
ALPINE_3_19_M_URL = "https://mirrors.edge.kernel.org/alpine/v3.19/main/x86_64"
ALPINE_3_2_M_URL = "https://mirrors.edge.kernel.org/alpine/v3.2/main/x86_64"
ALPINE_3_20_M_URL = "https://mirrors.edge.kernel.org/alpine/v3.20/main/x86_64"
ALPINE_3_21_M_URL = "https://mirrors.edge.kernel.org/alpine/v3.21/main/x86_64"
ALPINE_3_22_M_URL = "https://mirrors.edge.kernel.org/alpine/v3.22/main/x86_64"
ALPINE_S_M_URL = "https://mirrors.edge.kernel.org/alpine/latest-stable/main/x86_64"
ALPINE_E_M_URL = "https://mirrors.edge.kernel.org/alpine/edge/main/x86_64"

# rolling release distro doesnt have any versions to deal with
ARCH = "https://mirrors.edge.kernel.org/archlinux/pool/packages/"

# Helper: thread‑safe CSV writer (writes one row at a time)
csv_locks = {}   # distro → threading.Lock()




def _get_lock(distro: str) -> threading.Lock:
    """Create (or return) a lock for a given distro."""
    if distro not in csv_locks:
        csv_locks[distro] = threading.Lock()
    return csv_locks[distro]


def write_url_to_csv(distro: str, url: str) -> None:
    """
    Append a single URL to <distro>/output/urls.csv.
    The header is written only once (when the file is created).
    we add the state of -1 for later processing in hash_distro files
    """
    out_dir = os.path.join(distro, "output")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "urls.csv")

    lock = _get_lock(distro)
    with lock, open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if f.tell() == 0:                     # empty file → write header
            writer.writerow(["url", "state"])
        writer.writerow([url, "-1"])


# What we consider a “package file” – write it immediately and never fetch it
FILE_EXTENSIONS = (
    ".deb", ".rpm", ".zst", ".apk",
    ".tar.gz", ".tgz", ".tar.bz2", ".zip",
    ".xz", ".tar.xz", ".rpm", ".rpm2", ".rpm3"
)


def is_package(url: str) -> bool:
    """True if the URL ends with a known package extension (case‑insensitive)."""
    return url.lower().endswith(FILE_EXTENSIONS)


# Core scraper – BFS with a queue (no recursion)
def scrape_all_links(base_url: str, max_depth: int = 10, distro: str = "generic") -> None:
    """
    Crawl starting at *base_url*.
    Every discovered package file is written **immediately** to the CSV for *distro*.
    """
    visited = set()
    q = Queue()
    q.put((base_url, 0))

    while not q.empty():
        cur_url, depth = q.get()

        # Skip URLs we have already processed
        if cur_url in visited:
            continue
        visited.add(cur_url)

        # If the URL itself is a package file → write it and skip fetching
        if is_package(cur_url):
            write_url_to_csv(distro, cur_url)
            continue

        # Fetch the page – but only if it looks like HTML
        try:
            resp = requests.get(cur_url, timeout=5)
            resp.raise_for_status()
        except Exception as exc:
            print(f"ERROR fetching {cur_url}: {exc}", file=sys.stderr)
            continue

        # Some mirrors return a plain‑text directory listing with a
        # Content‑Type of “text/plain”.  We only want to feed HTML to BS.
        ct = resp.headers.get("Content-Type", "")
        if "text/html" not in ct.lower():
            # Not HTML → nothing to parse, just skip.
            continue

        # Parse the HTML – be tolerant to odd markup
        try:
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception:
            # Fallback to a more forgiving parser if the default fails
            try:
                soup = BeautifulSoup(resp.text, "lxml")
            except Exception:
                # Give up on this page – it’s not worth crashing the whole run
                print(f"WARNING: could not parse {cur_url}", file=sys.stderr)
                continue

        # Walk all <a> links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Skip navigation entries like "." or ".."
            if href in (".", "..", "./", "../"):
                continue

            full_url = urljoin(cur_url, href)

            # Keep only URLs that stay inside the same domain and under the base path
            if urlparse(full_url).netloc != urlparse(base_url).netloc:
                continue
            if not full_url.startswith(base_url):
                continue

            # If it looks like a package file → write immediately
            if is_package(full_url):
                write_url_to_csv(distro, full_url)
                continue

            # Otherwise queue it for further crawling (if we haven’t hit max depth)
            if depth < max_depth:
                q.put((full_url, depth + 1))



# Simple spinner – runs in its own daemon thread
def spinning_icon(stop_event: threading.Event):
    icons: list[str] = ["|", "/", "-", "\\"]
    i: int = 0
    while not stop_event.is_set():
        sys.stdout.write("\r" + icons[i])
        sys.stdout.flush()
        i = (i + 1) % len(icons)
        time.sleep(0.1)
    sys.stdout.write("\r")   # clean up the spinner character
    sys.stdout.flush()



def main():
    # support linux distro mirrors
    # in theory all linux distro mirrors should be the same, if there's discrepency then we have a bigger problem 
    distros: list[str] = ["debian", "ubuntu", "centos", "rocky", "fedora", "arch", "alpine"]
    
    parser = argparse.ArgumentParser(
        prog='Package URL Scraper',
        description='Scrapes package URLs from linux distro mirrors'
    )
    parser.add_argument('-d', '--distro', required=True, help=f"supported distros {distros}")
    args = parser.parse_args()

    # start our spinner
    stop_event = threading.Event()
    spinner = threading.Thread(target=spinning_icon, args=(stop_event,))
    spinner.daemon = True
    spinner.start()

    logging.basicConfig(format='%(levelname)s:%(message)s', filename=f'PURL_Scraper_{args.distro}.log', level=logging.DEBUG) 

    match args.distro:
        case "ubuntu":
            ubuntu_urls = [
                UBUNTU_MAIN_URL,
                UBUNTU_RESTRICTED_URL,
                UBUNTU_UNIVERSE_URL,
                UBUNTU_MULTIVERSE_URL,
            ]
            for u in ubuntu_urls:
                scrape_all_links(u, max_depth=10, distro="ubuntu")
        case "debian":
            for u in (DEBIAN_URL, DEBIAN_NONFREE_URL):
                scrape_all_links(u, max_depth=10, distro="debian")
        case "centos":
            for u in (CENTOS_9_URL, CENTOS_10_URL):
                scrape_all_links(u, max_depth=10, distro="centos")
        case "rocky":
            rocky_urls = [
                ROCKY_8_5_URL, ROCKY_8_6_URL, ROCKY_8_7_URL, ROCKY_8_8_URL,
                ROCKY_8_9_URL, ROCKY_9_0_URL, ROCKY_9_1_URL,
                ROCKY_9_2_URL, ROCKY_9_3_URL, ROCKY_9_4_URL, ROCKY_9_5_URL,
                ROCKY_9_6_URL, ROCKY_10_0_URL,
            ]
            for u in rocky_urls:
                scrape_all_links(u, max_depth=10, distro="rocky")
        case "fedora":
            fedora_urls = [
                FEDORA_38_URL, FEDORA_39_URL, FEDORA_40_URL,
                FEDORA_41_URL, FEDORA_42_URL,
            ]
            for u in fedora_urls:
                scrape_all_links(u, max_depth=10, distro="fedora")
        case "alpine":
            alpine_urls = [
                ALPINE_3_18_M_URL,
                ALPINE_3_19_M_URL,
                ALPINE_3_2_M_URL, 
                ALPINE_3_20_M_URL,
                ALPINE_3_21_M_URL,
                ALPINE_3_22_M_URL,
                ALPINE_S_M_URL,   
                ALPINE_E_M_URL,   
            ]
            for u in alpine_urls:
                scrape_all_links(u, max_depth=10, distro="alpine")
        case "arch":
            scrape_all_links(ARCH, 10, "arch")

    # stop our spinner we are done
    stop_event.set()
    spinner.join()
    print(f"Done processing URLS for {args.distro}!")


if __name__ == "__main__":
    main()

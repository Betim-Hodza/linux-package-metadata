import os
import sys
import csv
import time
import threading
from queue import Queue
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import concurrent.futures

# Define constants and helper functions
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

ALPINE_3_18_M_URL = "https://mirrors.edge.kernel.org/alpine/v3.18/main/"
ALPINE_3_19_M_URL = "https://mirrors.edge.kernel.org/alpine/v3.19/main/"
ALPINE_3_2_M_URL = "https://mirrors.edge.kernel.org/alpine/v3.2/main/"
ALPINE_3_20_M_URL = "https://mirrors.edge.kernel.org/alpine/v3.20/main/"
ALPINE_3_21_M_URL = "https://mirrors.edge.kernel.org/alpine/v3.21/main/"
ALPINE_3_22_M_URL = "https://mirrors.edge.kernel.org/alpine/v3.22/main/"
ALPINE_S_M_URL = "https://mirrors.edge.kernel.org/alpine/latest-stable/main/"
ALPINE_E_M_URL = "https://mirrors.edge.kernel.org/alpine/edge/main/"
package_count = 0

# Define helper functions
def is_package(url: str) -> bool:
    FILE_EXTENSIONS = (
        ".deb", ".rpm", ".zst", ".apk",
        ".tar.gz", ".tgz", ".tar.bz2", ".zip",
        ".xz", ".tar.xz", ".rpm", ".rpm2", ".rpm3"
    )
    return url.lower().endswith(FILE_EXTENSIONS)

def scrape_all_links(base_url: str, max_depth: int = 10, distro: str = "generic") -> None:
    global package_count
    visited = set()
    q = Queue()
    q.put((base_url, 0))

    while not q.empty():
        cur_url, depth = q.get()

        if cur_url in visited:
            continue
        visited.add(cur_url)

        if is_package(cur_url):
            package_count += 1
            continue

        try:
            resp = requests.get(cur_url, timeout=5)
            resp.raise_for_status()
        except Exception as exc:
            print(f"ERROR fetching {cur_url}: {exc}", file=sys.stderr)
            continue

        ct = resp.headers.get("Content-Type", "")
        if "text/html" not in ct.lower():
            continue

        try:
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception:
            try:
                soup = BeautifulSoup(resp.text, "lxml")
            except Exception:
                print(f"WARNING: could not parse {cur_url}", file=sys.stderr)
                continue

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href in (".", "..", "./", "../"):
                continue

            full_url = urljoin(cur_url, href)

            if urlparse(full_url).netloc != urlparse(base_url).netloc:
                continue
            if not full_url.startswith(base_url):
                continue

            if is_package(full_url):
                package_count += 1
                continue

            if depth < max_depth:
                q.put((full_url, depth + 1))

def spinning_icon(stop_event: threading.Event):
    icons = ["|", "/", "-", "\\"]
    i = 0
    while not stop_event.is_set():
        sys.stdout.write("\r" + icons[i])
        sys.stdout.flush()
        i = (i + 1) % len(icons)
        time.sleep(0.1)
    sys.stdout.write("\r")   
    sys.stdout.flush()

def main():
    stop_event = threading.Event()
    spinner = threading.Thread(target=spinning_icon, args=(stop_event,))
    spinner.daemon = True
    spinner.start()

    urls_to_scrape = [
        # Ubuntu
        (UBUNTU_MAIN_URL, "ubuntu"),
        (UBUNTU_RESTRICTED_URL, "ubuntu"),
        (UBUNTU_UNIVERSE_URL, "ubuntu"),
        (UBUNTU_MULTIVERSE_URL, "ubuntu"),
        # Debian
        (DEBIAN_URL, "debian"),
        (DEBIAN_NONFREE_URL, "debian"),
        # CentOS
        (CENTOS_9_URL, "centos"),
        (CENTOS_10_URL, "centos"),
        # Rocky
        (ROCKY_8_5_URL, "rocky"),
        (ROCKY_8_6_URL, "rocky"),
        (ROCKY_8_7_URL, "rocky"),
        (ROCKY_8_8_URL, "rocky"),
        (ROCKY_8_9_URL, "rocky"),
        (ROCKY_9_0_URL, "rocky"),
        (ROCKY_9_1_URL, "rocky"),
        (ROCKY_9_2_URL, "rocky"),
        (ROCKY_9_3_URL, "rocky"),
        (ROCKY_9_4_URL, "rocky"),
        (ROCKY_9_5_URL, "rocky"),
        (ROCKY_9_6_URL, "rocky"),
        (ROCKY_10_0_URL, "rocky"),
        # Fedora
        (FEDORA_38_URL, "fedora"),
        (FEDORA_39_URL, "fedora"),
        (FEDORA_40_URL, "fedora"),
        (FEDORA_41_URL, "fedora"),
        (FEDORA_42_URL, "fedora"),
        # Alpine
        (ALPINE_3_18_M_URL, "alpine"),
        (ALPINE_3_18_R_URL, "alpine"),
        (ALPINE_3_18_C_URL, "alpine"),
        (ALPINE_3_19_M_URL, "alpine"),
        (ALPINE_3_19_R_URL, "alpine"),
        (ALPINE_3_19_C_URL, "alpine"),
        (ALPINE_3_2_M_URL, "alpine"),
        (ALPINE_3_2_R_URL, "alpine"),
        (ALPINE_3_20_M_URL, "alpine"),
        (ALPINE_3_20_R_URL, "alpine"),
        (ALPINE_3_20_C_URL, "alpine"),
        (ALPINE_3_21_M_URL, "alpine"),
        (ALPINE_3_21_R_URL, "alpine"),
        (ALPINE_3_21_C_URL, "alpine"),
        (ALPINE_3_22_M_URL, "alpine"),
        (ALPINE_3_22_R_URL, "alpine"),
        (ALPINE_3_22_C_URL, "alpine"),
        (ALPINE_S_M_URL, "alpine"),
        (ALPINE_S_R_URL, "alpine"),
        (ALPINE_S_C_URL, "alpine"),
        (ALPINE_E_M_URL, "alpine"),
        (ALPINE_E_R_URL, "alpine"),
        (ALPINE_E_C_URL, "alpine"),
    ]

    package_counts = {"ubuntu": 0, "debian": 0, "centos": 0, "rocky": 0, "fedora": 0, "alpine": 0}

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for url, distro in urls_to_scrape:
            future = executor.submit(scrape_all_links, url, max_depth=10, distro=distro)
            futures.append((future, distro))

        for future, distro in futures:
            future.result()
            package_counts[distro] += package_count
            package_count = 0

    for distro, count in package_counts.items():
        print(f"Number of {distro} packages: {count}")

    stop_event.set()
    spinner.join()
    print("Done!")

if __name__ == "__main__":
    main()

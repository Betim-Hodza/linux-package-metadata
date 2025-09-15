import os
import requests
from bs4 import BeautifulSoup
import csv

# Define the mirror URLs and components
UBUNTU_COMPONENTS = ["main", "restricted", "universe", "multiverse"]
UBUNTU_URL = "https://mirrors.edge.kernel.org/ubuntu/pool/"

DEBIAN_COMPONENTS = ["main", "non-free"]
DEBIAN_URL = "https://mirrors.edge.kernel.org/debian/pool/"

CENTOS_VERSIONS = ["9-stream", "10-stream"]
CENTOS_URL = "https://dfw.mirror.rackspace.com/centos-stream/{}/AppStream/x86_64/os/Packages/"

ROCKY_VERSIONS = ["8.5", "8.6", "8.7", "8.8", "8.9", "8.10", "9.0", "9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "10.0"]
ROCKY_URL = "https://dfw.mirror.rackspace.com/rocky/{}/AppStream/x86_64/os/Packages/"

FEDORA_TYPE = ["archive"]
FEDORA_VERSIONS = ["38", "39", "40", "41", "42"]
FEDORA_URL = "https://download-ib01.fedoraproject.org/pub/{}/fedora/linux/releases/{}/Everything/x86_64/os/Packages/"

ALPINE_VERSIONS = ["v3.18", "v3.19", "v3.2", "v3.20", "v3.21", "v3.22", "latest-stable", "edge"]
ALPINE_COMPONENTS = ["main", "release", "community"]
ALPINE_URL = "https://mirrors.edge.kernel.org/alpine/{}/{}"

ARCH_URL = "https://mirrors.edge.kernel.org/archlinux/pool/packages"

def collect_urls(url, base_url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a')
        package_links = []
        for link in links:
            href = link.get('href')
            if href and (href.endswith(('.deb', '.rpm', '.pkg.tar.xz')) or href.startswith('/')):
                if href.startswith('/'):
                    package_links.append(os.path.join(base_url, href.lstrip('/')))
                else:
                    package_links.append(os.path.join(url, href))
            elif href and href.startswith('../'):
                parent_url = os.path.dirname(url)
                package_links.extend(collect_urls(parent_url, base_url))
            elif href and not href.startswith('/'):
                package_links.extend(collect_urls(os.path.join(url, href), base_url))
        return package_links
    except Exception as e:
        print(f"Error collecting URLs from {url}: {e}")
        return []

def save_urls_to_csv(urls, distro):
    output_dir = f"{distro}/output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    with open(f"{output_dir}/urls.csv", 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["url", "state"])
        for url in urls:
            writer.writerow([url, "-1"])

def main():
    # Ubuntu
    ubuntu_urls = []
    for component in UBUNTU_COMPONENTS:
        url = os.path.join(UBUNTU_URL, component)
        ubuntu_urls.extend(collect_urls(url, UBUNTU_URL))
    save_urls_to_csv(ubuntu_urls, "ubuntu")

    # Debian
    debian_urls = []
    for component in DEBIAN_COMPONENTS:
        url = os.path.join(DEBIAN_URL, component)
        debian_urls.extend(collect_urls(url, DEBIAN_URL))
    save_urls_to_csv(debian_urls, "debian")

    # CentOS
    centos_urls = []
    for version in CENTOS_VERSIONS:
        url = CENTOS_URL.format(version)
        centos_urls.extend(collect_urls(url, CENTOS_URL.format('')))
    save_urls_to_csv(centos_urls, "centos")

    # Rocky
    rocky_urls = []
    for version in ROCKY_VERSIONS:
        url = ROCKY_URL.format(version)
        rocky_urls.extend(collect_urls(url, ROCKY_URL.format('')))
    save_urls_to_csv(rocky_urls, "rocky")

    # Fedora
    fedora_urls = []
    for type in FEDORA_TYPE:
        for version in FEDORA_VERSIONS:
            url = FEDORA_URL.format(type, version)
            fedora_urls.extend(collect_urls(url, FEDORA_URL.format(type, '')))
    save_urls_to_csv(fedora_urls, "fedora")

    # Alpine
    alpine_urls = []
    for version in ALPINE_VERSIONS:
        for component in ALPINE_COMPONENTS:
            url = ALPINE_URL.format(version, component)
            alpine_urls.extend(collect_urls(url, ALPINE_URL.format(version, '')))
    save_urls_to_csv(alpine_urls, "alpine")

    # Arch
    arch_urls = collect_urls(ARCH_URL, ARCH_URL)
    save_urls_to_csv(arch_urls, "arch")

if __name__ == '__main__':
    main()
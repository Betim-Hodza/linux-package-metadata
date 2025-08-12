import concurrent.futures
import csv
import os
import requests
import shutil
import subprocess
import uuid

# GLOBALS
MAX_THREADS = 10
UBUNTU_COMPONENTS = ["main", "restricted", "universe", "multiverse"]
TEMP_DIR = "temp"
OUTPUT_DIR="output"


# Function to update the status of a package
def update_status(package_url, status):
    with open(os.path.join(OUTPUT_DIR, "urls.csv"), "r+", newline="") as csvfile:
        reader = csv.reader(csvfile)
        rows = list(reader)
        for row in rows:
            if row[0] == package_url:
                row[1] = status
                break
        csvfile.seek(0)
        writer = csv.writer(csvfile)
        writer.writerows(rows)
        csvfile.truncate()


# Get subfolders from a letter url
def get_subfolders(letter_url: str):
    # get the response object from url
    response = requests.get(letter_url)

    # grab each subfolder from the letter url. g -> gcc-15, gcc14, etc...
    subfolders = []
    for line in response.text.splitlines():
        if line.startswith("<a href="):
            subfolder = line.split('"')[1]
            subfolders.append(f"{letter_url}/{subfolder}")
    
    return subfolders

# these two functions are split apart for the 
# fact we'll make this one big script in the 
# future to choose which disto hashes to generate

# get the package url form a subfolder URL
def get_packages(subfolder_url: str):
    response = requests.get(subfolder_url)
    
    packages = []
    for line in response.text.splitlines():
        if line.startswith("<a href=") and line.endswith(".deb\""):
            package = line.split('"')[1]
            packages.append(f"{subfolder_url}/{package}")
    return packages

# Process a single PURL (package url)
def process_package(package_url: str):
    package: str = os.path.basename(package_url)
    package_file: str = os.path.join(TEMP_DIR, package)
    unique_id: str = str(uuid.uuid4())
    package_dir = os.path.join(TEMP_DIR, f"{package}-{unique_id}")

    # Update status to 0 (downloading)
    update_status(package_url, 0)

    try:
        # Download package and write to disk
        response = requests.get(package_url, stream=True)
        with open(package_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)

        # Extract name and version for ubuntu (name_version_arch.deb)
        package_name = package.split("_")[0]
        package_version = package.split("_")[1]

        # Create a temp package directory
        os.makedirs(package_dir, exist_ok=True)

        # Extract package contents
        subprocess.run(["dpkg-deb", "-x", package_file, package_dir])

        # Calculate sha256sum of the package
        package_sha256sum: str = subprocess.run(["sha256sum", package_file], capture_output=True, text=True).stdout.strip()

        # Append package metadata to CSV file
        with open(os.path.join(OUTPUT_DIR, "packages.csv"), "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([package_name, package_version, package_sha256sum, package_url])

        # Loop through all files in the package and get their sha256 sum as well
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = os.path.join(root, file)
                file_sha256sum = subprocess.run(["sha256sum", file_path], capture_output=True, text=True).stdout.strip()
                relative_file = os.path.relpath(file_path, package_dir)

                # Append file metadata to CSV file
                with open(os.path.join(OUTPUT_DIR, "files.csv"), "a", newline="") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow([package_name, package_version, file_sha256sum, relative_file, package_url])

        # Update status to 1 (processed successfully)
        update_status(package_url, 1)

    except Exception as e:
        # Update status to 0 (downloaded but failed to process)
        update_status(package_url, 0)
        print(f"Error processing package {package_url}: {e}")

    finally:
        # Cleanup
        if os.path.exists(package_file):
            os.remove(package_file)
        if os.path.exists(package_dir):
            shutil.rmtree(package_dir)

# Main function
def main():
    # Create output and temp dirs to work in
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    # Initialize CSV files packages, files, and urls if they don't exist
    if not os.path.exists(os.path.join(OUTPUT_DIR, "packages.csv")):
        with open(os.path.join(OUTPUT_DIR, "packages.csv"), "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["name", "version", "sha256", "url"])

    if not os.path.exists(os.path.join(OUTPUT_DIR, "files.csv")):
        with open(os.path.join(OUTPUT_DIR, "files.csv"), "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["name", "version", "sha256", "file", "url"])

    if not os.path.exists(os.path.join(OUTPUT_DIR, "urls.csv")):
        with open(os.path.join(OUTPUT_DIR, "urls.csv"), "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["url", "status"])

    # Get letter URLs
    letter_urls = []
    for component in UBUNTU_COMPONENTS:
        base_url = f"https://mirrors.kernel.org/ubuntu/pool/{component}"
        response = requests.get(base_url)
        for line in response.text.splitlines():
            if line.startswith("<a href="):
                letter_url = line.split('"')[1]
                letter_urls.append(f"{base_url}/{letter_url}")

    # Get subfolder URLs
    subfolder_urls = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(get_subfolders, letter_url): letter_url for letter_url in letter_urls}
        for future in concurrent.futures.as_completed(futures):
            letter_url = futures[future]
            try:
                subfolders = future.result()
                subfolder_urls.extend(subfolders)
            except Exception as e:
                print(f"Error getting subfolders for {letter_url}: {e}")

    # Get package URLs
    package_urls = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(get_packages, subfolder_url): subfolder_url for subfolder_url in subfolder_urls}
        for future in concurrent.futures.as_completed(futures):
            subfolder_url = futures[future]
            try:
                packages = future.result()
                package_urls.extend(packages)
            except Exception as e:
                print(f"Error getting packages for {subfolder_url}: {e}")

    # Add package URLs to urls.csv with status -1 (not worked on yet) if they don't exist
    if os.path.exists(os.path.join(OUTPUT_DIR, "urls.csv")):
        with open(os.path.join(OUTPUT_DIR, "urls.csv"), "r", newline="") as csvfile:
            reader = csv.reader(csvfile)
            existing_urls = [row[0] for row in reader]
            for package_url in package_urls:
                if package_url not in existing_urls:
                    with open(os.path.join(OUTPUT_DIR, "urls.csv"), "a", newline="") as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow([package_url, -1])
    else:
        with open(os.path.join(OUTPUT_DIR, "urls.csv"), "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            for package_url in package_urls:
                writer.writerow([package_url, -1])

    # Process packages
    with open(os.path.join(OUTPUT_DIR, "urls.csv"), "r", newline="") as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip header
        for row in reader:
            package_url = row[0]
            status = int(row[1])
            # if the status is -1 (not worked on) or 0 (error occurred during process) run
            if status == -1 or status == 0:
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                    futures = {executor.submit(process_package, package_url): package_url for package_url in [package_url]}
                    for future in concurrent.futures.as_completed(futures):
                        package_url = futures[future]
                        try:
                            future.result()
                        except Exception as e:
                            print(f"Error processing package {package_url}: {e}")

if __name__ == "__main__":
    main()

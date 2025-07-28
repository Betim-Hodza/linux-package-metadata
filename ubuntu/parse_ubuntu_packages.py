#!/usr/bin/env python3

import os
import sys
import csv
import gzip
import logging
from pathlib import Path
from typing import Dict, List, Optional, Iterator
import re
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils import LicenseDetector, SHASplitter, PURLGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UbuntuPackageParser:
    def __init__(self):
        self.license_detector = LicenseDetector()
        self.sha_splitter = SHASplitter()
        self.purl_generator = PURLGenerator()
        
        self.script_dir = Path(__file__).parent
        self.temp_dir = self.script_dir.parent / "temp" / "ubuntu"
        self.output_dir = self.script_dir.parent / "output" / "ubuntu"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def parse_packages_file(self, file_path: Path) -> Iterator[Dict[str, str]]:
        """Parse a Packages file and yield package dictionaries."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                current_package = {}
                
                for line in f:
                    line = line.rstrip('\n')
                    
                    if not line:
                        if current_package:
                            yield current_package
                            current_package = {}
                        continue
                    
                    if line.startswith(' ') or line.startswith('\t'):
                        if current_field:
                            current_package[current_field] += '\n' + line.strip()
                        continue
                    
                    if ':' in line:
                        field, value = line.split(':', 1)
                        current_field = field.strip()
                        current_package[current_field] = value.strip()
                
                if current_package:
                    yield current_package
                    
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
    
    def extract_package_metadata(self, package: Dict[str, str], release: str, component: str, architecture: str) -> Dict[str, str]:
        """Extract and normalize package metadata."""
        name = package.get('Package', '')
        version = package.get('Version', '')
        
        sha256, sha512 = self.sha_splitter.extract_from_package_metadata(package)
        
        if not sha256:
            sha256_field = package.get('SHA256', '')
            if sha256_field:
                sha256, _ = self.sha_splitter.extract_hashes(sha256_field)
        
        if not sha512:
            sha512_field = package.get('SHA512', '')
            if sha512_field:
                _, sha512 = self.sha_splitter.extract_hashes(sha512_field)
        
        filename = package.get('Filename', '')
        if filename:
            deb_url = f"http://archive.ubuntu.com/ubuntu/{filename}"
        else:
            deb_url = ""
        
        license_info = self.license_detector.guess_license_from_fields(package)
        if not license_info:
            license_info = "Unknown"
        
        purl = self.purl_generator.generate_deb_purl(
            name=name,
            version=version,
            distribution="ubuntu",
            component=component,
            architecture=architecture
        )
        
        return {
            'package': name,
            'version': version,
            'sha256': sha256 or '',
            'sha512': sha512 or '',
            'component': component,
            'architecture': architecture,
            'deb_url': deb_url,
            'license': license_info,
            'purl': purl,
            'release': release
        }
    
    def parse_release_info(self) -> Dict[str, str]:
        """Parse Ubuntu release information."""
        releases = {}
        for release_file in self.temp_dir.glob("Release_*"):
            release_name = release_file.name.replace("Release_", "")
            try:
                with open(release_file, 'r') as f:
                    content = f.read()
                    releases[release_name] = content
            except Exception as e:
                logger.error(f"Error reading release file {release_file}: {e}")
        return releases
    
    def process_all_packages(self):
        """Process all downloaded Ubuntu package files."""
        logger.info("Starting Ubuntu package processing")
        
        packages_files = list(self.temp_dir.glob("Packages_*"))
        if not packages_files:
            logger.error("No package files found in temp directory")
            return
        
        all_packages = []
        
        for packages_file in packages_files:
            try:
                filename_parts = packages_file.stem.split('_')
                if len(filename_parts) >= 4:
                    release = filename_parts[1]
                    component = filename_parts[2]
                    architecture = filename_parts[3]
                else:
                    logger.warning(f"Unexpected filename format: {packages_file}")
                    continue
                
                logger.info(f"Processing {packages_file.name}")
                
                package_count = 0
                for package in self.parse_packages_file(packages_file):
                    try:
                        metadata = self.extract_package_metadata(package, release, component, architecture)
                        all_packages.append(metadata)
                        package_count += 1
                    except Exception as e:
                        logger.error(f"Error processing package in {packages_file}: {e}")
                
                logger.info(f"Processed {package_count} packages from {packages_file.name}")
                
            except Exception as e:
                logger.error(f"Error processing file {packages_file}: {e}")
        
        if all_packages:
            output_file = self.output_dir / "ubuntu_packages.csv"
            self.write_csv(all_packages, output_file)
            logger.info(f"Written {len(all_packages)} packages to {output_file}")
        else:
            logger.warning("No packages processed")
    
    def write_csv(self, packages: List[Dict[str, str]], output_file: Path):
        """Write packages to CSV file."""
        fieldnames = ['package', 'version', 'sha256', 'sha512', 'component', 
                     'architecture', 'deb_url', 'license', 'purl', 'release']
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(packages)
        except Exception as e:
            logger.error(f"Error writing CSV file {output_file}: {e}")

def main():
    parser = UbuntuPackageParser()
    parser.process_all_packages()

if __name__ == "__main__":
    main()
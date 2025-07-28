#!/usr/bin/env python3

import os
import sys
import csv
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Iterator
import re
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils import LicenseDetector, SHASplitter, PURLGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CentOSPackageParser:
    def __init__(self):
        self.license_detector = LicenseDetector()
        self.sha_splitter = SHASplitter()
        self.purl_generator = PURLGenerator()
        
        self.script_dir = Path(__file__).parent
        self.temp_dir = self.script_dir.parent / "temp" / "centos"
        self.output_dir = self.script_dir.parent / "output" / "centos"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.namespaces = {
            'rpm': 'http://linux.duke.edu/metadata/common',
            'repo': 'http://linux.duke.edu/metadata/repo'
        }
    
    def parse_primary_xml(self, file_path: Path) -> Iterator[Dict[str, str]]:
        """Parse a primary.xml file and yield package dictionaries."""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            for package in root.findall('.//rpm:package', self.namespaces):
                try:
                    pkg_data = {}
                    
                    # Get package name from child element, not attribute
                    name_elem = package.find('rpm:name', self.namespaces)
                    pkg_data['name'] = name_elem.text if name_elem is not None else ''
                    
                    # Get architecture from child element
                    arch_elem = package.find('rpm:arch', self.namespaces)
                    pkg_data['arch'] = arch_elem.text if arch_elem is not None else ''
                    
                    version_elem = package.find('rpm:version', self.namespaces)
                    if version_elem is not None:
                        epoch = version_elem.get('epoch', '0')
                        ver = version_elem.get('ver', '')
                        rel = version_elem.get('rel', '')
                        
                        if epoch and epoch != '0':
                            pkg_data['version'] = f"{epoch}:{ver}-{rel}"
                        else:
                            pkg_data['version'] = f"{ver}-{rel}"
                        
                        pkg_data['epoch'] = epoch
                        pkg_data['ver'] = ver
                        pkg_data['rel'] = rel
                    
                    description_elem = package.find('rpm:description', self.namespaces)
                    if description_elem is not None:
                        pkg_data['description'] = description_elem.text or ''
                    
                    summary_elem = package.find('rpm:summary', self.namespaces)
                    if summary_elem is not None:
                        pkg_data['summary'] = summary_elem.text or ''
                    
                    url_elem = package.find('rpm:url', self.namespaces)
                    if url_elem is not None:
                        pkg_data['url'] = url_elem.text or ''
                    
                    packager_elem = package.find('rpm:packager', self.namespaces)
                    if packager_elem is not None:
                        pkg_data['packager'] = packager_elem.text or ''
                    
                    location_elem = package.find('rpm:location', self.namespaces)
                    if location_elem is not None:
                        pkg_data['location_href'] = location_elem.get('href', '')
                    
                    checksum_elem = package.find('rpm:checksum', self.namespaces)
                    if checksum_elem is not None:
                        checksum_type = checksum_elem.get('type', '').lower()
                        checksum_value = checksum_elem.text or ''
                        if checksum_type == 'sha256':
                            pkg_data['sha256'] = checksum_value
                        elif checksum_type == 'sha1':
                            pkg_data['sha1'] = checksum_value
                    
                    format_elem = package.find('rpm:format', self.namespaces)
                    if format_elem is not None:
                        license_elem = format_elem.find('rpm:license', self.namespaces)
                        if license_elem is not None:
                            pkg_data['license'] = license_elem.text or ''
                        
                        group_elem = format_elem.find('rpm:group', self.namespaces)
                        if group_elem is not None:
                            pkg_data['group'] = group_elem.text or ''
                    
                    yield pkg_data
                    
                except Exception as e:
                    logger.error(f"Error parsing package in {file_path}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error parsing XML file {file_path}: {e}")
    
    def extract_package_metadata(self, package: Dict[str, str], release: str, repo: str, architecture: str) -> Optional[Dict[str, str]]:
        """Extract and normalize package metadata."""
        name = package.get('name', '').strip()
        version = package.get('version', '').strip()
        ver = package.get('ver', '').strip()
        
        # Skip packages without required fields
        if not name or not ver:
            return None
        
        sha256 = package.get('sha256', '')
        sha512 = ''
        
        location_href = package.get('location_href', '')
        if location_href:
            if release == "7":
                if repo == "os":
                    rpm_url = f"http://vault.centos.org/7.9.2009/os/{architecture}/{location_href}"
                elif repo == "updates":
                    rpm_url = f"http://vault.centos.org/7.9.2009/updates/{architecture}/{location_href}"
                elif repo == "extras":
                    rpm_url = f"http://vault.centos.org/7.9.2009/extras/{architecture}/{location_href}"
                else:
                    rpm_url = location_href
            elif release == "8":
                if repo == "baseos":
                    rpm_url = f"http://vault.centos.org/8.5.2111/BaseOS/{architecture}/os/{location_href}"
                elif repo == "appstream":
                    rpm_url = f"http://vault.centos.org/8.5.2111/AppStream/{architecture}/os/{location_href}"
                elif repo == "extras":
                    rpm_url = f"http://vault.centos.org/8.5.2111/extras/{architecture}/os/{location_href}"
                else:
                    rpm_url = location_href
            else:  # CentOS 9 Stream
                if repo == "baseos":
                    rpm_url = f"http://mirror.stream.centos.org/9-stream/BaseOS/{architecture}/os/{location_href}"
                elif repo == "appstream":
                    rpm_url = f"http://mirror.stream.centos.org/9-stream/AppStream/{architecture}/os/{location_href}"
                elif repo == "extras":
                    rpm_url = f"http://mirror.stream.centos.org/9-stream/extras-common/{location_href}"
                else:
                    rpm_url = location_href
        else:
            rpm_url = ""
        
        license_info = package.get('license', '')
        if license_info:
            detected_license = self.license_detector.detect_license(license_info)
            license_info = detected_license if detected_license else license_info
        else:
            license_info = self.license_detector.guess_license_from_fields(package)
            if not license_info:
                license_info = "Unknown"
        
        purl = self.purl_generator.generate_rpm_purl(
            name=name,
            version=ver,
            distribution="centos",
            release=package.get('rel', ''),
            architecture=architecture,
            epoch=package.get('epoch', '0') if package.get('epoch', '0') != '0' else None
        )
        
        return {
            'package': name,
            'version': version,
            'sha256': sha256,
            'sha512': sha512,
            'component': repo,
            'architecture': architecture,
            'deb_url': rpm_url,
            'license': license_info,
            'purl': purl,
            'release': f"el{release}"
        }
    
    def process_all_packages(self):
        """Process all downloaded CentOS package files."""
        logger.info("Starting CentOS package processing")
        
        primary_files = list(self.temp_dir.glob("primary_*.xml"))
        if not primary_files:
            logger.error("No primary.xml files found in temp directory")
            return
        
        all_packages = []
        
        for primary_file in primary_files:
            try:
                filename_parts = primary_file.stem.split('_')
                if len(filename_parts) >= 4:
                    release = filename_parts[1]
                    repo = filename_parts[2]
                    architecture = filename_parts[3]
                else:
                    logger.warning(f"Unexpected filename format: {primary_file}")
                    continue
                
                logger.info(f"Processing {primary_file.name}")
                
                package_count = 0
                for package in self.parse_primary_xml(primary_file):
                    try:
                        metadata = self.extract_package_metadata(package, release, repo, architecture)
                        if metadata:  # Only process valid packages
                            all_packages.append(metadata)
                            package_count += 1
                    except Exception as e:
                        logger.error(f"Error processing package in {primary_file}: {e}")
                
                logger.info(f"Processed {package_count} packages from {primary_file.name}")
                
            except Exception as e:
                logger.error(f"Error processing file {primary_file}: {e}")
        
        if all_packages:
            output_file = self.output_dir / "centos_packages.csv"
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
    parser = CentOSPackageParser()
    parser.process_all_packages()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3

import os
import sys
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils import SHASplitter, PURLGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OutputValidator:
    def __init__(self):
        self.sha_splitter = SHASplitter()
        self.purl_generator = PURLGenerator()
        
        self.script_dir = Path(__file__).parent
        self.output_dir = self.script_dir.parent / "final_output"
        
        self.required_fields = [
            'package', 'version', 'sha256', 'sha512', 'component',
            'architecture', 'deb_url', 'license', 'purl', 'release'
        ]
        
        self.validation_results = {
            'total_files': 0,
            'total_packages': 0,
            'valid_packages': 0,
            'errors': [],
            'warnings': [],
            'file_stats': {}
        }
    
    def validate_csv_structure(self, csv_file: Path) -> bool:
        """Validate CSV file structure and headers."""
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                if not headers:
                    self.validation_results['errors'].append(f"{csv_file.name}: No headers found")
                    return False
                
                missing_fields = set(self.required_fields) - set(headers)
                if missing_fields:
                    self.validation_results['errors'].append(
                        f"{csv_file.name}: Missing required fields: {missing_fields}"
                    )
                    return False
                
                extra_fields = set(headers) - set(self.required_fields)
                if extra_fields:
                    self.validation_results['warnings'].append(
                        f"{csv_file.name}: Extra fields found: {extra_fields}"
                    )
                
                return True
                
        except Exception as e:
            self.validation_results['errors'].append(f"{csv_file.name}: Error reading file: {e}")
            return False
    
    def validate_package_data(self, package: Dict[str, str], file_name: str, row_num: int) -> bool:
        """Validate individual package data."""
        is_valid = True
        errors = []
        warnings = []
        
        # Check required fields are not empty
        for field in ['package', 'version']:
            if not package.get(field, '').strip():
                errors.append(f"Empty {field}")
                is_valid = False
        
        # Validate SHA hashes if present
        sha256 = package.get('sha256', '').strip()
        sha512 = package.get('sha512', '').strip()
        
        if sha256 and not self.sha_splitter.validate_sha256(sha256):
            errors.append(f"Invalid SHA256 format: {sha256}")
            is_valid = False
        
        if sha512 and not self.sha_splitter.validate_sha512(sha512):
            errors.append(f"Invalid SHA512 format: {sha512}")
            is_valid = False
        
        # Validate PURL format
        purl = package.get('purl', '').strip()
        if purl:
            if not purl.startswith('pkg:'):
                errors.append(f"Invalid PURL format: {purl}")
                is_valid = False
            else:
                try:
                    parsed = self.purl_generator.parse_purl(purl)
                    if not parsed.get('name') or not parsed.get('version'):
                        warnings.append(f"PURL missing name or version: {purl}")
                except Exception as e:
                    errors.append(f"PURL parsing error: {e}")
                    is_valid = False
        else:
            warnings.append("Empty PURL")
        
        # Validate URL format
        url = package.get('deb_url', '').strip()
        if url and not url.startswith(('http://', 'https://')):
            warnings.append(f"Suspicious URL format: {url}")
        
        # Validate architecture
        arch = package.get('architecture', '').strip()
        if arch and arch not in ['x86_64', 'amd64', 'aarch64', 'arm64', 'i386', 'i686', 'noarch', 'all', 'any']:
            warnings.append(f"Unusual architecture: {arch}")
        
        # Log errors and warnings
        for error in errors:
            self.validation_results['errors'].append(f"{file_name}:{row_num}: {error}")
        
        for warning in warnings:
            self.validation_results['warnings'].append(f"{file_name}:{row_num}: {warning}")
        
        return is_valid
    
    def validate_csv_file(self, csv_file: Path) -> Dict[str, int]:
        """Validate a single CSV file."""
        logger.info(f"Validating {csv_file.name}")
        
        file_stats = {
            'total_rows': 0,
            'valid_rows': 0,
            'invalid_rows': 0,
            'empty_rows': 0
        }
        
        if not self.validate_csv_structure(csv_file):
            return file_stats
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 because row 1 is headers
                    file_stats['total_rows'] += 1
                    
                    if not any(row.values()):
                        file_stats['empty_rows'] += 1
                        self.validation_results['warnings'].append(
                            f"{csv_file.name}:{row_num}: Empty row"
                        )
                        continue
                    
                    if self.validate_package_data(row, csv_file.name, row_num):
                        file_stats['valid_rows'] += 1
                    else:
                        file_stats['invalid_rows'] += 1
                        
        except Exception as e:
            self.validation_results['errors'].append(f"{csv_file.name}: Error processing file: {e}")
        
        return file_stats
    
    def validate_all_outputs(self):
        """Validate all CSV files in the output directory."""
        logger.info("Starting output validation")
        
        if not self.output_dir.exists():
            logger.error(f"Output directory not found: {self.output_dir}")
            return False
        
        csv_files = list(self.output_dir.glob("*.csv"))
        if not csv_files:
            logger.error("No CSV files found in output directory")
            return False
        
        self.validation_results['total_files'] = len(csv_files)
        
        for csv_file in csv_files:
            file_stats = self.validate_csv_file(csv_file)
            self.validation_results['file_stats'][csv_file.name] = file_stats
            self.validation_results['total_packages'] += file_stats['total_rows']
            self.validation_results['valid_packages'] += file_stats['valid_rows']
        
        return True
    
    def generate_validation_report(self):
        """Generate a validation report."""
        report_file = self.output_dir / "validation_report.txt"
        
        with open(report_file, 'w') as f:
            f.write("Linux Package Metadata Validation Report\n")
            f.write("========================================\n\n")
            
            f.write(f"Total CSV files: {self.validation_results['total_files']}\n")
            f.write(f"Total packages: {self.validation_results['total_packages']}\n")
            f.write(f"Valid packages: {self.validation_results['valid_packages']}\n")
            f.write(f"Invalid packages: {self.validation_results['total_packages'] - self.validation_results['valid_packages']}\n")
            
            if self.validation_results['total_packages'] > 0:
                validity_percentage = (self.validation_results['valid_packages'] / self.validation_results['total_packages']) * 100
                f.write(f"Validity percentage: {validity_percentage:.2f}%\n")
            
            f.write("\nFile Statistics:\n")
            f.write("-" * 50 + "\n")
            for file_name, stats in self.validation_results['file_stats'].items():
                f.write(f"{file_name}:\n")
                f.write(f"  Total rows: {stats['total_rows']}\n")
                f.write(f"  Valid rows: {stats['valid_rows']}\n")
                f.write(f"  Invalid rows: {stats['invalid_rows']}\n")
                f.write(f"  Empty rows: {stats['empty_rows']}\n")
                if stats['total_rows'] > 0:
                    validity = (stats['valid_rows'] / stats['total_rows']) * 100
                    f.write(f"  Validity: {validity:.2f}%\n")
                f.write("\n")
            
            if self.validation_results['errors']:
                f.write(f"\nErrors ({len(self.validation_results['errors'])}):\n")
                f.write("-" * 50 + "\n")
                for error in self.validation_results['errors'][:50]:  # Limit to first 50 errors
                    f.write(f"- {error}\n")
                if len(self.validation_results['errors']) > 50:
                    f.write(f"... and {len(self.validation_results['errors']) - 50} more errors\n")
            
            if self.validation_results['warnings']:
                f.write(f"\nWarnings ({len(self.validation_results['warnings'])}):\n")
                f.write("-" * 50 + "\n")
                for warning in self.validation_results['warnings'][:50]:  # Limit to first 50 warnings
                    f.write(f"- {warning}\n")
                if len(self.validation_results['warnings']) > 50:
                    f.write(f"... and {len(self.validation_results['warnings']) - 50} more warnings\n")
        
        logger.info(f"Validation report generated: {report_file}")
        return report_file
    
    def print_summary(self):
        """Print validation summary to console."""
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Total CSV files processed: {self.validation_results['total_files']}")
        print(f"Total packages validated: {self.validation_results['total_packages']}")
        print(f"Valid packages: {self.validation_results['valid_packages']}")
        print(f"Invalid packages: {self.validation_results['total_packages'] - self.validation_results['valid_packages']}")
        
        if self.validation_results['total_packages'] > 0:
            validity_percentage = (self.validation_results['valid_packages'] / self.validation_results['total_packages']) * 100
            print(f"Overall validity: {validity_percentage:.2f}%")
        
        print(f"Total errors: {len(self.validation_results['errors'])}")
        print(f"Total warnings: {len(self.validation_results['warnings'])}")
        
        if len(self.validation_results['errors']) > 0:
            print("\nSample errors:")
            for error in self.validation_results['errors'][:5]:
                print(f"  - {error}")
        
        print("=" * 60)

def main():
    validator = OutputValidator()
    
    if not validator.validate_all_outputs():
        logger.error("Validation failed")
        sys.exit(1)
    
    report_file = validator.generate_validation_report()
    validator.print_summary()
    
    error_count = len(validator.validation_results['errors'])
    if error_count > 0:
        logger.warning(f"Validation completed with {error_count} errors. See {report_file} for details.")
        sys.exit(1)
    else:
        logger.info("Validation completed successfully. All outputs are valid.")
        sys.exit(0)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3

import re
from typing import Optional, List, Dict

class LicenseDetector:
    """Detects and normalizes software licenses to SPDX identifiers."""
    
    def __init__(self):
        self.license_patterns = {
            'GPL-2.0': [
                r'GPL.*version\s*2',
                r'GNU.*General.*Public.*License.*version\s*2',
                r'GPL-2',
                r'GPLv2'
            ],
            'GPL-3.0': [
                r'GPL.*version\s*3',
                r'GNU.*General.*Public.*License.*version\s*3',
                r'GPL-3',
                r'GPLv3'
            ],
            'LGPL-2.1': [
                r'LGPL.*version\s*2\.1',
                r'GNU.*Lesser.*General.*Public.*License.*version\s*2\.1',
                r'LGPL-2\.1',
                r'LGPLv2\.1'
            ],
            'LGPL-3.0': [
                r'LGPL.*version\s*3',
                r'GNU.*Lesser.*General.*Public.*License.*version\s*3',
                r'LGPL-3',
                r'LGPLv3'
            ],
            'MIT': [
                r'\bMIT\b',
                r'MIT License',
                r'X11 License'
            ],
            'Apache-2.0': [
                r'Apache.*License.*version\s*2',
                r'Apache-2\.0',
                r'Apache\s*2'
            ],
            'BSD-3-Clause': [
                r'BSD.*3.*clause',
                r'BSD.*3-clause',
                r'New BSD License'
            ],
            'BSD-2-Clause': [
                r'BSD.*2.*clause',
                r'BSD.*2-clause',
                r'Simplified BSD License'
            ],
            'ISC': [
                r'\bISC\b',
                r'ISC License'
            ],
            'MPL-2.0': [
                r'Mozilla.*Public.*License.*2',
                r'MPL-2\.0',
                r'MPLv2'
            ],
            'CC0-1.0': [
                r'CC0',
                r'Creative Commons Zero',
                r'Public Domain'
            ],
            'Unlicense': [
                r'Unlicense',
                r'This is free and unencumbered software'
            ],
            'AGPL-3.0': [
                r'AGPL.*version\s*3',
                r'GNU.*Affero.*General.*Public.*License.*version\s*3',
                r'AGPL-3',
                r'AGPLv3'
            ]
        }
    
    def detect_license(self, text: str) -> Optional[str]:
        """
        Detect license from text and return SPDX identifier.
        
        Args:
            text: Text to analyze for license information
            
        Returns:
            SPDX license identifier or None if not detected
        """
        if not text:
            return None
            
        text_lower = text.lower()
        
        for spdx_id, patterns in self.license_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return spdx_id
        
        return None
    
    def guess_license_from_fields(self, package_fields: Dict[str, str]) -> Optional[str]:
        """
        Guess license from various package metadata fields.
        
        Args:
            package_fields: Dictionary containing package metadata
            
        Returns:
            SPDX license identifier or None if not detected
        """
        license_fields = [
            'license', 'licence', 'copyright', 'rights',
            'description', 'summary', 'homepage'
        ]
        
        for field in license_fields:
            if field in package_fields:
                detected = self.detect_license(package_fields[field])
                if detected:
                    return detected
        
        return None
    
    def extract_licenses_from_copyright(self, copyright_text: str) -> List[str]:
        """
        Extract multiple licenses from copyright text.
        
        Args:
            copyright_text: Copyright text to analyze
            
        Returns:
            List of SPDX license identifiers
        """
        licenses = []
        if not copyright_text:
            return licenses
            
        for spdx_id, patterns in self.license_patterns.items():
            for pattern in patterns:
                if re.search(pattern, copyright_text, re.IGNORECASE):
                    if spdx_id not in licenses:
                        licenses.append(spdx_id)
        
        return licenses
    
    def normalize_license_string(self, license_str: str) -> str:
        """
        Normalize a license string to standard format.
        
        Args:
            license_str: Raw license string
            
        Returns:
            Normalized license string or original if no match
        """
        if not license_str:
            return "Unknown"
            
        detected = self.detect_license(license_str)
        return detected if detected else license_str.strip()
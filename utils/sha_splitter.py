#!/usr/bin/env python3

import hashlib
import re
from typing import Tuple, Optional, Dict

class SHASplitter:
    """Utility to extract and validate SHA256 and SHA512 hashes from various sources."""
    
    def __init__(self):
        self.sha256_pattern = re.compile(r'\b[a-fA-F0-9]{64}\b')
        self.sha512_pattern = re.compile(r'\b[a-fA-F0-9]{128}\b')
    
    def extract_hashes(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract SHA256 and SHA512 hashes from text.
        
        Args:
            text: Text containing potential hash values
            
        Returns:
            Tuple of (sha256, sha512) or (None, None) if not found
        """
        if not text:
            return None, None
            
        sha256_matches = self.sha256_pattern.findall(text)
        sha512_matches = self.sha512_pattern.findall(text)
        
        sha256 = sha256_matches[0].lower() if sha256_matches else None
        sha512 = sha512_matches[0].lower() if sha512_matches else None
        
        return sha256, sha512
    
    def parse_hash_file(self, hash_content: str, filename: str = None) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
        """
        Parse hash file content (like SHA256SUMS or SHA512SUMS).
        
        Args:
            hash_content: Content of hash file
            filename: Optional specific filename to look for
            
        Returns:
            Dictionary mapping filenames to (sha256, sha512) tuples
        """
        results = {}
        
        for line in hash_content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            parts = line.split()
            if len(parts) >= 2:
                hash_value = parts[0].lower()
                file_path = ' '.join(parts[1:]).lstrip('*')
                
                if len(hash_value) == 64:
                    if file_path not in results:
                        results[file_path] = (None, None)
                    results[file_path] = (hash_value, results[file_path][1])
                elif len(hash_value) == 128:
                    if file_path not in results:
                        results[file_path] = (None, None)
                    results[file_path] = (results[file_path][0], hash_value)
        
        if filename:
            return {k: v for k, v in results.items() if filename in k}
        
        return results
    
    def validate_sha256(self, hash_value: str) -> bool:
        """
        Validate SHA256 hash format.
        
        Args:
            hash_value: Hash string to validate
            
        Returns:
            True if valid SHA256 format
        """
        if not hash_value:
            return False
        return bool(self.sha256_pattern.match(hash_value))
    
    def validate_sha512(self, hash_value: str) -> bool:
        """
        Validate SHA512 hash format.
        
        Args:
            hash_value: Hash string to validate
            
        Returns:
            True if valid SHA512 format
        """
        if not hash_value:
            return False
        return bool(self.sha512_pattern.match(hash_value))
    
    def compute_file_hashes(self, file_path: str) -> Tuple[str, str]:
        """
        Compute SHA256 and SHA512 hashes for a file.
        
        Args:
            file_path: Path to file to hash
            
        Returns:
            Tuple of (sha256, sha512) hashes
        """
        sha256_hash = hashlib.sha256()
        sha512_hash = hashlib.sha512()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
                sha512_hash.update(chunk)
        
        return sha256_hash.hexdigest(), sha512_hash.hexdigest()
    
    def extract_from_package_metadata(self, metadata: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract hashes from package metadata fields.
        
        Args:
            metadata: Package metadata dictionary
            
        Returns:
            Tuple of (sha256, sha512) or (None, None)
        """
        hash_fields = ['sha256', 'sha512', 'checksum', 'hash', 'digest']
        
        sha256 = None
        sha512 = None
        
        for field in hash_fields:
            if field in metadata:
                extracted_sha256, extracted_sha512 = self.extract_hashes(metadata[field])
                if extracted_sha256 and not sha256:
                    sha256 = extracted_sha256
                if extracted_sha512 and not sha512:
                    sha512 = extracted_sha512
        
        if not sha256 or not sha512:
            for key, value in metadata.items():
                if 'sha' in key.lower() or 'hash' in key.lower():
                    extracted_sha256, extracted_sha512 = self.extract_hashes(str(value))
                    if extracted_sha256 and not sha256:
                        sha256 = extracted_sha256
                    if extracted_sha512 and not sha512:
                        sha512 = extracted_sha512
        
        return sha256, sha512
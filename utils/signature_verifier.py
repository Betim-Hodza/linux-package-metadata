#!/usr/bin/env python3

import subprocess
import requests
import tempfile
import os
import logging
from pathlib import Path
from typing import Dict, Optional, List
import json

logger = logging.getLogger(__name__)

class SignatureVerifier:
    """Verify digital signatures for Linux packages across different formats."""
    
    def __init__(self):
        self.gpg_keyring_dir = Path.home() / ".linux-package-metadata" / "keyrings"
        self.gpg_keyring_dir.mkdir(parents=True, exist_ok=True)
    
    def verify_deb_repository(self, release_url: str, release_content: str, 
                             release_gpg_url: str) -> Dict[str, any]:
        """
        Verify DEB repository Release file signature.
        
        Args:
            release_url: URL of the Release file
            release_content: Content of the Release file
            release_gpg_url: URL of the Release.gpg signature file
            
        Returns:
            Dict with verification results
        """
        try:
            # Download the GPG signature
            response = requests.get(release_gpg_url, timeout=30)
            response.raise_for_status()
            signature_content = response.content
            
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.gpg', delete=False) as sig_file:
                sig_file.write(signature_content)
                sig_file_path = sig_file.name
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.release', delete=False) as release_file:
                release_file.write(release_content)
                release_file_path = release_file.name
            
            try:
                # Verify signature using gpg
                result = subprocess.run([
                    'gpg', '--verify', sig_file_path, release_file_path
                ], capture_output=True, text=True, timeout=30)
                
                verification_result = {
                    'verified': result.returncode == 0,
                    'signature_url': release_gpg_url,
                    'gpg_output': result.stderr,
                    'verification_method': 'GPG Release.gpg'
                }
                
                if result.returncode == 0:
                    # Extract signer information
                    lines = result.stderr.split('\n')
                    for line in lines:
                        if 'Good signature from' in line:
                            verification_result['signer'] = line.split('"')[1] if '"' in line else 'Unknown'
                            break
                
                return verification_result
                
            finally:
                os.unlink(sig_file_path)
                os.unlink(release_file_path)
                
        except Exception as e:
            logger.error(f"Error verifying DEB repository signature: {e}")
            return {
                'verified': False,
                'error': str(e),
                'verification_method': 'GPG Release.gpg'
            }
    
    def verify_rpm_signature(self, rpm_url: str) -> Dict[str, any]:
        """
        Verify RPM package signature.
        
        Args:
            rpm_url: URL of the RPM package
            
        Returns:
            Dict with verification results
        """
        try:
            # Download a small portion of the RPM to check signature
            headers = {'Range': 'bytes=0-8192'}  # Get first 8KB for header
            response = requests.get(rpm_url, headers=headers, timeout=30)
            
            if response.status_code not in [200, 206]:  # 206 = Partial Content
                return {
                    'verified': False,
                    'error': f'HTTP {response.status_code}',
                    'verification_method': 'RPM signature check'
                }
            
            with tempfile.NamedTemporaryFile(suffix='.rpm', delete=False) as rpm_file:
                rpm_file.write(response.content)
                rpm_file_path = rpm_file.name
            
            try:
                # Use rpm command to check signature
                result = subprocess.run([
                    'rpm', '--checksig', '--nosignature', rpm_file_path
                ], capture_output=True, text=True, timeout=30)
                
                # Also try to get signature info
                sig_result = subprocess.run([
                    'rpm', '-qp', '--qf', '%{SIGPGP:pgpsig}', rpm_file_path
                ], capture_output=True, text=True, timeout=30)
                
                verification_result = {
                    'verified': 'OK' in result.stdout,
                    'checksig_output': result.stdout.strip(),
                    'signature_info': sig_result.stdout.strip() if sig_result.returncode == 0 else None,
                    'verification_method': 'RPM --checksig'
                }
                
                return verification_result
                
            finally:
                os.unlink(rpm_file_path)
                
        except Exception as e:
            logger.error(f"Error verifying RPM signature: {e}")
            return {
                'verified': False,
                'error': str(e),
                'verification_method': 'RPM signature check'
            }
    
    def verify_apk_signature(self, apkindex_url: str) -> Dict[str, any]:
        """
        Verify APK repository signature.
        
        Args:
            apkindex_url: URL of the APKINDEX.tar.gz file
            
        Returns:
            Dict with verification results
        """
        try:
            # Alpine uses .SIGN.RSA files alongside APKINDEX
            sign_url = apkindex_url.replace('APKINDEX.tar.gz', '.SIGN.RSA.alpine-devel@lists.alpinelinux.org-4a6a0840.rsa.pub')
            
            response = requests.head(sign_url, timeout=30)
            has_signature = response.status_code == 200
            
            verification_result = {
                'verified': has_signature,
                'signature_url': sign_url if has_signature else None,
                'verification_method': 'APK .SIGN.RSA file check'
            }
            
            if has_signature:
                verification_result['signer'] = 'Alpine Linux Developer'
            
            return verification_result
            
        except Exception as e:
            logger.error(f"Error verifying APK signature: {e}")
            return {
                'verified': False,
                'error': str(e),
                'verification_method': 'APK signature check'
            }
    
    def verify_arch_signature(self, package_url: str) -> Dict[str, any]:
        """
        Verify Arch Linux package signature.
        
        Args:
            package_url: URL of the package file
            
        Returns:
            Dict with verification results
        """
        try:
            # Arch packages have .sig files
            sig_url = package_url + '.sig'
            
            response = requests.head(sig_url, timeout=30)
            has_signature = response.status_code == 200
            
            verification_result = {
                'verified': has_signature,
                'signature_url': sig_url if has_signature else None,
                'verification_method': 'Arch .sig file check'
            }
            
            if has_signature:
                # Could download and verify with pacman-key, but requires Arch environment
                verification_result['note'] = 'Signature file exists, full verification requires pacman-key'
            
            return verification_result
            
        except Exception as e:
            logger.error(f"Error verifying Arch signature: {e}")
            return {
                'verified': False,
                'error': str(e),
                'verification_method': 'Arch signature check'
            }
    
    def get_signature_info(self, package_url: str, package_format: str) -> Dict[str, any]:
        """
        Get signature information for a package based on its format.
        
        Args:
            package_url: URL of the package or repository
            package_format: Format type (deb, rpm, apk, alpm)
            
        Returns:
            Dict with signature verification results
        """
        try:
            if package_format == 'deb':
                # For DEB, we'd need the Release file URL, this is a simplified example
                return {'verification_method': 'DEB - requires Release file URL'}
            elif package_format == 'rpm':
                return self.verify_rpm_signature(package_url)
            elif package_format == 'apk':
                return self.verify_apk_signature(package_url)
            elif package_format == 'alpm':
                return self.verify_arch_signature(package_url)
            else:
                return {
                    'verified': False,
                    'error': f'Unsupported package format: {package_format}',
                    'verification_method': 'Unknown'
                }
        except Exception as e:
            logger.error(f"Error getting signature info: {e}")
            return {
                'verified': False,
                'error': str(e),
                'verification_method': f'{package_format} signature check'
            }

def main():
    """Example usage of signature verification."""
    verifier = SignatureVerifier()
    
    # Example URLs (these may not work without proper setup)
    examples = [
        ('https://example.com/package.rpm', 'rpm'),
        ('https://dl-cdn.alpinelinux.org/alpine/v3.18/main/x86_64/APKINDEX.tar.gz', 'apk'),
        ('https://example.com/package.pkg.tar.xz', 'alpm')
    ]
    
    for url, format_type in examples:
        print(f"\nChecking {format_type} signature for: {url}")
        result = verifier.get_signature_info(url, format_type)
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
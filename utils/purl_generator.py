#!/usr/bin/env python3

from typing import Optional, Dict
import urllib.parse

class PURLGenerator:
    """Generates Package URLs (PURLs) according to the specification."""
    
    def __init__(self):
        self.type_mappings = {
            'ubuntu': 'deb',
            'debian': 'deb',
            'centos': 'rpm',
            'rocky': 'rpm',
            'fedora': 'rpm',
            'rhel': 'rpm',
            'amazonlinux': 'rpm',
            'alpine': 'apk',
            'arch': 'alpm'
        }
    
    def generate_purl(self, 
                     package_type: str,
                     name: str,
                     version: str,
                     namespace: Optional[str] = None,
                     qualifiers: Optional[Dict[str, str]] = None,
                     subpath: Optional[str] = None) -> str:
        """
        Generate a Package URL (PURL) according to the specification.
        
        Args:
            package_type: Type of package (deb, rpm, apk, etc.)
            name: Package name
            version: Package version
            namespace: Optional namespace (e.g., distribution)
            qualifiers: Optional key-value pairs for additional metadata
            subpath: Optional subpath within the package
            
        Returns:
            PURL string in format: pkg:<type>/<namespace>/<name>@<version>
        """
        if not package_type or not name or not version:
            raise ValueError("package_type, name, and version are required")
        
        purl_parts = ['pkg:', package_type.lower()]
        
        if namespace:
            purl_parts.extend(['/', namespace.lower()])
        
        purl_parts.extend(['/', name.lower(), '@', version])
        
        if qualifiers:
            qualifier_strings = []
            for key, value in sorted(qualifiers.items()):
                encoded_value = urllib.parse.quote(str(value), safe='')
                qualifier_strings.append(f"{key}={encoded_value}")
            if qualifier_strings:
                purl_parts.extend(['?', '&'.join(qualifier_strings)])
        
        if subpath:
            encoded_subpath = urllib.parse.quote(subpath, safe='/')
            purl_parts.extend(['#', encoded_subpath])
        
        return ''.join(purl_parts)
    
    def generate_deb_purl(self, 
                         name: str, 
                         version: str, 
                         distribution: str,
                         component: Optional[str] = None,
                         architecture: Optional[str] = None) -> str:
        """
        Generate PURL for Debian/Ubuntu packages.
        
        Args:
            name: Package name
            version: Package version
            distribution: Distribution name (ubuntu, debian)
            component: Component name (main, universe, etc.)
            architecture: Package architecture
            
        Returns:
            PURL string for Debian package
        """
        qualifiers = {}
        
        if component:
            qualifiers['component'] = component
        if architecture:
            qualifiers['arch'] = architecture
            
        return self.generate_purl(
            package_type='deb',
            name=name,
            version=version,
            namespace=distribution.lower(),
            qualifiers=qualifiers if qualifiers else None
        )
    
    def generate_rpm_purl(self,
                         name: str,
                         version: str,
                         distribution: str,
                         release: Optional[str] = None,
                         architecture: Optional[str] = None,
                         epoch: Optional[str] = None) -> str:
        """
        Generate PURL for RPM packages.
        
        Args:
            name: Package name
            version: Package version
            distribution: Distribution name (centos, fedora, etc.)
            release: Release string
            architecture: Package architecture
            epoch: Package epoch
            
        Returns:
            PURL string for RPM package
        """
        qualifiers = {}
        
        if release:
            qualifiers['release'] = release
        if architecture:
            qualifiers['arch'] = architecture
        if epoch:
            qualifiers['epoch'] = epoch
            
        return self.generate_purl(
            package_type='rpm',
            name=name,
            version=version,
            namespace=distribution.lower(),
            qualifiers=qualifiers if qualifiers else None
        )
    
    def generate_apk_purl(self,
                         name: str,
                         version: str,
                         repository: Optional[str] = None,
                         architecture: Optional[str] = None) -> str:
        """
        Generate PURL for Alpine APK packages.
        
        Args:
            name: Package name
            version: Package version
            repository: Repository name
            architecture: Package architecture
            
        Returns:
            PURL string for APK package
        """
        qualifiers = {}
        
        if repository:
            qualifiers['repository'] = repository
        if architecture:
            qualifiers['arch'] = architecture
            
        return self.generate_purl(
            package_type='apk',
            name=name,
            version=version,
            namespace='alpine',
            qualifiers=qualifiers if qualifiers else None
        )
    
    def generate_arch_purl(self,
                          name: str,
                          version: str,
                          repository: Optional[str] = None,
                          architecture: Optional[str] = None) -> str:
        """
        Generate PURL for Arch Linux packages.
        
        Args:
            name: Package name
            version: Package version
            repository: Repository name (core, extra, community, etc.)
            architecture: Package architecture
            
        Returns:
            PURL string for Arch package
        """
        qualifiers = {}
        
        if repository:
            qualifiers['repository'] = repository
        if architecture:
            qualifiers['arch'] = architecture
            
        return self.generate_purl(
            package_type='alpm',
            name=name,
            version=version,
            namespace='arch',
            qualifiers=qualifiers if qualifiers else None
        )
    
    def parse_purl(self, purl: str) -> Dict[str, Optional[str]]:
        """
        Parse a PURL string into its components.
        
        Args:
            purl: PURL string to parse
            
        Returns:
            Dictionary with PURL components
        """
        if not purl.startswith('pkg:'):
            raise ValueError("Invalid PURL: must start with 'pkg:'")
        
        purl = purl[4:]  # Remove 'pkg:' prefix
        
        # Split on '#' for subpath
        if '#' in purl:
            purl, subpath = purl.split('#', 1)
            subpath = urllib.parse.unquote(subpath)
        else:
            subpath = None
        
        # Split on '?' for qualifiers
        if '?' in purl:
            purl, qualifier_string = purl.split('?', 1)
            qualifiers = {}
            for pair in qualifier_string.split('&'):
                key, value = pair.split('=', 1)
                qualifiers[key] = urllib.parse.unquote(value)
        else:
            qualifiers = None
        
        # Split on '@' for version
        if '@' in purl:
            path_part, version = purl.rsplit('@', 1)
        else:
            raise ValueError("Invalid PURL: missing version")
        
        # Parse type and namespace/name
        parts = path_part.split('/')
        package_type = parts[0]
        
        if len(parts) == 2:
            namespace = None
            name = parts[1]
        elif len(parts) == 3:
            namespace = parts[1]
            name = parts[2]
        else:
            raise ValueError("Invalid PURL: incorrect path structure")
        
        return {
            'type': package_type,
            'namespace': namespace,
            'name': name,
            'version': version,
            'qualifiers': qualifiers,
            'subpath': subpath
        }
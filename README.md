# Linux Package Metadata Extractor

A comprehensive tool for extracting and aggregating Linux package metadata from multiple distributions. This system generates consistent CSV output for each supported distribution and architecture, including key metadata fields like package names, versions, checksums, licenses, and Package URLs (PURLs).

## Supported Distributions

- **Ubuntu** (22.04–latest, all components)
- **Debian** (last 4 stable releases: bullseye, bookworm, trixie, sid)
- **CentOS** (7, 8, 9)
- **Rocky Linux** (8, 9, 10)
- **Fedora** (last 4 versions: 38, 39, 40, 41)
- **Amazon Linux** (2 and 2023)
- **Alpine Linux** (last 3 stable releases: 3.18, 3.19, 3.20)
- **Arch Linux** (rolling release)

## Architecture Support

- **amd64/x86_64** - Intel/AMD 64-bit
- **aarch64/arm64** - ARM 64-bit

## Prerequisites

- **Python 3.10+** with pip and tkinter (for GUI)
- **bash** shell environment
- **curl** or **wget** for downloads
- Internet connection for downloading package metadata

### Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

**Note**: The GUI requires tkinter, which is included with most Python installations. If tkinter is not available, you can still use the command-line interface.

## Project Structure

```
linux-package-metadata/
├── ubuntu/
│   ├── download_ubuntu_packages.sh
│   └── parse_ubuntu_packages.py
├── debian/
│   ├── download_debian_packages.sh
│   └── parse_debian_packages.py
├── centos/
│   ├── download_centos_packages.sh
│   └── parse_centos_packages.py
├── rocky/
│   ├── download_rocky_packages.sh
│   └── parse_rocky_packages.py
├── fedora/
│   └── parse_fedora_packages.py
├── alpine/
│   └── parse_alpine_packages.py
├── arch/
│   └── parse_arch_packages.py
├── amazonlinux/
│   └── parse_amazon_packages.py
├── utils/
│   ├── license_detector.py
│   ├── sha_splitter.py
│   ├── purl_generator.py
│   └── __init__.py
├── scripts/
│   ├── run_all.sh
│   └── validate_outputs.py
├── gui_menu.py          # GUI interface for distribution selection
├── hash_distro_files.sh # Get specific distro package's individual file hash for each file in the package
├── requirements.txt
├── .gitignore
└── README.md
```

## Quick Start

### GUI Interface (Recommended)

For the easiest experience, use the graphical interface:

```bash
python3 gui_menu.py
```

**Features:**
- ✅ **Visual distribution selection** with checkboxes
- 📊 **Real-time progress monitoring** with live output streaming
- ⏱️ **Estimated processing times** and package counts for each distribution
- 🎮 **Start/Stop controls** for managing extractions
- 📋 **Distribution information** showing package counts and processing time
- 🔐 **Automatic signature verification** for all packages (enabled by default)

**Usage:**
1. Select desired Linux distributions using checkboxes
2. Click "Start Extraction" to begin processing
3. Monitor real-time progress in the log area
4. Use "Stop All" to halt processing if needed
5. Results are saved to `output/` directory as CSV files with signature verification data

### hash_distro_files

Take in a distro as an argumnent, grabs all the PURLs (package urls) from a distro mirror. 
Saves those to a urls.csv with a state of complete / not complete (1 or 0). Then for each
package in urls.csv, downloads the package with wget, saves it and unpacks it in a temp dir,
then hashes the full package and each individual file within that to packages.csv and files.csv.

This is an extremly CPU intensive task and takes up gigabytes of storage. Its meant to be a 1shot script
and not to be run often unless things go catastrophically wrong lol.

Future plans is to run this and then host it on a website when we have a server.

#### Dependencies
* zstd 
* debian package manager (dpkg)
* redhat package manager (rpm)


#### Dependencies


### Command Line Interface

#### Run All Distributions

```bash
# Make the main script executable
chmod +x scripts/run_all.sh

# Extract metadata from all supported distributions
./scripts/run_all.sh
```

This will:
1. Download package index files for distributions that require it
2. Parse metadata from all distributions in parallel
3. Generate individual CSV files for each distribution
4. Create a combined CSV with all packages
5. Generate an extraction summary

#### Run Individual Distributions

```bash
# Ubuntu (~275K packages, 2-3 minutes)
python3 ubuntu/parse_ubuntu_packages.py

# Debian (~532K packages, 3-5 minutes)
python3 debian/parse_debian_packages.py

# CentOS (~55K packages, 8-12 minutes - includes download)
bash centos/download_centos_packages.sh
python3 centos/parse_centos_packages.py

# Rocky Linux (~31K packages, 6-10 minutes - includes download)
bash rocky/download_rocky_packages.sh
python3 rocky/parse_rocky_packages.py

# Fedora (~209K packages, 5-8 minutes)
python3 fedora/parse_fedora_packages.py

# Alpine Linux (~134K packages, 1-2 minutes)
python3 alpine/parse_alpine_packages.py

# Arch Linux (~28K packages, 1-2 minutes)
python3 arch/parse_arch_packages.py

# Amazon Linux (~120K packages, 4-6 minutes)
python3 amazonlinux/parse_amazon_packages.py
```

### Validate Outputs

```bash
# Validate all generated CSV files
./scripts/validate_outputs.py
```

## Output Format

All CSV files follow the same format with **signature verification columns**:

```csv
package,version,sha256,sha512,component,architecture,deb_url,license,purl,release,signature_verified,signature_method,signer
```

### Field Descriptions

- **package**: Package name
- **version**: Package version (including epoch and release for RPM packages)
- **sha256**: SHA256 checksum (when available)
- **sha512**: SHA512 checksum (when available)
- **component**: Repository component/section (e.g., main, universe, core, etc.)
- **architecture**: Target architecture (amd64, x86_64, aarch64, etc.)
- **deb_url**: Download URL for the package file
- **license**: License information (normalized to SPDX identifiers when possible)
- **purl**: Package URL following the PURL specification
- **release**: Distribution release (e.g., jammy, bullseye, el8, fc39, etc.)
- **signature_verified**: Digital signature verification status (`true`/`false`/`disabled`/`error`)
- **signature_method**: Type of signature verification performed (e.g., `InRelease GPG signature`, `RPM GPG signature`)
- **signer**: Entity that signed the package/repository (e.g., `Ubuntu Archive Automatic Signing Key`)

### Example Output

```csv
package,version,sha256,sha512,component,architecture,deb_url,license,purl,release,signature_verified,signature_method,signer
bash,5.1-6ubuntu1,a1b2c3...,d4e5f6...,main,amd64,http://archive.ubuntu.com/ubuntu/pool/main/b/bash/bash_5.1-6ubuntu1_amd64.deb,GPL-3.0,pkg:deb/ubuntu/bash@5.1-6ubuntu1?arch=amd64&component=main,jammy,true,InRelease GPG signature,Ubuntu Archive Automatic Signing Key
```

## Output Locations

- **Individual distribution outputs**: `output/{distribution}/{distribution}_packages.csv`
- **Final consolidated outputs**: `final_output/`
  - Individual distribution CSVs
  - `all_packages.csv` - Combined dataset
  - `extraction_summary.txt` - Summary statistics
  - `validation_report.txt` - Validation results (if validation is run)

## Features

### License Detection
- Automatic license detection from package metadata
- Normalization to SPDX identifiers when possible
- Support for common licenses (GPL, MIT, Apache, BSD, etc.)

### Hash Validation
- SHA256 and SHA512 checksum extraction and validation
- Support for multiple hash formats and sources

### PURL Generation
- Automatic generation of Package URLs following the PURL specification
- Support for different package types (deb, rpm, apk, alpm)
- Proper namespace and qualifier handling

### Digital Signature Verification
- **Repository-level verification** for DEB/APK packages (InRelease files, .SIGN.RSA files)
- **Package-level verification** for RPM/Arch packages (embedded GPG signatures, .sig files)
- **Signature status tracking**: `true`/`false`/`disabled`/`error` in CSV output
- **Verification method identification**: InRelease GPG, RPM GPG, APK RSA, Arch .sig signatures
- **Signer identification**: Distribution signing keys and authorities
- **Performance optimized**: Repository-level signatures cached to avoid repeated verification
- **Configurable**: Can be enabled/disabled per parser for faster processing

#### Signature Support by Distribution
| Distribution | Signature Method | Verification Type | Signer |
|--------------|------------------|-------------------|---------|
| **Ubuntu** | InRelease GPG signature | Repository-level | Ubuntu Archive Automatic Signing Key |
| **Debian** | InRelease GPG signature | Repository-level | Debian Archive Automatic Signing Key |
| **Fedora** | RPM GPG signature | Package-level | Fedora Project |
| **CentOS** | RPM GPG signature | Package-level | CentOS Project |
| **Rocky Linux** | RPM GPG signature | Package-level | Rocky Linux |
| **Amazon Linux** | RPM GPG signature | Package-level | Amazon Linux |
| **Alpine Linux** | APK .SIGN.RSA signature | Repository-level | Alpine Linux Developer |
| **Arch Linux** | Arch .sig file signature | Package-level | Arch Linux Developer |

### Parallel Processing
- Downloads and processing run in parallel for faster execution
- Configurable concurrency limits to avoid overwhelming servers

### Error Handling
- Comprehensive error logging and reporting
- Graceful handling of network failures and malformed data
- Validation of output data integrity

## Configuration

### Environment Variables

- `CLEANUP_TEMP=false` - Disable temporary file cleanup (default: true)

### Signature Verification Configuration

**Signature verification is enabled by default** for enhanced security. To disable it:

#### Method 1: Modify Parser Initialization
```python
# In any parse_*_packages.py file
def main():
    parser = UbuntuPackageParser(verify_signatures=False)  # Disable signatures
    parser.process_all_packages()
```

#### Method 2: Environment Variable (Future Enhancement)
```bash
export VERIFY_SIGNATURES=false
python3 ubuntu/parse_ubuntu_packages.py
```

**Performance Impact:**
- **Enabled**: ~10-20% slower processing (due to signature verification)
- **Disabled**: Faster processing, but reduced security assurance

**When Disabled:**
- `signature_verified: disabled`
- `signature_method: signature verification disabled`
- `signer: N/A`

### Customization

You can modify the following in individual scripts:

- **Releases**: Update release lists in download scripts
- **Components**: Modify component lists for different repository sections
- **Architectures**: Add or remove target architectures
- **Concurrency**: Adjust parallel job limits in download scripts
- **Signature Verification**: Enable/disable per parser as needed

## Troubleshooting

### Common Issues

1. **Network timeouts**: Some repositories may be slow. The scripts include retry logic and reasonable timeouts.

2. **Missing dependencies**: Install required Python packages:
   ```bash
   pip3 install requests lxml
   ```

3. **Permission errors**: Make sure all scripts are executable:
   ```bash
   find . -name "*.sh" -exec chmod +x {} \;
   find . -name "*.py" -exec chmod +x {} \;
   ```

4. **Disk space**: Package metadata can be large. Ensure sufficient disk space (recommended: 10GB+).

### Debugging

Enable verbose logging by setting the log level:

```bash
export PYTHONPATH=.
PYTHON_LOG_LEVEL=DEBUG ./scripts/run_all.sh
```

### Performance Tuning

- Adjust parallel job limits in scripts if you experience network issues
- Use SSD storage for better I/O performance during processing
- Increase available RAM for processing large datasets

## Technical Details

### Package Format Support

- **DEB packages**: Parses Packages.gz files from APT repositories
- **RPM packages**: Parses primary.xml.gz files from YUM/DNF repositories
- **APK packages**: Parses APKINDEX.tar.gz files from Alpine repositories
- **ALPM packages**: Parses .db.tar.gz files from Pacman repositories

### Data Processing Pipeline

1. **Download Phase**: Retrieve package index files from distribution mirrors
2. **Parse Phase**: Extract structured data from various package formats
3. **Normalize Phase**: Convert to unified CSV format with consistent fields
4. **Validate Phase**: Check data integrity and format compliance
5. **Aggregate Phase**: Combine all distributions into unified datasets

### Security Considerations

- All downloads use HTTPS where available
- **Digital signature verification** for package authenticity and integrity
- Package checksums are validated when present (SHA256/SHA512)
- **Multi-layer verification**: Signatures + checksums provide comprehensive validation
- No code execution from downloaded content
- Comprehensive input validation and sanitization
- **Supply chain security**: Verifies packages are from legitimate distribution sources

## Contributing

To add support for additional distributions:

1. Create a directory for the new distribution
2. Implement download script (if needed) and parser script
3. Follow the existing patterns for metadata extraction
4. Update the main orchestration script
5. Add appropriate test cases

## License

This project is licensed under the Apache 2.0 License. See individual package licenses in the generated CSV files.

## Support

For issues, questions, or contributions, please refer to the project documentation or create an issue in the project repository.
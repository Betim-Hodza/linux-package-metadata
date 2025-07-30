#!/usr/bin/env python3
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import os
import sys
from pathlib import Path
import time
import webbrowser

class LinuxPackageExtractorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Linux Package Metadata Extractor")
        self.root.geometry("800x600")
        
        # Dictionary of distributions with their commands and descriptions
        self.distributions = {
            "Ubuntu": {
                "command": ["python3", "ubuntu/parse_ubuntu_packages.py"],
                "description": "Extract Ubuntu package metadata (DEB format)",
                "estimated_time": "2-3 minutes",
                "packages": "~275K packages"
            },
            "Debian": {
                "command": ["python3", "debian/parse_debian_packages.py"],
                "description": "Extract Debian package metadata (DEB format)",
                "estimated_time": "3-5 minutes",
                "packages": "~532K packages"
            },
            "Arch Linux": {
                "command": ["python3", "arch/parse_arch_packages.py"],
                "description": "Extract Arch Linux package metadata (ALPM format)",
                "estimated_time": "1-2 minutes",
                "packages": "~28K packages"
            },
            "Fedora": {
                "command": ["python3", "fedora/parse_fedora_packages.py"],
                "description": "Extract Fedora package metadata (RPM format)",
                "estimated_time": "5-8 minutes",
                "packages": "~209K packages"
            },
            "CentOS": {
                "command": ["bash", "centos/download_centos_packages.sh", "&&", "python3", "centos/parse_centos_packages.py"],
                "description": "Extract CentOS package metadata (RPM format, requires download)",
                "estimated_time": "8-12 minutes",
                "packages": "~55K packages"
            },
            "Rocky Linux": {
                "command": ["bash", "rocky/download_rocky_packages.sh", "&&", "python3", "rocky/parse_rocky_packages.py"],
                "description": "Extract Rocky Linux package metadata (RPM format, requires download)",
                "estimated_time": "6-10 minutes",
                "packages": "~31K packages"
            },
            "Amazon Linux": {
                "command": ["python3", "amazonlinux/parse_amazon_packages.py"],
                "description": "Extract Amazon Linux package metadata (RPM format)",
                "estimated_time": "4-6 minutes",
                "packages": "~120K packages"
            },
            "Alpine Linux": {
                "command": ["python3", "alpine/parse_alpine_packages.py"],
                "description": "Extract Alpine Linux package metadata (APK format)",
                "estimated_time": "1-2 minutes",
                "packages": "~134K packages"
            }
        }
        
        self.selected_distros = {}
        self.running_processes = {}
        
        self.create_widgets()
        
        # Schedule periodic GUI updates for responsiveness
        self.schedule_gui_update()
        
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="Linux Package Metadata Extractor", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Instructions
        instructions = ttk.Label(main_frame, 
                                text="Select Linux distributions to extract package metadata from:",
                                font=("Arial", 10))
        instructions.grid(row=1, column=0, columnspan=2, pady=(0, 10))
        
        # Checkbox frame
        checkbox_frame = ttk.LabelFrame(main_frame, text="Available Distributions", padding="10")
        checkbox_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Create checkboxes for each distribution
        for i, (distro, info) in enumerate(self.distributions.items()):
            var = tk.BooleanVar()
            self.selected_distros[distro] = var
            
            cb = ttk.Checkbutton(checkbox_frame, text=distro, variable=var)
            cb.grid(row=i, column=0, sticky=tk.W, padx=(0, 20))
            
            # Description label
            desc_text = f"{info['description']}\n{info['packages']} | Est. time: {info['estimated_time']}"
            desc_label = ttk.Label(checkbox_frame, text=desc_text, 
                                  font=("Arial", 8), foreground="gray")
            desc_label.grid(row=i, column=1, sticky=tk.W)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        # Select All button
        select_all_btn = ttk.Button(button_frame, text="Select All", command=self.safe_select_all)
        select_all_btn.grid(row=0, column=0, padx=5)
        
        # Clear All button
        clear_all_btn = ttk.Button(button_frame, text="Clear All", command=self.safe_clear_all)
        clear_all_btn.grid(row=0, column=1, padx=5)
        
        # Start Extraction button
        self.start_btn = ttk.Button(button_frame, text="Start Extraction", 
                                   command=self.safe_start_extraction, style="Accent.TButton")
        self.start_btn.grid(row=0, column=2, padx=5)
        
        # Stop button
        self.stop_btn = ttk.Button(button_frame, text="Stop All", 
                                  command=self.safe_stop_extraction, state="disabled")
        self.stop_btn.grid(row=0, column=3, padx=5)
        
        # Help button
        help_btn = ttk.Button(button_frame, text="Help", command=self.safe_show_help)
        help_btn.grid(row=0, column=4, padx=5)
        
        # Advanced Tools button
        tools_btn = ttk.Button(button_frame, text="Advanced Tools", command=self.safe_show_advanced_tools)
        tools_btn.grid(row=0, column=5, padx=5)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(main_frame, text="Extraction Progress", padding="10")
        progress_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Progress text area
        self.progress_text = scrolledtext.ScrolledText(progress_frame, height=15, width=80)
        self.progress_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.rowconfigure(0, weight=1)
    
    def select_all(self):
        for var in self.selected_distros.values():
            var.set(True)
    
    def clear_all(self):
        for var in self.selected_distros.values():
            var.set(False)
    
    def log_message(self, message):
        """Add a message to the progress text area."""
        def update_log():
            timestamp = time.strftime("%H:%M:%S")
            self.progress_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.progress_text.see(tk.END)
            self.root.update_idletasks()
        
        # Ensure thread-safe GUI updates
        if threading.current_thread() == threading.main_thread():
            update_log()
        else:
            self.root.after(0, update_log)
    
    def start_extraction(self):
        selected = [distro for distro, var in self.selected_distros.items() if var.get()]
        
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one distribution.")
            return
        
        # Disable start button, enable stop button
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        
        # Clear progress text
        self.progress_text.delete(1.0, tk.END)
        
        self.log_message(f"Starting extraction for: {', '.join(selected)}")
        self.safe_update_status(f"Extracting {len(selected)} distributions...")
        
        # Start extraction in separate thread
        self.extraction_thread = threading.Thread(target=self.run_extractions, args=(selected,))
        self.extraction_thread.daemon = True
        self.extraction_thread.start()
    
    def run_extractions(self, selected_distros):
        """Run the extraction commands for selected distributions."""
        try:
            for distro in selected_distros:
                if distro not in self.running_processes:  # Check if not stopped
                    self.log_message(f"Starting {distro} extraction...")
                    
                    # Handle complex commands (CentOS and Rocky Linux)
                    if distro in ["CentOS", "Rocky Linux"]:
                        # Run download script first
                        if distro == "CentOS":
                            download_cmd = ["bash", "centos/download_centos_packages.sh"]
                            parse_cmd = ["python3", "centos/parse_centos_packages.py"]
                        else:  # Rocky Linux
                            download_cmd = ["bash", "rocky/download_rocky_packages.sh"]
                            parse_cmd = ["python3", "rocky/parse_rocky_packages.py"]
                        
                        # Run download
                        self.log_message(f"Downloading {distro} repository data...")
                        download_process = subprocess.Popen(download_cmd, 
                                                          stdout=subprocess.PIPE, 
                                                          stderr=subprocess.STDOUT,
                                                          universal_newlines=True)
                        
                        # Stream download output
                        for line in download_process.stdout:
                            if distro in self.running_processes:  # Check if stopped
                                break
                            self.log_message(f"[{distro} Download] {line.strip()}")
                        
                        download_process.wait()
                        
                        if download_process.returncode != 0:
                            self.log_message(f"ERROR: {distro} download failed!")
                            continue
                        
                        # Run parser
                        self.log_message(f"Parsing {distro} packages...")
                        cmd = parse_cmd
                    else:
                        cmd = self.distributions[distro]["command"]
                    
                    # Run the extraction command
                    process = subprocess.Popen(cmd, 
                                             stdout=subprocess.PIPE, 
                                             stderr=subprocess.STDOUT,
                                             universal_newlines=True)
                    
                    self.running_processes[distro] = process
                    
                    # Stream output
                    for line in process.stdout:
                        if distro not in self.running_processes:  # Check if stopped
                            break
                        self.log_message(f"[{distro}] {line.strip()}")
                    
                    process.wait()
                    
                    if distro in self.running_processes:
                        del self.running_processes[distro]
                        
                        if process.returncode == 0:
                            self.log_message(f"✅ {distro} extraction completed successfully!")
                        else:
                            self.log_message(f"❌ {distro} extraction failed with code {process.returncode}")
            
            # All done
            if not self.running_processes:  # Only if not stopped
                self.log_message("🎉 All selected extractions completed!")
                self.safe_update_status("Completed")
            
        except Exception as e:
            self.log_message(f"ERROR: {str(e)}")
        finally:
            # Re-enable buttons
            self.root.after(0, self.extraction_finished)
    
    def stop_extraction(self):
        """Stop all running processes."""
        self.log_message("Stopping all extractions...")
        
        for distro, process in list(self.running_processes.items()):
            try:
                process.terminate()
                self.log_message(f"Stopped {distro} extraction")
            except:
                pass
        
        self.running_processes.clear()
        self.safe_update_status("Stopped")
        self.extraction_finished()
    
    def extraction_finished(self):
        """Re-enable buttons after extraction is finished."""
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
    
    def schedule_gui_update(self):
        """Schedule periodic GUI updates to maintain responsiveness."""
        try:
            self.root.update_idletasks()
        except tk.TclError:
            # Window might be destroyed
            return
        
        # Schedule next update in 100ms
        self.root.after(100, self.schedule_gui_update)
    
    def safe_show_help(self):
        """Thread-safe wrapper for showing help."""
        self.root.update_idletasks()
        self.root.after_idle(self.show_help)
    
    def safe_show_advanced_tools(self):
        """Thread-safe wrapper for showing advanced tools."""
        self.root.update_idletasks()
        self.root.after_idle(self.show_advanced_tools)
    
    def safe_select_all(self):
        """Thread-safe wrapper for select all."""
        self.root.update_idletasks()
        self.select_all()
        self.root.update_idletasks()
    
    def safe_clear_all(self):
        """Thread-safe wrapper for clear all."""
        self.root.update_idletasks()
        self.clear_all()
        self.root.update_idletasks()
    
    def safe_start_extraction(self):
        """Thread-safe wrapper for start extraction."""
        self.root.update_idletasks()
        self.start_extraction()
    
    def safe_stop_extraction(self):
        """Thread-safe wrapper for stop extraction."""
        self.root.update_idletasks()
        self.stop_extraction()
    
    def safe_update_status(self, status):
        """Thread-safe method to update status bar."""
        def update_status():
            self.status_var.set(status)
            self.root.update_idletasks()
        
        if threading.current_thread() == threading.main_thread():
            update_status()
        else:
            self.root.after(0, update_status)
    
    def show_help(self):
        """Show comprehensive help dialog."""
        help_window = tk.Toplevel(self.root)
        help_window.title("Help - Linux Package Metadata Extractor")
        help_window.geometry("800x600")
        help_window.transient(self.root)
        help_window.grab_set()  # Make dialog modal
        
        # Center the window
        help_window.update_idletasks()
        x = (help_window.winfo_screenwidth() // 2) - (800 // 2)
        y = (help_window.winfo_screenheight() // 2) - (600 // 2)
        help_window.geometry(f"800x600+{x}+{y}")
        
        # Create notebook for tabbed help
        notebook = ttk.Notebook(help_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Overview tab
        overview_frame = ttk.Frame(notebook)
        notebook.add(overview_frame, text="Overview")
        
        overview_text = scrolledtext.ScrolledText(overview_frame, wrap=tk.WORD, height=25)
        overview_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        overview_content = """
LINUX PACKAGE METADATA EXTRACTOR

OVERVIEW:
This tool extracts package metadata from various Linux distributions and converts it into CSV format for analysis. It supports 8 major Linux distributions and can process millions of packages.

SUPPORTED DISTRIBUTIONS:
• Ubuntu (22.04, 24.04 LTS) - ~275K packages
• Debian (bullseye, bookworm, trixie, sid) - ~532K packages  
• Arch Linux (rolling release) - ~28K packages
• Fedora (latest release) - ~209K packages
• CentOS (7.6-7.9, 8.0-8.5, 9-stream) - ~74K packages
• Rocky Linux (8.5-8.10, 9.0-9.6, 10.0) - ~43K packages
• Amazon Linux (AL2, AL2023) - ~120K packages
• Alpine Linux (edge, latest) - ~134K packages

WHAT IT DOES:
1. Downloads package repository metadata
2. Parses package information (name, version, description, etc.)
3. Detects licenses and generates PURLs (Package URLs)
4. Verifies package signatures when available
5. Exports everything to CSV files for analysis

OUTPUT FORMAT:
Each CSV contains columns like:
- package: Package name
- version: Package version
- sha256/sha512: Package checksums
- component: Repository component
- architecture: Target architecture (x86_64, aarch64, etc.)
- deb_url/rpm_url: Download URL
- license: Detected license
- purl: Package URL identifier
- release: Distribution release
- signature_verified: Signature verification status

TIME ESTIMATES:
• Single distribution: 1-10 minutes
• All distributions: 30-60 minutes
• Total packages: ~1.4 million across all distributions
        """
        
        overview_text.insert(tk.END, overview_content)
        overview_text.config(state=tk.DISABLED)
        
        # Usage tab
        usage_frame = ttk.Frame(notebook)
        notebook.add(usage_frame, text="How to Use")
        
        usage_text = scrolledtext.ScrolledText(usage_frame, wrap=tk.WORD, height=25)
        usage_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        usage_content = """
HOW TO USE THE GUI:

1. SELECT DISTRIBUTIONS:
   • Check the boxes for distributions you want to process
   • Use "Select All" to choose everything
   • Use "Clear All" to deselect everything

2. START EXTRACTION:
   • Click "Start Extraction" to begin processing
   • Progress will be shown in the text area below
   • You can stop at any time with "Stop All"

3. MONITOR PROGRESS:
   • Watch the progress area for real-time updates
   • Each distribution shows download and parsing progress
   • Completed distributions show ✅ success markers

4. FIND YOUR RESULTS:
   • CSV files are saved in the output/ directory
   • Each distribution gets its own folder
   • Combined files are available in the root directory

UNDERSTANDING THE OUTPUT:
• Individual files: output/ubuntu/ubuntu_packages.csv
• Release-specific: output/rocky/rocky_9.4_packages.csv  
• Combined files: combined_ubuntu_packages.csv

COMMAND LINE OPTIONS:
Each distribution script supports command line options:
• --help: Show detailed help
• --version: Show version information
• --list-releases: Show supported releases
• --release X: Process specific release only
• --no-csv: Skip CSV generation
        """
        
        usage_text.insert(tk.END, usage_content)
        usage_text.config(state=tk.DISABLED)
        
        # Advanced tab
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="Advanced")
        
        advanced_text = scrolledtext.ScrolledText(advanced_frame, wrap=tk.WORD, height=25)
        advanced_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        advanced_content = """
ADVANCED FEATURES:

COMMAND LINE USAGE:
You can run individual scripts from the command line:

Download Scripts:
• bash rocky/download_rocky_packages.sh --help
• bash ubuntu/download_ubuntu_packages.sh --help
• bash centos/download_centos_packages.sh --help  
• bash debian/download_debian_packages.sh --help

Parser Scripts:
• python3 rocky/parse_rocky_packages.py --release 9.4
• python3 ubuntu/parse_ubuntu_packages.py --release jammy
• python3 centos/parse_centos_packages.py --release 8.5

Combine Scripts:
• python3 scripts/combine_csv.py --all
• python3 scripts/combine_csv.py --by-distribution
• python3 scripts/combine_csv.py --list

DIRECTORY STRUCTURE:
linux-package-metadata/
├── output/           # Generated CSV files
│   ├── ubuntu/       # Ubuntu-specific CSVs
│   ├── rocky/        # Rocky Linux CSVs
│   └── ...
├── temp/             # Temporary download files
├── scripts/          # Utility scripts
└── utils/            # Python utilities

CUSTOMIZATION:
• Modify release lists in download scripts
• Adjust architectures (x86_64, aarch64, arm64)
• Change output directories with --output-dir
• Use custom temporary directories with --temp-dir

SIGNATURE VERIFICATION:
The tool attempts to verify package signatures when available:
• Ubuntu/Debian: APT signature verification
• Rocky/CentOS: RPM GPG signature verification
• Results included in signature_verified column

PERFORMANCE TUNING:
• Scripts use parallel downloads (6-8 concurrent)
• Adjust job limits in scripts if needed
• More CPU cores = faster processing
• SSD storage recommended for temp files

LICENSE DETECTION:
Advanced license detection using patterns:
• SPDX license identifiers
• Common license names (MIT, GPL, Apache, etc.)
• Fuzzy matching for variations
• Unknown licenses marked appropriately
        """
        
        advanced_text.insert(tk.END, advanced_content)
        advanced_text.config(state=tk.DISABLED)
        
        # About tab
        about_frame = ttk.Frame(notebook)
        notebook.add(about_frame, text="About")
        
        about_text = scrolledtext.ScrolledText(about_frame, wrap=tk.WORD, height=25)
        about_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        about_content = """
ABOUT LINUX PACKAGE METADATA EXTRACTOR

VERSION: 1.0
AUTHOR: Linux Package Metadata Team

PURPOSE:
This tool was created to provide comprehensive package metadata from major Linux distributions in a standardized CSV format. It enables security researchers, system administrators, and developers to analyze software packages across different Linux ecosystems.

FEATURES:
✓ Support for 8 major Linux distributions
✓ Multiple release versions per distribution
✓ Comprehensive metadata extraction
✓ License detection and PURL generation
✓ Signature verification where available
✓ Parallel processing for speed
✓ User-friendly GUI and command-line interfaces
✓ Standardized CSV output format

DATA SOURCES:
All package data comes directly from official distribution repositories:
• Ubuntu: archive.ubuntu.com, ports.ubuntu.com
• Debian: deb.debian.org, ftp.debian.org
• Rocky Linux: dl.rockylinux.org
• CentOS: vault.centos.org, mirror.stream.centos.org
• Fedora, Arch, Alpine, Amazon Linux: respective official APIs

OUTPUT SPECIFICATION:
CSV files follow a standardized schema across all distributions:
- Consistent column names and formats
- UTF-8 encoding
- RFC 4180 compliant CSV format
- Proper escaping of special characters
- Sortable and filterable data

REQUIREMENTS:
• Python 3.7 or higher
• curl, gunzip, standard Unix tools
• Internet connection for downloads
• 1-2 GB free disk space
• Modern multi-core CPU recommended

LICENSE:
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at:

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Package data remains under the respective distribution licenses.
        """
        
        about_text.insert(tk.END, about_content)
        about_text.config(state=tk.DISABLED)
        
        # Close button
        def close_help():
            help_window.grab_release()
            help_window.destroy()
        
        close_btn = ttk.Button(help_window, text="Close", command=close_help)
        close_btn.pack(pady=10)
        
        # Handle window close event
        help_window.protocol("WM_DELETE_WINDOW", close_help)
    
    def show_advanced_tools(self):
        """Show advanced tools dialog."""
        tools_window = tk.Toplevel(self.root)
        tools_window.title("Advanced Tools")
        tools_window.geometry("600x500")
        tools_window.transient(self.root)
        tools_window.grab_set()  # Make dialog modal
        
        # Center the window
        tools_window.update_idletasks()
        x = (tools_window.winfo_screenwidth() // 2) - (600 // 2)
        y = (tools_window.winfo_screenheight() // 2) - (500 // 2)
        tools_window.geometry(f"600x500+{x}+{y}")
        
        main_frame = ttk.Frame(tools_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Advanced Tools", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Combine CSV section
        combine_frame = ttk.LabelFrame(main_frame, text="Combine CSV Files", padding="10")
        combine_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(combine_frame, text="Combine generated CSV files:", font=("Arial", 10)).pack(anchor=tk.W)
        
        combine_buttons_frame = ttk.Frame(combine_frame)
        combine_buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(combine_buttons_frame, text="List Available Files", 
                  command=lambda: self.run_command(["python3", "scripts/combine_csv.py", "--list"])).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(combine_buttons_frame, text="Combine All", 
                  command=lambda: self.run_command(["python3", "scripts/combine_csv.py", "--all"])).pack(side=tk.LEFT, padx=5)
        ttk.Button(combine_buttons_frame, text="By Distribution", 
                  command=lambda: self.run_command(["python3", "scripts/combine_csv.py", "--by-distribution"])).pack(side=tk.LEFT, padx=5)
        
        # Individual script section
        scripts_frame = ttk.LabelFrame(main_frame, text="Run Individual Scripts", padding="10")
        scripts_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(scripts_frame, text="Run specific distribution scripts with options:", font=("Arial", 10)).pack(anchor=tk.W)
        
        # Script selection
        script_frame = ttk.Frame(scripts_frame)
        script_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(script_frame, text="Script:").pack(side=tk.LEFT)
        self.script_var = tk.StringVar(value="rocky/download_rocky_packages.sh")
        script_combo = ttk.Combobox(script_frame, textvariable=self.script_var, width=40)
        script_combo['values'] = [
            "rocky/download_rocky_packages.sh",
            "ubuntu/download_ubuntu_packages.sh", 
            "centos/download_centos_packages.sh",
            "debian/download_debian_packages.sh",
            "rocky/parse_rocky_packages.py",
            "ubuntu/parse_ubuntu_packages.py",
            "centos/parse_centos_packages.py",
            "debian/parse_debian_packages.py"
        ]
        script_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Options entry
        options_frame = ttk.Frame(scripts_frame)
        options_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(options_frame, text="Options:").pack(side=tk.LEFT)
        self.options_var = tk.StringVar(value="--help")
        options_entry = ttk.Entry(options_frame, textvariable=self.options_var)
        options_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Run button
        ttk.Button(scripts_frame, text="Run Script", command=self.run_individual_script).pack(pady=5)
        
        # Output area
        output_frame = ttk.LabelFrame(main_frame, text="Output", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tools_output = scrolledtext.ScrolledText(output_frame, height=15)
        self.tools_output.pack(fill=tk.BOTH, expand=True)
        
        # Close button
        def close_tools():
            tools_window.grab_release()
            tools_window.destroy()
        
        ttk.Button(main_frame, text="Close", command=close_tools).pack(pady=10)
        
        # Handle window close event
        tools_window.protocol("WM_DELETE_WINDOW", close_tools)
    
    def run_command(self, command):
        """Run a command and display output in tools window."""
        def run_in_thread():
            try:
                result = subprocess.run(command, capture_output=True, text=True, cwd=".")
                output = f"Command: {' '.join(command)}\n"
                output += f"Exit code: {result.returncode}\n\n"
                output += "STDOUT:\n" + result.stdout + "\n"
                if result.stderr:
                    output += "STDERR:\n" + result.stderr + "\n"
                output += "\n" + "="*50 + "\n\n"
                
                # Thread-safe GUI update
                self.root.after(0, lambda: self._update_tools_output(output))
            except Exception as e:
                error_msg = f"Error running command: {e}\n\n"
                # Thread-safe GUI update
                self.root.after(0, lambda: self._update_tools_output(error_msg))
        
        thread = threading.Thread(target=run_in_thread)
        thread.daemon = True
        thread.start()
    
    def _update_tools_output(self, text):
        """Thread-safe method to update tools output."""
        if hasattr(self, 'tools_output'):
            self.tools_output.insert(tk.END, text)
            self.tools_output.see(tk.END)
            self.root.update_idletasks()
    
    def run_individual_script(self):
        """Run an individual script with options."""
        script = self.script_var.get()
        options = self.options_var.get().split() if self.options_var.get() else []
        
        if script.endswith('.py'):
            command = ["python3", script] + options
        else:
            command = ["bash", script] + options
        
        self.run_command(command)

def main():
    # Check if we're in the right directory
    if not Path("requirements.txt").exists():
        print("Error: Please run this script from the linux-package-metadata directory")
        print("Current directory:", os.getcwd())
        sys.exit(1)
    
    root = tk.Tk()
    app = LinuxPackageExtractorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

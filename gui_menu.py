#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import os
import sys
from pathlib import Path
import time

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
        select_all_btn = ttk.Button(button_frame, text="Select All", command=self.select_all)
        select_all_btn.grid(row=0, column=0, padx=5)
        
        # Clear All button
        clear_all_btn = ttk.Button(button_frame, text="Clear All", command=self.clear_all)
        clear_all_btn.grid(row=0, column=1, padx=5)
        
        # Start Extraction button
        self.start_btn = ttk.Button(button_frame, text="Start Extraction", 
                                   command=self.start_extraction, style="Accent.TButton")
        self.start_btn.grid(row=0, column=2, padx=5)
        
        # Stop button
        self.stop_btn = ttk.Button(button_frame, text="Stop All", 
                                  command=self.stop_extraction, state="disabled")
        self.stop_btn.grid(row=0, column=3, padx=5)
        
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
        timestamp = time.strftime("%H:%M:%S")
        self.progress_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.progress_text.see(tk.END)
        self.root.update_idletasks()
    
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
        self.status_var.set(f"Extracting {len(selected)} distributions...")
        
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
                self.status_var.set("Completed")
            
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
        self.status_var.set("Stopped")
        self.extraction_finished()
    
    def extraction_finished(self):
        """Re-enable buttons after extraction is finished."""
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

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
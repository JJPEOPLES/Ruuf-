#!/usr/bin/env python3
"""
Ruuf USB Flasher - A simple GUI application to create bootable USB drives for Windows, macOS, and Linux
"""

import sys
import os
import platform
import subprocess
import threading
import time
import importlib.util
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QPushButton, QLabel, QProgressBar,
                            QComboBox, QFileDialog, QMessageBox, QGroupBox,
                            QAction, QMenu, QInputDialog, QLineEdit, QDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QIcon, QFont

# Import the password dialog
try:
    from password_dialog import PasswordDialog
except ImportError:
    # Fallback implementation if the module is not available
    class PasswordDialog(QDialog):
        """
        Dialog for getting sudo password on Linux
        """
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Authentication Required")
            self.setMinimumWidth(400)

            layout = QVBoxLayout()
            self.setLayout(layout)

            # Message
            message = QLabel("This operation requires administrative privileges.\nPlease enter your password:")
            layout.addWidget(message)

            # Password field
            self.password_field = QLineEdit()
            self.password_field.setEchoMode(QLineEdit.Password)
            layout.addWidget(self.password_field)

            # Buttons
            button_layout = QHBoxLayout()

            self.ok_button = QPushButton("OK")
            self.ok_button.clicked.connect(self.accept)
            button_layout.addWidget(self.ok_button)

            self.cancel_button = QPushButton("Cancel")
            self.cancel_button.clicked.connect(self.reject)
            button_layout.addWidget(self.cancel_button)

            layout.addLayout(button_layout)

        def get_password(self):
            """Return the entered password"""
            return self.password_field.text()

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    password_required = pyqtSignal()

class FlashWorker(threading.Thread):
    """
    Worker thread for flashing ISO to USB drive
    """
    def __init__(self, iso_path, usb_device):
        super().__init__()
        self.iso_path = iso_path
        self.usb_device = usb_device
        self.signals = WorkerSignals()
        self.is_running = True
        self.sudo_password = None

    def run_sudo_command(self, cmd, **kwargs):
        """Run a command with sudo, using the password if available"""
        if self.sudo_password and platform.system() == "Linux":
            # Prepend the password to the command
            cmd = f"echo '{self.sudo_password}' | sudo -S {cmd}"
        else:
            # Just prepend sudo
            cmd = f"sudo {cmd}"
        return subprocess.run(cmd, shell=True, **kwargs)

    def run(self):
        try:
            self.signals.status.emit("Preparing to flash ISO...")
            self.signals.progress.emit(0)

            # Platform-specific commands
            if platform.system() == "Windows":
                self._flash_windows()
            elif platform.system() == "Linux":
                # On Linux, always use dd for direct writing (most reliable method)
                self.signals.status.emit("Using dd for direct writing (most reliable method on Linux)...")
                self._flash_linux_dd(self.usb_device)
            elif platform.system() == "Darwin":  # macOS
                self._flash_macos()
            else:
                self.signals.error.emit(f"Unsupported operating system: {platform.system()}")
                return

            self.signals.status.emit("Flash completed successfully!")
            self.signals.progress.emit(100)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(f"Error during flashing: {str(e)}")

class HackintoshWorker(threading.Thread):
    """
    Worker thread for creating Hackintosh USB
    """
    def __init__(self, macos_version, usb_device):
        super().__init__()
        self.macos_version = macos_version
        self.usb_device = usb_device
        self.signals = WorkerSignals()
        self.is_running = True
        self.sudo_password = None

    def run_sudo_command(self, cmd, **kwargs):
        """Run a command with sudo, using the password if available"""
        if self.sudo_password and platform.system() == "Linux":
            # Prepend the password to the command
            cmd = f"echo '{self.sudo_password}' | sudo -S {cmd}"
        else:
            # Just prepend sudo
            cmd = f"sudo {cmd}"
        return subprocess.run(cmd, shell=True, **kwargs)

class LinuxWorker(threading.Thread):
    """
    Worker thread for creating Linux USB
    """
    def __init__(self, linux_distro, custom_iso_path, usb_device):
        super().__init__()
        self.linux_distro = linux_distro
        self.custom_iso_path = custom_iso_path
        self.usb_device = usb_device
        self.signals = WorkerSignals()
        self.is_running = True
        self.sudo_password = None

    def run_sudo_command(self, cmd, **kwargs):
        """Run a command with sudo, using the password if available"""
        if self.sudo_password and platform.system() == "Linux":
            # Prepend the password to the command
            cmd = f"echo '{self.sudo_password}' | sudo -S {cmd}"
        else:
            # Just prepend sudo
            cmd = f"sudo {cmd}"
        return subprocess.run(cmd, shell=True, **kwargs)

    def run(self):
        try:
            self.signals.status.emit(f"Preparing to create {self.linux_distro} USB...")
            self.signals.progress.emit(0)

            # Platform-specific commands
            if platform.system() == "Windows":
                self._create_linux_windows()
            elif platform.system() == "Linux":
                self._create_linux_linux()
            elif platform.system() == "Darwin":  # macOS
                self._create_linux_macos()
            else:
                self.signals.error.emit(f"Unsupported operating system: {platform.system()}")
                return

            self.signals.status.emit(f"{self.linux_distro} USB created successfully!")
            self.signals.progress.emit(100)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(f"Error during Linux USB creation: {str(e)}")

    def _create_linux_windows(self):
        """Create Linux USB on Windows using direct write method"""
        try:
            # Get drive letter from device path
            drive_letter = self.usb_device.split(':')[0]

            # Get disk number for the USB drive
            self.signals.status.emit("Identifying USB disk number...")
            self.signals.progress.emit(5)

            get_disk_cmd = f'powershell "Get-Disk | Where-Object {{$_.Bustype -eq \'USB\' -and (Get-Partition -DiskNumber $_.Number | Where-Object {{$_.DriveLetter -eq \'{drive_letter}\'}})}} | Select-Object -ExpandProperty Number"'
            disk_number = subprocess.check_output(get_disk_cmd, shell=True).decode().strip()

            if not disk_number:
                self.signals.error.emit(f"Could not find disk number for drive {drive_letter}:")
                return

            # Determine if we need to download an ISO or use a custom one
            iso_path = ""
            if self.linux_distro == "Other (Custom ISO)":
                if not self.custom_iso_path:
                    self.signals.error.emit("No custom ISO file selected")
                    return
                iso_path = self.custom_iso_path
                self.signals.status.emit(f"Using custom ISO: {os.path.basename(iso_path)}")
            else:
                # Download the selected Linux distribution
                self.signals.status.emit(f"Downloading {self.linux_distro} ISO...")
                self.signals.progress.emit(10)

                # Create a temporary directory for downloads
                temp_dir = os.path.join(os.environ.get('TEMP', '.'), 'linux_temp')
                os.makedirs(temp_dir, exist_ok=True)

                # Get the download URL for the selected distribution
                download_url = self._get_linux_download_url()
                iso_filename = download_url.split('/')[-1]
                iso_path = os.path.join(temp_dir, iso_filename)

                # Download the ISO
                download_cmd = f'powershell -Command "Invoke-WebRequest -Uri \'{download_url}\' -OutFile \'{iso_path}\'"'

                # For large files, this could take a while, so we'll update progress periodically
                self.signals.status.emit(f"Downloading {self.linux_distro} ISO (this may take a while)...")

                process = subprocess.Popen(
                    download_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT
                )

                # Monitor the process
                start_time = time.time()
                while process.poll() is None:
                    if not self.is_running:
                        process.terminate()
                        break

                    # Update progress based on time (approximate)
                    elapsed = time.time() - start_time
                    # Assume it takes roughly 10 minutes to download a typical ISO
                    progress = min(10 + int(elapsed / 600 * 30), 40)
                    self.signals.progress.emit(progress)
                    self.signals.status.emit(f"Downloading {self.linux_distro} ISO... (approximately {progress-10}% complete)")
                    time.sleep(2)

                if process.returncode != 0:
                    self.signals.error.emit("Download failed")
                    return

            # Use direct write method for Linux ISOs (similar to dd on Linux/macOS)
            self.signals.status.emit(f"Preparing to write ISO to disk {disk_number}...")
            self.signals.progress.emit(45)

            # First, unmount/dismount the drive to ensure we can write to it
            self.signals.status.emit("Dismounting drive...")
            dismount_cmd = f'powershell "Get-Disk -Number {disk_number} | Get-Partition | Get-Volume | Where-Object DriveLetter | ForEach-Object {{ mountvol $($_.DriveLetter + \':\') /d }}"'
            subprocess.run(dismount_cmd, shell=True)

            # Get total size for progress calculation
            total_size = os.path.getsize(iso_path)

            # Use PowerShell and Win32_DiskDrive to write the ISO directly to the disk
            self.signals.status.emit(f"Writing ISO to disk {disk_number}...")
            self.signals.progress.emit(50)

            # Create a PowerShell script for direct writing
            # Handle backslashes in the path properly
            safe_iso_path = iso_path.replace("\\", "\\\\")

            ps_script = """
            $iso = [System.IO.File]::OpenRead('{0}')
            $disk = New-Object -ComObject Win32_DiskDrive
            $disk.DeviceID = '\\\\.\\PhysicalDrive{1}'
            $disk.Open()

            $buffer = New-Object byte[] 1048576  # 1MB buffer
            $total = $iso.Length
            $written = 0

            while ($count = $iso.Read($buffer, 0, $buffer.Length)) {{
                $disk.Write($buffer, $count)
                $written += $count
                Write-Host "Progress: $written of $total bytes"
            }}

            $iso.Close()
            $disk.Close()
            """.format(safe_iso_path, disk_number)

            # Write the PowerShell script to a temporary file
            ps_script_path = os.path.join(os.environ.get('TEMP', '.'), 'write_iso.ps1')
            with open(ps_script_path, 'w') as f:
                f.write(ps_script)

            # Run the PowerShell script with admin privileges
            write_cmd = f'powershell -ExecutionPolicy Bypass -File "{ps_script_path}"'

            process = subprocess.Popen(
                write_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )

            # Monitor progress
            for line in iter(process.stdout.readline, ''):
                if not self.is_running:
                    process.terminate()
                    break

                if "Progress:" in line:
                    try:
                        # Extract bytes written
                        parts = line.split()
                        bytes_written = int(parts[1])
                        progress = min(50 + int(bytes_written / total_size * 45), 95)
                        self.signals.progress.emit(progress)
                        self.signals.status.emit(f"Writing: {bytes_written/1024/1024:.2f} MB of {total_size/1024/1024:.2f} MB")
                    except (ValueError, IndexError):
                        pass

            process.wait()
            if process.returncode != 0:
                self.signals.error.emit("Write operation failed")
                return

            # Remove the temporary script file
            os.remove(ps_script_path)

            # Finalize
            self.signals.status.emit("Finalizing...")
            self.signals.progress.emit(95)

            # Clean up downloaded files if not a custom ISO
            if self.linux_distro != "Other (Custom ISO)":
                try:
                    os.remove(iso_path)
                    os.rmdir(os.path.dirname(iso_path))
                except:
                    pass

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return

    def _create_linux_linux(self):
        """Create Linux USB on Linux using dd for direct writing"""
        try:
            # Ensure device path is correct (should be like /dev/sdb, not a partition)
            device = self.usb_device

            # Check if we need to unmount any existing partitions
            self.signals.status.emit("Checking for mounted partitions...")
            self.signals.progress.emit(5)

            # Get list of mounted partitions for this device
            check_mounts_cmd = f"mount | grep {device}"
            mounted_parts = subprocess.run(check_mounts_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if mounted_parts.stdout:
                self.signals.status.emit("Unmounting partitions...")
                # Unmount all partitions of the device
                unmount_cmd = f"sudo umount {device}*"
                subprocess.run(unmount_cmd, shell=True, stderr=subprocess.PIPE)

            # Determine if we need to download an ISO or use a custom one
            iso_path = ""
            if self.linux_distro == "Other (Custom ISO)":
                if not self.custom_iso_path:
                    self.signals.error.emit("No custom ISO file selected")
                    return
                iso_path = self.custom_iso_path
                self.signals.status.emit(f"Using custom ISO: {os.path.basename(iso_path)}")
                self.signals.progress.emit(40)
            else:
                # Download the selected Linux distribution
                self.signals.status.emit(f"Downloading {self.linux_distro} ISO...")
                self.signals.progress.emit(10)

                # Create a temporary directory for downloads
                temp_dir = "/tmp/linux_temp"
                os.makedirs(temp_dir, exist_ok=True)

                # Get the download URL for the selected distribution
                download_url = self._get_linux_download_url()
                iso_filename = download_url.split('/')[-1]
                iso_path = os.path.join(temp_dir, iso_filename)

                # Download the ISO using wget
                download_cmd = f"wget -q --show-progress -O '{iso_path}' '{download_url}'"

                process = subprocess.Popen(
                    download_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )

                # Monitor progress
                for line in iter(process.stdout.readline, ''):
                    if not self.is_running:
                        process.terminate()
                        break

                    if "%" in line:
                        try:
                            # Extract percentage
                            percent = int(line.split('%')[0].split()[-1])
                            progress = 10 + int(percent * 0.3)  # Scale to 10-40% range
                            self.signals.progress.emit(progress)
                            self.signals.status.emit(f"Downloading: {percent}% complete")
                        except (ValueError, IndexError):
                            pass

                process.wait()
                if process.returncode != 0:
                    self.signals.error.emit("Download failed")
                    return

            # Use dd to directly write the ISO to the USB drive (most reliable method for Linux)
            self.signals.status.emit(f"Writing ISO to {device} using dd...")
            self.signals.progress.emit(45)

            # Get total size for progress calculation
            total_size = os.path.getsize(iso_path)
            block_size = 4 * 1024 * 1024  # 4MB blocks

            # Use dd with status=progress to get real-time progress
            if self.sudo_password:
                # Use echo to pipe the password to sudo
                cmd = f"echo '{self.sudo_password}' | sudo -S dd if='{iso_path}' of='{device}' bs={block_size} status=progress"
            else:
                cmd = f"sudo dd if='{iso_path}' of='{device}' bs={block_size} status=progress"

            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )

            # Monitor progress
            for line in iter(process.stdout.readline, ''):
                if not self.is_running:
                    process.terminate()
                    break

                if "bytes" in line:
                    try:
                        # Extract bytes written
                        bytes_written = int(line.split()[0])
                        progress = min(45 + int(bytes_written / total_size * 50), 95)
                        self.signals.progress.emit(progress)
                        self.signals.status.emit(f"Writing: {bytes_written/1024/1024:.2f} MB of {total_size/1024/1024:.2f} MB")
                    except (ValueError, IndexError):
                        pass

            process.wait()
            if process.returncode != 0:
                self.signals.error.emit("dd command failed")
                return

            # Sync to ensure all writes are complete
            self.signals.status.emit("Syncing writes to disk...")
            self.signals.progress.emit(95)
            subprocess.run("sync", shell=True, check=True)

            # Clean up downloaded files if not a custom ISO
            if self.linux_distro != "Other (Custom ISO)":
                try:
                    os.remove(iso_path)
                    os.rmdir(os.path.dirname(iso_path))
                except:
                    pass

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return

    def _create_linux_macos(self):
        """Create Linux USB on macOS using dd for direct writing"""
        try:
            # Get the base device (e.g., /dev/disk2)
            base_device = self.usb_device

            # Check if any volumes from this device are mounted
            self.signals.status.emit("Checking for mounted volumes...")
            self.signals.progress.emit(5)

            # Unmount all volumes on this disk
            self.signals.status.emit("Unmounting volumes...")
            subprocess.run(f"diskutil unmountDisk {base_device}", shell=True)

            # Determine if we need to download an ISO or use a custom one
            iso_path = ""
            if self.linux_distro == "Other (Custom ISO)":
                if not self.custom_iso_path:
                    self.signals.error.emit("No custom ISO file selected")
                    return
                iso_path = self.custom_iso_path
                self.signals.status.emit(f"Using custom ISO: {os.path.basename(iso_path)}")
                self.signals.progress.emit(40)
            else:
                # Download the selected Linux distribution
                self.signals.status.emit(f"Downloading {self.linux_distro} ISO...")
                self.signals.progress.emit(10)

                # Create a temporary directory for downloads
                temp_dir = "/tmp/linux_temp"
                os.makedirs(temp_dir, exist_ok=True)

                # Get the download URL for the selected distribution
                download_url = self._get_linux_download_url()
                iso_filename = download_url.split('/')[-1]
                iso_path = os.path.join(temp_dir, iso_filename)

                # Download the ISO using curl
                download_cmd = f"curl -L -o '{iso_path}' '{download_url}'"

                # For large files, this could take a while, so we'll update progress periodically
                self.signals.status.emit(f"Downloading {self.linux_distro} ISO (this may take a while)...")

                process = subprocess.Popen(
                    download_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT
                )

                # Monitor the process
                start_time = time.time()
                while process.poll() is None:
                    if not self.is_running:
                        process.terminate()
                        break

                    # Update progress based on time (approximate)
                    elapsed = time.time() - start_time
                    # Assume it takes roughly 10 minutes to download a typical ISO
                    progress = min(10 + int(elapsed / 600 * 30), 40)
                    self.signals.progress.emit(progress)
                    self.signals.status.emit(f"Downloading {self.linux_distro} ISO... (approximately {progress-10}% complete)")
                    time.sleep(2)

                if process.returncode != 0:
                    self.signals.error.emit("Download failed")
                    return

            # Convert /dev/diskX to /dev/rdiskX for faster writes
            raw_device = base_device
            if raw_device.startswith("/dev/disk"):
                raw_device = raw_device.replace("/dev/disk", "/dev/rdisk")

            # Use dd to directly write the ISO to the USB drive (most reliable method)
            self.signals.status.emit(f"Writing ISO to {raw_device} using dd...")
            self.signals.progress.emit(45)

            # Get total size for progress calculation
            total_size = os.path.getsize(iso_path)
            block_size = 4 * 1024 * 1024  # 4MB blocks

            # Use dd command
            cmd = f"sudo dd if='{iso_path}' of='{raw_device}' bs={block_size}"

            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )

            # Since macOS dd doesn't show progress, we'll check the disk usage periodically
            start_time = time.time()
            while process.poll() is None:
                if not self.is_running:
                    process.terminate()
                    break

                # Update progress based on time (approximate)
                elapsed = time.time() - start_time
                # Assume it takes roughly 5 minutes to write a typical ISO
                progress = min(45 + int(elapsed / 300 * 50), 95)
                self.signals.progress.emit(progress)
                self.signals.status.emit(f"Writing ISO... (approximately {progress-45}% complete)")
                time.sleep(2)

            if process.returncode != 0:
                self.signals.error.emit("dd command failed")
                return

            # Sync to ensure all writes are complete
            self.signals.status.emit("Syncing writes to disk...")
            self.signals.progress.emit(95)
            subprocess.run("sync", shell=True, check=True)

            # Clean up downloaded files if not a custom ISO
            if self.linux_distro != "Other (Custom ISO)":
                try:
                    os.remove(iso_path)
                    os.rmdir(os.path.dirname(iso_path))
                except:
                    pass

            # Eject the USB drive
            subprocess.run(f"diskutil eject {base_device}", shell=True)

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return

    def _get_linux_download_url(self):
        """Get the download URL for the selected Linux distribution"""
        # These URLs may need to be updated periodically as new versions are released
        urls = {
            "Ubuntu 22.04 LTS": "https://releases.ubuntu.com/22.04/ubuntu-22.04.3-desktop-amd64.iso",
            "Ubuntu 23.10": "https://releases.ubuntu.com/23.10/ubuntu-23.10-desktop-amd64.iso",
            "Linux Mint 21.2": "https://mirrors.edge.kernel.org/linuxmint/stable/21.2/linuxmint-21.2-cinnamon-64bit.iso",
            "Debian 12": "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.2.0-amd64-netinst.iso",
            "Fedora 39": "https://download.fedoraproject.org/pub/fedora/linux/releases/39/Workstation/x86_64/iso/Fedora-Workstation-Live-x86_64-39-1.5.iso",
            "Pop!_OS 22.04": "https://iso.pop-os.org/22.04/amd64/intel/22/pop-os_22.04_amd64_intel_22.iso",
            "Manjaro": "https://download.manjaro.org/kde/23.0.2/manjaro-kde-23.0.2-230921-linux65.iso",
            "Arch Linux": "https://geo.mirror.pkgbuild.com/iso/2023.11.01/archlinux-2023.11.01-x86_64.iso",
            "Kali Linux": "https://cdimage.kali.org/kali-2023.3/kali-linux-2023.3-installer-amd64.iso",
            "Elementary OS 7": "https://sgp1.dl.elementary.io/download/MTY5OTQ0NzU5Nw==/elementaryos-7.0-stable.20230129rc.iso",
            "Zorin OS 17": "https://mirrors.edge.kernel.org/zorinos/17/Zorin-OS-17-Core-64-bit.iso"
        }

        return urls.get(self.linux_distro, "")

    def stop(self):
        """Stop the creation process"""
        self.is_running = True

    def run(self):
        try:
            self.signals.status.emit("Preparing to create Hackintosh USB...")
            self.signals.progress.emit(0)

            # Platform-specific commands
            if platform.system() == "Windows":
                self._create_hackintosh_windows()
            elif platform.system() == "Linux":
                self._create_hackintosh_linux()
            elif platform.system() == "Darwin":  # macOS
                self._create_hackintosh_macos()
            else:
                self.signals.error.emit(f"Unsupported operating system: {platform.system()}")
                return

            self.signals.status.emit("Hackintosh USB created successfully!")
            self.signals.progress.emit(100)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(f"Error during Hackintosh USB creation: {str(e)}")

    def _create_hackintosh_windows(self):
        """Create Hackintosh USB on Windows"""
        try:
            # Get drive letter from device path
            drive_letter = self.usb_device.split(':')[0]

            # Get disk number for the USB drive
            self.signals.status.emit("Identifying USB disk number...")
            self.signals.progress.emit(5)

            get_disk_cmd = f'powershell "Get-Disk | Where-Object {{$_.Bustype -eq \'USB\' -and (Get-Partition -DiskNumber $_.Number | Where-Object {{$_.DriveLetter -eq \'{drive_letter}\'}})}} | Select-Object -ExpandProperty Number"'
            disk_number = subprocess.check_output(get_disk_cmd, shell=True).decode().strip()

            if not disk_number:
                self.signals.error.emit(f"Could not find disk number for drive {drive_letter}:")
                return

            # Clean the disk and create a new GPT partition table
            self.signals.status.emit(f"Cleaning disk {disk_number} and creating new partition table...")
            self.signals.progress.emit(10)

            # Use diskpart to clean the disk and create a GPT partition
            diskpart_script = f"""select disk {disk_number}
clean
convert gpt
create partition primary
format quick fs=fat32 label="EFI"
assign letter=S
create partition primary
format quick fs=exfat label="Install macOS"
assign letter={drive_letter}
exit"""

            # Write diskpart script to a temporary file
            script_path = os.path.join(os.environ.get('TEMP', '.'), 'diskpart_script.txt')
            with open(script_path, 'w') as f:
                f.write(diskpart_script)

            # Run diskpart with the script
            diskpart_cmd = f'diskpart /s "{script_path}"'
            subprocess.run(diskpart_cmd, shell=True, check=True)

            # Remove the temporary script file
            os.remove(script_path)

            # Download OpenCore bootloader
            self.signals.status.emit("Downloading OpenCore bootloader...")
            self.signals.progress.emit(20)

            # Create a temporary directory for downloads
            temp_dir = os.path.join(os.environ.get('TEMP', '.'), 'hackintosh_temp')
            os.makedirs(temp_dir, exist_ok=True)

            # Download OpenCore
            opencore_url = "https://github.com/acidanthera/OpenCorePkg/releases/download/0.9.5/OpenCore-0.9.5-RELEASE.zip"
            opencore_zip = os.path.join(temp_dir, "OpenCore.zip")

            self.signals.status.emit("Downloading OpenCore...")
            download_cmd = f'powershell -Command "Invoke-WebRequest -Uri \'{opencore_url}\' -OutFile \'{opencore_zip}\'"'
            subprocess.run(download_cmd, shell=True, check=True)

            # Extract OpenCore
            self.signals.status.emit("Extracting OpenCore...")
            self.signals.progress.emit(30)

            extract_cmd = f'powershell -Command "Expand-Archive -Path \'{opencore_zip}\' -DestinationPath \'{temp_dir}\' -Force"'
            subprocess.run(extract_cmd, shell=True, check=True)

            # Copy EFI folder to the EFI partition
            self.signals.status.emit("Copying OpenCore to EFI partition...")
            self.signals.progress.emit(40)

            # Copy the X64 EFI folder for UEFI systems
            copy_cmd = f'xcopy "{temp_dir}\\X64\\EFI" "S:\\EFI\\" /E /H /I /Y'
            subprocess.run(copy_cmd, shell=True, check=True)

            # Download macOS recovery
            self.signals.status.emit(f"Downloading {self.macos_version} recovery...")
            self.signals.progress.emit(50)

            # Download macOS recovery script
            recovery_script_url = "https://raw.githubusercontent.com/corpnewt/gibMacOS/master/gibMacOS.bat"
            recovery_script = os.path.join(temp_dir, "gibMacOS.bat")

            download_cmd = f'powershell -Command "Invoke-WebRequest -Uri \'{recovery_script_url}\' -OutFile \'{recovery_script}\'"'
            subprocess.run(download_cmd, shell=True, check=True)

            # Run the recovery download script
            self.signals.status.emit("Downloading macOS recovery files (this may take a while)...")
            self.signals.progress.emit(60)

            # Get macOS version code
            macos_code = self._get_macos_version_code()

            # Change to the temp directory and run the script
            os.chdir(temp_dir)
            recovery_cmd = f'cmd /c gibMacOS.bat -r -v {macos_code} -o "{drive_letter}:\\"'

            process = subprocess.Popen(
                recovery_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )

            # Monitor the process
            while process.poll() is None:
                if not self.is_running:
                    process.terminate()
                    break
                time.sleep(1)
                # Update progress (approximate)
                self.signals.progress.emit(70)

            # Configure OpenCore
            self.signals.status.emit("Configuring OpenCore...")
            self.signals.progress.emit(80)

            # Copy sample config to the correct location
            copy_cmd = f'copy "{temp_dir}\\Docs\\Sample.plist" "S:\\EFI\\OC\\config.plist" /Y'
            subprocess.run(copy_cmd, shell=True, check=True)

            # Download ProperTree for config editing
            propertree_url = "https://github.com/corpnewt/ProperTree/archive/refs/heads/master.zip"
            propertree_zip = os.path.join(temp_dir, "ProperTree.zip")

            download_cmd = f'powershell -Command "Invoke-WebRequest -Uri \'{propertree_url}\' -OutFile \'{propertree_zip}\'"'
            subprocess.run(download_cmd, shell=True, check=True)

            # Extract ProperTree
            extract_cmd = f'powershell -Command "Expand-Archive -Path \'{propertree_zip}\' -DestinationPath \'{temp_dir}\\ProperTree\' -Force"'
            subprocess.run(extract_cmd, shell=True, check=True)

            # Create a README file with instructions
            self.signals.status.emit("Creating documentation...")
            self.signals.progress.emit(90)

            readme_content = f"""# Hackintosh USB for {self.macos_version}

## Contents
- OpenCore 0.9.5 bootloader
- macOS {self.macos_version} recovery files

## Next Steps
1. You need to customize the config.plist file for your specific hardware
2. Use ProperTree (included in the USB) to edit S:\\EFI\\OC\\config.plist
3. Add necessary kexts for your hardware
4. Boot from this USB and follow the macOS installation process

## Resources
- OpenCore Install Guide: https://dortania.github.io/OpenCore-Install-Guide/
- Hackintosh Subreddit: https://www.reddit.com/r/hackintosh/
- OpenCore Discord: https://discord.gg/rV9AmXPd

Created with Ruuf USB Flasher
"""

            with open(f"{drive_letter}:\\README.txt", 'w') as f:
                f.write(readme_content)

            # Clean up
            self.signals.status.emit("Cleaning up...")
            self.signals.progress.emit(95)

            # Remove temporary files
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return

    def _create_hackintosh_linux(self):
        """Create Hackintosh USB on Linux"""
        try:
            # Ensure device path is correct (should be like /dev/sdb, not a partition)
            device = self.usb_device

            # Check if we need to unmount any existing partitions
            self.signals.status.emit("Checking for mounted partitions...")
            self.signals.progress.emit(5)

            # Get list of mounted partitions for this device
            check_mounts_cmd = f"mount | grep {device}"
            mounted_parts = subprocess.run(check_mounts_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if mounted_parts.stdout:
                self.signals.status.emit("Unmounting partitions...")
                # Unmount all partitions of the device
                unmount_cmd = f"sudo umount {device}*"
                subprocess.run(unmount_cmd, shell=True, stderr=subprocess.PIPE)

            # Create a new GPT partition table
            self.signals.status.emit("Creating new partition table...")
            self.signals.progress.emit(10)

            # Create a GPT partition table
            parted_cmd = f"sudo parted -s {device} mklabel gpt"
            subprocess.run(parted_cmd, shell=True, check=True)

            # Create an EFI partition (200MB)
            self.signals.status.emit("Creating EFI partition...")
            self.signals.progress.emit(15)

            parted_cmd = f"sudo parted -s {device} mkpart primary fat32 1MiB 201MiB"
            subprocess.run(parted_cmd, shell=True, check=True)

            # Set the ESP flag
            parted_cmd = f"sudo parted -s {device} set 1 esp on"
            subprocess.run(parted_cmd, shell=True, check=True)

            # Create a main data partition
            self.signals.status.emit("Creating main data partition...")
            self.signals.progress.emit(20)

            parted_cmd = f"sudo parted -s {device} mkpart primary 201MiB 100%"
            subprocess.run(parted_cmd, shell=True, check=True)

            # Format the partitions
            self.signals.status.emit("Formatting partitions...")
            self.signals.progress.emit(25)

            # Wait for the system to recognize the new partitions
            time.sleep(2)

            # Get the partition names
            efi_part = f"{device}1"
            main_part = f"{device}2"

            # Format EFI as FAT32
            format_cmd = f"sudo mkfs.fat -F32 {efi_part}"
            subprocess.run(format_cmd, shell=True, check=True)

            # Format main partition as exFAT or HFS+ if available
            try:
                format_cmd = f"sudo mkfs.exfat -n 'Install macOS' {main_part}"
                subprocess.run(format_cmd, shell=True, check=True)
            except:
                # Fallback to FAT32 if exFAT is not available
                format_cmd = f"sudo mkfs.fat -F32 {main_part}"
                subprocess.run(format_cmd, shell=True, check=True)

            # Create mount points
            self.signals.status.emit("Creating mount points...")
            self.signals.progress.emit(30)

            efi_mount = "/tmp/efi_mount"
            main_mount = "/tmp/main_mount"
            temp_dir = "/tmp/hackintosh_temp"

            os.makedirs(efi_mount, exist_ok=True)
            os.makedirs(main_mount, exist_ok=True)
            os.makedirs(temp_dir, exist_ok=True)

            # Mount the partitions
            mount_cmd = f"sudo mount {efi_part} {efi_mount}"
            subprocess.run(mount_cmd, shell=True, check=True)

            mount_cmd = f"sudo mount {main_part} {main_mount}"
            subprocess.run(mount_cmd, shell=True, check=True)

            # Download OpenCore
            self.signals.status.emit("Downloading OpenCore bootloader...")
            self.signals.progress.emit(40)

            opencore_url = "https://github.com/acidanthera/OpenCorePkg/releases/download/0.9.5/OpenCore-0.9.5-RELEASE.zip"
            opencore_zip = os.path.join(temp_dir, "OpenCore.zip")

            download_cmd = f"wget -q {opencore_url} -O {opencore_zip}"
            subprocess.run(download_cmd, shell=True, check=True)

            # Extract OpenCore
            self.signals.status.emit("Extracting OpenCore...")
            self.signals.progress.emit(50)

            extract_cmd = f"unzip -q {opencore_zip} -d {temp_dir}"
            subprocess.run(extract_cmd, shell=True, check=True)

            # Copy EFI folder to the EFI partition
            self.signals.status.emit("Copying OpenCore to EFI partition...")
            self.signals.progress.emit(60)

            # Create EFI directory structure
            os.makedirs(f"{efi_mount}/EFI", exist_ok=True)

            # Copy the X64 EFI folder for UEFI systems
            copy_cmd = f"sudo cp -r {temp_dir}/X64/EFI/* {efi_mount}/EFI/"
            subprocess.run(copy_cmd, shell=True, check=True)

            # Download macOS recovery
            self.signals.status.emit(f"Downloading {self.macos_version} recovery...")
            self.signals.progress.emit(70)

            # Clone gibMacOS repository
            clone_cmd = f"git clone --depth=1 https://github.com/corpnewt/gibMacOS {temp_dir}/gibMacOS"
            subprocess.run(clone_cmd, shell=True, check=True)

            # Run the recovery download script
            self.signals.status.emit("Downloading macOS recovery files (this may take a while)...")
            self.signals.progress.emit(75)

            # Get macOS version code
            macos_code = self._get_macos_version_code()

            # Change to the gibMacOS directory and run the script
            os.chdir(f"{temp_dir}/gibMacOS")
            recovery_cmd = f"python3 gibMacOS.py -r -v {macos_code} -o {main_mount}"

            process = subprocess.Popen(
                recovery_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )

            # Monitor the process
            while process.poll() is None:
                if not self.is_running:
                    process.terminate()
                    break
                time.sleep(1)
                # Update progress (approximate)
                self.signals.progress.emit(80)

            # Configure OpenCore
            self.signals.status.emit("Configuring OpenCore...")
            self.signals.progress.emit(85)

            # Copy sample config to the correct location
            copy_cmd = f"sudo cp {temp_dir}/Docs/Sample.plist {efi_mount}/EFI/OC/config.plist"
            subprocess.run(copy_cmd, shell=True, check=True)

            # Clone ProperTree for config editing
            clone_cmd = f"git clone --depth=1 https://github.com/corpnewt/ProperTree {main_mount}/ProperTree"
            subprocess.run(clone_cmd, shell=True, check=True)

            # Create a README file with instructions
            self.signals.status.emit("Creating documentation...")
            self.signals.progress.emit(90)

            readme_content = f"""# Hackintosh USB for {self.macos_version}

## Contents
- OpenCore 0.9.5 bootloader
- macOS {self.macos_version} recovery files

## Next Steps
1. You need to customize the config.plist file for your specific hardware
2. Use ProperTree (included in the USB) to edit /EFI/OC/config.plist
3. Add necessary kexts for your hardware
4. Boot from this USB and follow the macOS installation process

## Resources
- OpenCore Install Guide: https://dortania.github.io/OpenCore-Install-Guide/
- Hackintosh Subreddit: https://www.reddit.com/r/hackintosh/
- OpenCore Discord: https://discord.gg/rV9AmXPd

Created with Ruuf USB Flasher
"""

            with open(f"{main_mount}/README.txt", 'w') as f:
                f.write(readme_content)

            # Clean up
            self.signals.status.emit("Unmounting and cleaning up...")
            self.signals.progress.emit(95)

            # Unmount partitions
            subprocess.run(f"sudo umount {efi_mount}", shell=True)
            subprocess.run(f"sudo umount {main_mount}", shell=True)

            # Remove temporary directories
            try:
                os.rmdir(efi_mount)
                os.rmdir(main_mount)
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass

            # Sync to ensure all writes are complete
            subprocess.run("sync", shell=True, check=True)

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return

    def _create_hackintosh_macos(self):
        """Create Hackintosh USB on macOS (easiest since we're already on macOS)"""
        try:
            # Get the base device (e.g., /dev/disk2)
            base_device = self.usb_device

            # Check if any volumes from this device are mounted
            self.signals.status.emit("Checking for mounted volumes...")
            self.signals.progress.emit(5)

            # Unmount all volumes on this disk
            self.signals.status.emit("Unmounting volumes...")
            subprocess.run(f"diskutil unmountDisk {base_device}", shell=True)

            # Create a new GPT partition scheme
            self.signals.status.emit("Creating new partition scheme...")
            self.signals.progress.emit(10)

            # Erase the disk with GPT partition scheme
            erase_cmd = f"diskutil eraseDisk JHFS+ 'Install macOS' GPT {base_device}"
            subprocess.run(erase_cmd, shell=True, check=True)

            # Find the volume path
            self.signals.status.emit("Locating created volume...")
            self.signals.progress.emit(15)

            volume_info = subprocess.check_output("diskutil list", shell=True, text=True)
            volume_path = None

            for line in volume_info.splitlines():
                if "Install macOS" in line:
                    parts = line.split()
                    for part in parts:
                        if part.startswith("/dev/"):
                            volume_path = part
                            break
                    if volume_path:
                        break

            if not volume_path:
                self.signals.error.emit("Could not find the created volume")
                return

            # Create a temporary directory for downloads
            temp_dir = "/tmp/hackintosh_temp"
            os.makedirs(temp_dir, exist_ok=True)

            # Download OpenCore
            self.signals.status.emit("Downloading OpenCore bootloader...")
            self.signals.progress.emit(20)

            opencore_url = "https://github.com/acidanthera/OpenCorePkg/releases/download/0.9.5/OpenCore-0.9.5-RELEASE.zip"
            opencore_zip = os.path.join(temp_dir, "OpenCore.zip")

            download_cmd = f"curl -L {opencore_url} -o {opencore_zip}"
            subprocess.run(download_cmd, shell=True, check=True)

            # Extract OpenCore
            self.signals.status.emit("Extracting OpenCore...")
            self.signals.progress.emit(25)

            extract_cmd = f"unzip -q {opencore_zip} -d {temp_dir}"
            subprocess.run(extract_cmd, shell=True, check=True)

            # Create EFI partition
            self.signals.status.emit("Creating and mounting EFI partition...")
            self.signals.progress.emit(30)

            # Get the disk identifier (e.g., disk2)
            disk_id = base_device.split("/")[-1]

            # Create the EFI partition
            efi_cmd = f"diskutil addPartition {disk_id}s1 EFI FAT32 'EFI' 200M"
            subprocess.run(efi_cmd, shell=True, check=True)

            # Mount the EFI partition
            mount_cmd = f"diskutil mount {disk_id}s1"
            subprocess.run(mount_cmd, shell=True, check=True)

            # Copy OpenCore to EFI partition
            self.signals.status.emit("Copying OpenCore to EFI partition...")
            self.signals.progress.emit(35)

            # Create EFI directory structure
            os.makedirs("/Volumes/EFI/EFI", exist_ok=True)

            # Copy the X64 EFI folder for UEFI systems
            copy_cmd = f"cp -r {temp_dir}/X64/EFI/* /Volumes/EFI/EFI/"
            subprocess.run(copy_cmd, shell=True, check=True)

            # Download macOS
            self.signals.status.emit(f"Preparing to download {self.macos_version}...")
            self.signals.progress.emit(40)

            # Use createinstallmedia which is built into macOS
            # First, determine the installer path based on macOS version
            installer_app = self._get_macos_installer_path()

            # Check if the installer exists
            if not os.path.exists(installer_app):
                # Need to download the installer
                self.signals.status.emit(f"Downloading {self.macos_version} installer...")
                self.signals.progress.emit(45)

                # Use softwareupdate to download the installer
                macos_code = self._get_macos_version_code(for_softwareupdate=True)
                download_cmd = f"softwareupdate --fetch-full-installer --full-installer-version {macos_code}"

                process = subprocess.Popen(
                    download_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT
                )

                # Monitor the process
                while process.poll() is None:
                    if not self.is_running:
                        process.terminate()
                        break
                    time.sleep(1)
                    # Update progress (approximate)
                    self.signals.progress.emit(50)

            # Create the bootable installer
            self.signals.status.emit("Creating bootable installer (this may take a while)...")
            self.signals.progress.emit(60)

            create_cmd = f"sudo '{installer_app}/Contents/Resources/createinstallmedia' --volume /Volumes/Install\\ macOS --nointeraction"

            process = subprocess.Popen(
                create_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )

            # Monitor the process
            while process.poll() is None:
                if not self.is_running:
                    process.terminate()
                    break
                time.sleep(1)
                # Update progress (approximate)
                self.signals.progress.emit(70)

            # Configure OpenCore
            self.signals.status.emit("Configuring OpenCore...")
            self.signals.progress.emit(80)

            # Copy sample config to the correct location
            copy_cmd = f"cp {temp_dir}/Docs/Sample.plist /Volumes/EFI/EFI/OC/config.plist"
            subprocess.run(copy_cmd, shell=True, check=True)

            # Download ProperTree for config editing
            self.signals.status.emit("Downloading ProperTree...")
            self.signals.progress.emit(85)

            # Clone ProperTree repository
            clone_cmd = f"git clone --depth=1 https://github.com/corpnewt/ProperTree {temp_dir}/ProperTree"
            subprocess.run(clone_cmd, shell=True, check=True)

            # Copy ProperTree to the installer volume
            new_volume_name = f"Install macOS {self._get_macos_version_name()}"
            copy_cmd = f"cp -r {temp_dir}/ProperTree /Volumes/'{new_volume_name}'/"
            subprocess.run(copy_cmd, shell=True, check=True)

            # Create a README file with instructions
            self.signals.status.emit("Creating documentation...")
            self.signals.progress.emit(90)

            readme_content = f"""# Hackintosh USB for {self.macos_version}

## Contents
- OpenCore 0.9.5 bootloader
- macOS {self.macos_version} installer

## Next Steps
1. You need to customize the config.plist file for your specific hardware
2. Use ProperTree (included in the USB) to edit the config.plist on the EFI partition
3. Add necessary kexts for your hardware
4. Boot from this USB and follow the macOS installation process

## Resources
- OpenCore Install Guide: https://dortania.github.io/OpenCore-Install-Guide/
- Hackintosh Subreddit: https://www.reddit.com/r/hackintosh/
- OpenCore Discord: https://discord.gg/rV9AmXPd

Created with Ruuf USB Flasher
"""

            with open(f"/Volumes/'{new_volume_name}'/README.txt", 'w') as f:
                f.write(readme_content)

            # Clean up
            self.signals.status.emit("Finalizing...")
            self.signals.progress.emit(95)

            # Unmount volumes
            subprocess.run("diskutil unmount /Volumes/EFI", shell=True)

            # Remove temporary files
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return

    def _get_macos_version_code(self, for_softwareupdate=False):
        """Get the version code for the selected macOS version"""
        version_map = {
            "macOS Sonoma (14)": "14.0" if for_softwareupdate else "mac-os-sonoma",
            "macOS Ventura (13)": "13.0" if for_softwareupdate else "mac-os-ventura",
            "macOS Monterey (12)": "12.0" if for_softwareupdate else "mac-os-monterey",
            "macOS Big Sur (11)": "11.0" if for_softwareupdate else "mac-os-big-sur",
            "macOS Catalina (10.15)": "10.15" if for_softwareupdate else "mac-os-catalina",
            "macOS Mojave (10.14)": "10.14" if for_softwareupdate else "mac-os-mojave",
            "macOS High Sierra (10.13)": "10.13" if for_softwareupdate else "mac-os-high-sierra"
        }
        return version_map.get(self.macos_version, "latest")

    def _get_macos_version_name(self):
        """Get the short name for the selected macOS version"""
        version_map = {
            "macOS Sonoma (14)": "Sonoma",
            "macOS Ventura (13)": "Ventura",
            "macOS Monterey (12)": "Monterey",
            "macOS Big Sur (11)": "Big Sur",
            "macOS Catalina (10.15)": "Catalina",
            "macOS Mojave (10.14)": "Mojave",
            "macOS High Sierra (10.13)": "High Sierra"
        }
        return version_map.get(self.macos_version, "")

    def _get_macos_installer_path(self):
        """Get the path to the macOS installer app"""
        version_name = self._get_macos_version_name()
        return f"/Applications/Install macOS {version_name}.app"

    def stop(self):
        """Stop the creation process"""
        self.is_running = False
        
    def run(self):
        try:
            self.signals.status.emit("Preparing to flash...")
            self.signals.progress.emit(0)
            
            # Platform-specific commands
            if platform.system() == "Windows":
                self._flash_windows()
            elif platform.system() == "Linux":
                self._flash_linux()
            elif platform.system() == "Darwin":  # macOS
                self._flash_macos()
            else:
                self.signals.error.emit(f"Unsupported operating system: {platform.system()}")
                return
                
            self.signals.status.emit("Flash completed successfully!")
            self.signals.progress.emit(100)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(f"Error during flashing: {str(e)}")
    
    def _flash_windows(self):
        """Flash ISO to USB on Windows using PowerShell and DISM"""
        try:
            # Get drive letter from device path
            drive_letter = self.usb_device.split(':')[0]

            # Get disk number for the USB drive
            self.signals.status.emit("Identifying USB disk number...")
            self.signals.progress.emit(5)

            get_disk_cmd = f'powershell "Get-Disk | Where-Object {{$_.Bustype -eq \'USB\' -and (Get-Partition -DiskNumber $_.Number | Where-Object {{$_.DriveLetter -eq \'{drive_letter}\'}})}} | Select-Object -ExpandProperty Number"'
            disk_number = subprocess.check_output(get_disk_cmd, shell=True).decode().strip()

            if not disk_number:
                self.signals.error.emit(f"Could not find disk number for drive {drive_letter}:")
                return

            # Clean the disk and create a new partition table
            self.signals.status.emit(f"Cleaning disk {disk_number} and creating new partition table...")
            self.signals.progress.emit(10)

            # Use diskpart to clean the disk and create a new MBR partition
            diskpart_script = f"""select disk {disk_number}
clean
create partition primary
select partition 1
active
format fs=NTFS quick
assign letter={drive_letter}
exit"""

            # Write diskpart script to a temporary file
            script_path = os.path.join(os.environ.get('TEMP', '.'), 'diskpart_script.txt')
            with open(script_path, 'w') as f:
                f.write(diskpart_script)

            # Run diskpart with the script
            diskpart_cmd = f'diskpart /s "{script_path}"'
            subprocess.run(diskpart_cmd, shell=True, check=True)

            # Remove the temporary script file
            os.remove(script_path)

            # Make the USB bootable
            self.signals.status.emit("Making drive bootable...")
            self.signals.progress.emit(30)

            # Mount the ISO
            self.signals.status.emit("Mounting ISO image...")
            mount_cmd = f'powershell Mount-DiskImage -ImagePath "{self.iso_path}"'
            subprocess.run(mount_cmd, shell=True, check=True)

            # Get the mounted drive letter
            get_mount_cmd = f'powershell "(Get-DiskImage -ImagePath \'{self.iso_path}\' | Get-Volume).DriveLetter"'
            iso_drive = subprocess.check_output(get_mount_cmd, shell=True).decode().strip()

            # Check if the ISO contains a boot folder
            self.signals.status.emit("Checking ISO structure...")
            self.signals.progress.emit(35)

            # Copy files
            self.signals.status.emit("Copying files to USB drive...")
            self.signals.progress.emit(40)

            # Use robocopy for more reliable copying with long paths
            # /MIR mirrors the directory structure, /NFL no file list, /NDL no dir list
            copy_cmd = f'robocopy {iso_drive}:\\ {drive_letter}:\\ /E /NFL /NDL /COPY:DAT /R:1 /W:1'
            subprocess.run(copy_cmd, shell=True)

            # Make sure boot files are properly set up
            self.signals.status.emit("Setting up boot files...")
            self.signals.progress.emit(80)

            # Check if this is a Windows 10/11 ISO by looking for specific files
            if os.path.exists(f"{drive_letter}:\\sources\\boot.wim"):
                # For Windows 10/11 ISOs, ensure bootmgr is properly set up
                if os.path.exists(f"{iso_drive}:\\boot\\bootsect.exe"):
                    bootsect_cmd = f'{iso_drive}:\\boot\\bootsect.exe /nt60 {drive_letter}: /force /mbr'
                    subprocess.run(bootsect_cmd, shell=True)

            # Unmount the ISO
            self.signals.status.emit("Finalizing...")
            self.signals.progress.emit(90)

            unmount_cmd = f'powershell Dismount-DiskImage -ImagePath "{self.iso_path}"'
            subprocess.run(unmount_cmd, shell=True, check=True)

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return
    
    def _flash_linux(self):
        """Flash ISO to USB on Linux using dd or a hybrid approach"""
        try:
            # Ensure device path is correct (should be like /dev/sdb, not a partition)
            device = self.usb_device

            # Check if we need to unmount any existing partitions
            self.signals.status.emit("Checking for mounted partitions...")
            self.signals.progress.emit(5)

            # Get list of mounted partitions for this device
            check_mounts_cmd = f"mount | grep {device}"
            mounted_parts = subprocess.run(check_mounts_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if mounted_parts.stdout:
                self.signals.status.emit("Unmounting partitions...")
                # Unmount all partitions of the device
                if self.sudo_password:
                    unmount_cmd = f"echo '{self.sudo_password}' | sudo -S umount {device}*"
                else:
                    unmount_cmd = f"sudo umount {device}*"
                subprocess.run(unmount_cmd, shell=True, stderr=subprocess.PIPE)

            # Check if this is a Windows ISO by trying to mount it
            self.signals.status.emit("Analyzing ISO file...")
            self.signals.progress.emit(8)

            # Create a temporary mount point
            temp_mount = "/tmp/iso_check"
            os.makedirs(temp_mount, exist_ok=True)

            # Try to mount the ISO
            if self.sudo_password:
                mount_iso_cmd = f"echo '{self.sudo_password}' | sudo -S mount -o loop '{self.iso_path}' {temp_mount}"
            else:
                mount_iso_cmd = f"sudo mount -o loop '{self.iso_path}' {temp_mount}"
            mount_result = subprocess.run(mount_iso_cmd, shell=True, stderr=subprocess.PIPE)

            is_windows_iso = False
            hybrid_method = False

            if mount_result.returncode == 0:
                # Check for Windows-specific directories
                if os.path.exists(f"{temp_mount}/sources") or os.path.exists(f"{temp_mount}/boot"):
                    is_windows_iso = True

                    # Check if we should use a hybrid method (for UEFI boot support)
                    if os.path.exists(f"{temp_mount}/efi") or os.path.exists(f"{temp_mount}/EFI"):
                        hybrid_method = True

                # Unmount the ISO
                if self.sudo_password:
                    subprocess.run(f"echo '{self.sudo_password}' | sudo -S umount {temp_mount}", shell=True)
                else:
                    subprocess.run(f"sudo umount {temp_mount}", shell=True)

            # Remove the temporary mount point
            try:
                os.rmdir(temp_mount)
            except:
                pass

            if hybrid_method:
                # For Windows ISOs with UEFI support, we'll use a hybrid approach
                self._flash_linux_hybrid(device)
            else:
                # Standard dd method for direct ISO writing
                self._flash_linux_dd(device)

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return

    def _flash_linux_dd(self, device):
        """Use dd to directly write the ISO to the USB drive"""
        try:
            self.signals.status.emit(f"Writing ISO to {device} using dd...")
            self.signals.progress.emit(10)

            # Get total size for progress calculation
            total_size = os.path.getsize(self.iso_path)
            block_size = 4 * 1024 * 1024  # 4MB blocks

            # Use dd with status=progress to get real-time progress
            if self.sudo_password:
                cmd = f"echo '{self.sudo_password}' | sudo -S dd if='{self.iso_path}' of='{device}' bs={block_size} status=progress"
            else:
                cmd = f"sudo dd if='{self.iso_path}' of='{device}' bs={block_size} status=progress"

            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )

            # Monitor progress
            for line in iter(process.stdout.readline, ''):
                if not self.is_running:
                    process.terminate()
                    break

                if "bytes" in line:
                    try:
                        # Extract bytes written
                        bytes_written = int(line.split()[0])
                        progress = min(int(bytes_written / total_size * 90), 90)
                        self.signals.progress.emit(progress)
                        self.signals.status.emit(f"Writing: {bytes_written/1024/1024:.2f} MB of {total_size/1024/1024:.2f} MB")
                    except (ValueError, IndexError):
                        pass

            process.wait()
            if process.returncode != 0:
                self.signals.error.emit("dd command failed")
                return

            # Sync to ensure all writes are complete
            self.signals.status.emit("Syncing writes to disk...")
            self.signals.progress.emit(95)
            subprocess.run("sync", shell=True, check=True)

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return

    def _flash_linux_hybrid(self, device):
        """Create a bootable Windows USB with proper partitioning for UEFI support"""
        try:
            # Step 1: Create a new partition table
            self.signals.status.emit("Creating new partition table...")
            self.signals.progress.emit(10)

            # Create a GPT partition table for UEFI support
            parted_cmd = f"sudo parted -s {device} mklabel gpt"
            subprocess.run(parted_cmd, shell=True, check=True)

            # Step 2: Create an EFI System Partition (ESP)
            self.signals.status.emit("Creating EFI System Partition...")
            self.signals.progress.emit(15)

            # Create a 200MB EFI partition
            parted_cmd = f"sudo parted -s {device} mkpart primary fat32 1MiB 201MiB"
            subprocess.run(parted_cmd, shell=True, check=True)

            # Set the ESP flag
            parted_cmd = f"sudo parted -s {device} set 1 esp on"
            subprocess.run(parted_cmd, shell=True, check=True)

            # Step 3: Create a main data partition
            self.signals.status.emit("Creating main data partition...")
            self.signals.progress.emit(20)

            parted_cmd = f"sudo parted -s {device} mkpart primary ntfs 201MiB 100%"
            subprocess.run(parted_cmd, shell=True, check=True)

            # Step 4: Format the partitions
            self.signals.status.emit("Formatting partitions...")
            self.signals.progress.emit(25)

            # Wait for the system to recognize the new partitions
            time.sleep(2)

            # Get the partition names
            esp_part = f"{device}1"
            main_part = f"{device}2"

            # Format ESP as FAT32
            format_cmd = f"sudo mkfs.fat -F32 {esp_part}"
            subprocess.run(format_cmd, shell=True, check=True)

            # Format main partition as NTFS
            format_cmd = f"sudo mkfs.ntfs -f {main_part}"
            subprocess.run(format_cmd, shell=True, check=True)

            # Step 5: Mount the ISO and partitions
            self.signals.status.emit("Mounting ISO and partitions...")
            self.signals.progress.emit(30)

            # Create mount points
            iso_mount = "/tmp/iso_mount"
            esp_mount = "/tmp/esp_mount"
            main_mount = "/tmp/main_mount"

            os.makedirs(iso_mount, exist_ok=True)
            os.makedirs(esp_mount, exist_ok=True)
            os.makedirs(main_mount, exist_ok=True)

            # Mount the ISO
            mount_cmd = f"sudo mount -o loop '{self.iso_path}' {iso_mount}"
            subprocess.run(mount_cmd, shell=True, check=True)

            # Mount the partitions
            mount_cmd = f"sudo mount {esp_part} {esp_mount}"
            subprocess.run(mount_cmd, shell=True, check=True)

            mount_cmd = f"sudo mount {main_part} {main_mount}"
            subprocess.run(mount_cmd, shell=True, check=True)

            # Step 6: Copy EFI files
            self.signals.status.emit("Copying EFI files...")
            self.signals.progress.emit(40)

            # Check if the ISO has an EFI directory
            efi_source = None
            for efi_dir in ["efi", "EFI"]:
                if os.path.exists(f"{iso_mount}/{efi_dir}"):
                    efi_source = f"{iso_mount}/{efi_dir}"
                    break

            if efi_source:
                # Copy EFI files
                copy_cmd = f"sudo cp -r {efi_source} {esp_mount}/"
                subprocess.run(copy_cmd, shell=True, check=True)
            else:
                self.signals.status.emit("Warning: No EFI directory found in ISO")

            # Step 7: Copy all files to the main partition
            self.signals.status.emit("Copying Windows files...")
            self.signals.progress.emit(50)

            copy_cmd = f"sudo cp -r {iso_mount}/* {main_mount}/"
            subprocess.run(copy_cmd, shell=True, check=True)

            # Step 8: Unmount everything
            self.signals.status.emit("Finalizing...")
            self.signals.progress.emit(90)

            # Unmount in reverse order
            subprocess.run(f"sudo umount {main_mount}", shell=True)
            subprocess.run(f"sudo umount {esp_mount}", shell=True)
            subprocess.run(f"sudo umount {iso_mount}", shell=True)

            # Remove mount points
            try:
                os.rmdir(main_mount)
                os.rmdir(esp_mount)
                os.rmdir(iso_mount)
            except:
                pass

            # Sync to ensure all writes are complete
            self.signals.status.emit("Syncing writes to disk...")
            self.signals.progress.emit(95)
            subprocess.run("sync", shell=True, check=True)

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return
    
    def _flash_macos(self):
        """Flash ISO to USB on macOS using a hybrid approach for Windows ISOs"""
        try:
            # Get the base device (e.g., /dev/disk2)
            base_device = self.usb_device

            # Check if any volumes from this device are mounted
            self.signals.status.emit("Checking for mounted volumes...")
            self.signals.progress.emit(5)

            # Get information about the disk
            diskutil_info = subprocess.check_output(f"diskutil list {base_device}", shell=True, text=True)

            # Unmount all volumes on this disk
            self.signals.status.emit("Unmounting volumes...")
            subprocess.run(f"diskutil unmountDisk {base_device}", shell=True)

            # Check if this is a Windows ISO by mounting it
            self.signals.status.emit("Analyzing ISO file...")
            self.signals.progress.emit(8)

            # Create a temporary mount point
            temp_dir = "/tmp/iso_check"
            os.makedirs(temp_dir, exist_ok=True)

            # Mount the ISO
            mount_cmd = f"hdiutil mount '{self.iso_path}' -mountpoint {temp_dir}"
            mount_result = subprocess.run(mount_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            is_windows_iso = False
            has_efi = False

            if mount_result.returncode == 0:
                # Check for Windows-specific directories
                if os.path.exists(f"{temp_dir}/sources") or os.path.exists(f"{temp_dir}/boot"):
                    is_windows_iso = True

                    # Check for EFI support
                    if os.path.exists(f"{temp_dir}/efi") or os.path.exists(f"{temp_dir}/EFI"):
                        has_efi = True

                # Unmount the ISO
                subprocess.run(f"hdiutil unmount {temp_dir}", shell=True)

            # Remove the temporary directory
            try:
                os.rmdir(temp_dir)
            except:
                pass

            if is_windows_iso and has_efi:
                # For Windows ISOs with UEFI support, use the hybrid approach
                self._flash_macos_hybrid(base_device)
            else:
                # For other ISOs or Windows ISOs without UEFI, use direct dd
                self._flash_macos_dd(base_device)

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return

    def _flash_macos_dd(self, device):
        """Use dd to directly write the ISO to the USB drive on macOS"""
        try:
            # Convert /dev/diskX to /dev/rdiskX for faster writes
            if device.startswith("/dev/disk"):
                raw_device = device.replace("/dev/disk", "/dev/rdisk")
            else:
                raw_device = device

            # Use dd to write the ISO to the USB drive
            self.signals.status.emit(f"Writing ISO to {raw_device}...")
            self.signals.progress.emit(10)

            # Get total size for progress calculation
            total_size = os.path.getsize(self.iso_path)
            block_size = 4 * 1024 * 1024  # 4MB blocks

            # Use dd command
            cmd = f"sudo dd if='{self.iso_path}' of='{raw_device}' bs={block_size}"

            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )

            # Since macOS dd doesn't show progress, we'll check the disk usage periodically
            start_time = time.time()
            while process.poll() is None:
                if not self.is_running:
                    process.terminate()
                    break

                # Update progress based on time (approximate)
                elapsed = time.time() - start_time
                # Assume it takes roughly 5 minutes to write a typical ISO
                progress = min(int(elapsed / 300 * 90), 90)
                self.signals.progress.emit(progress)
                self.signals.status.emit(f"Writing ISO... (approximately {progress}%)")
                time.sleep(2)

            if process.returncode != 0:
                self.signals.error.emit("dd command failed")
                return

            # Sync to ensure all writes are complete
            self.signals.status.emit("Syncing writes to disk...")
            self.signals.progress.emit(95)
            subprocess.run("sync", shell=True, check=True)

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return

    def _flash_macos_hybrid(self, device):
        """Create a bootable Windows USB with proper partitioning for UEFI support on macOS"""
        try:
            # Step 1: Erase the disk and create a GPT partition scheme
            self.signals.status.emit("Creating new partition scheme...")
            self.signals.progress.emit(10)

            # Erase the disk with GPT partition scheme
            erase_cmd = f"diskutil eraseDisk MS-DOS WINUSB GPT {device}"
            subprocess.run(erase_cmd, shell=True, check=True)

            # Step 2: Get the new volume path
            self.signals.status.emit("Locating created volume...")
            self.signals.progress.emit(15)

            # Find the volume path
            volume_info = subprocess.check_output("diskutil list", shell=True, text=True)
            volume_path = None

            for line in volume_info.splitlines():
                if "WINUSB" in line:
                    parts = line.split()
                    for part in parts:
                        if part.startswith("/dev/"):
                            volume_path = part
                            break
                    if volume_path:
                        break

            if not volume_path:
                self.signals.error.emit("Could not find the created volume")
                return

            # Step 3: Mount the ISO
            self.signals.status.emit("Mounting ISO image...")
            self.signals.progress.emit(20)

            # Create a temporary mount point
            iso_mount = "/tmp/iso_mount"
            os.makedirs(iso_mount, exist_ok=True)

            # Mount the ISO
            mount_cmd = f"hdiutil mount '{self.iso_path}' -mountpoint {iso_mount}"
            subprocess.run(mount_cmd, shell=True, check=True)

            # Step 4: Get the volume mount point
            volume_mount = "/Volumes/WINUSB"

            # Step 5: Copy all files from ISO to USB
            self.signals.status.emit("Copying files to USB drive...")
            self.signals.progress.emit(30)

            # Use ditto for reliable copying with resource forks and metadata
            copy_cmd = f"sudo ditto -rsrc {iso_mount}/ {volume_mount}/"

            process = subprocess.Popen(
                copy_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )

            # Since ditto doesn't show progress, we'll update based on time
            start_time = time.time()
            while process.poll() is None:
                if not self.is_running:
                    process.terminate()
                    break

                # Update progress based on time (approximate)
                elapsed = time.time() - start_time
                # Assume it takes roughly 3 minutes to copy files
                progress = min(30 + int(elapsed / 180 * 60), 90)
                self.signals.progress.emit(progress)
                self.signals.status.emit(f"Copying files... (approximately {progress-30}% complete)")
                time.sleep(1)

            if process.returncode != 0:
                self.signals.error.emit("File copying failed")
                return

            # Step 6: Make the drive bootable
            self.signals.status.emit("Making drive bootable...")
            self.signals.progress.emit(90)

            # Check if the ISO contains boot files
            if os.path.exists(f"{iso_mount}/boot") or os.path.exists(f"{iso_mount}/Boot"):
                # The files are already copied in the previous step
                pass

            # Step 7: Clean up
            self.signals.status.emit("Finalizing...")
            self.signals.progress.emit(95)

            # Unmount the ISO
            subprocess.run(f"hdiutil unmount {iso_mount}", shell=True)

            # Remove the temporary mount point
            try:
                os.rmdir(iso_mount)
            except:
                pass

            # Eject the USB drive
            subprocess.run(f"diskutil eject {device}", shell=True)

        except subprocess.CalledProcessError as e:
            self.signals.error.emit(f"Command failed: {str(e)}")
            return
    
    def stop(self):
        """Stop the flashing process"""
        self.is_running = False


class USBFlasherApp(QMainWindow):
    """
    Main application window
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ruuf USB Flasher")
        self.setMinimumSize(600, 400)

        self.iso_path = ""
        self.linux_iso_path = ""
        self.usb_devices = []
        self.selected_device = ""
        self.flash_worker = None
        self.refresh_timer = None
        self.current_mode = "windows"  # Default mode: windows, hackintosh, or linux

        self.init_ui()
        self.refresh_usb_devices()

        # Set up a timer to refresh USB devices every 5 seconds
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_usb_devices)
        self.refresh_timer.start(5000)  # 5 seconds
    
    def init_ui(self):
        """Initialize the user interface"""
        # Create menu bar
        self.create_menu_bar()

        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Title
        title_label = QLabel("Ruuf USB Flasher")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)

        # Description
        desc_label = QLabel("Flash Windows ISO images and create Hackintosh USB drives")
        desc_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(desc_label)
        
        # Mode Selection Group
        mode_group = QGroupBox("Operation Mode")
        mode_layout = QHBoxLayout()
        mode_group.setLayout(mode_layout)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Windows ISO Flasher")
        self.mode_combo.addItem("Hackintosh Creator")
        self.mode_combo.addItem("Linux Distribution")
        self.mode_combo.currentIndexChanged.connect(self.mode_changed)
        mode_layout.addWidget(self.mode_combo)

        main_layout.addWidget(mode_group)

        # ISO Selection Group
        iso_group = QGroupBox("ISO Image / macOS Version")
        iso_layout = QHBoxLayout()
        iso_group.setLayout(iso_layout)

        self.iso_path_label = QLabel("No ISO selected")
        iso_layout.addWidget(self.iso_path_label, 1)

        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_iso)
        iso_layout.addWidget(self.browse_button)

        # macOS Version Selection (initially hidden)
        self.macos_combo = QComboBox()
        self.macos_combo.addItem("macOS Monterey (12)")
        self.macos_combo.addItem("macOS Ventura (13)")
        self.macos_combo.addItem("macOS Sonoma (14)")
        self.macos_combo.addItem("macOS Big Sur (11)")
        self.macos_combo.addItem("macOS Catalina (10.15)")
        self.macos_combo.addItem("macOS Mojave (10.14)")
        self.macos_combo.addItem("macOS High Sierra (10.13)")
        self.macos_combo.hide()
        iso_layout.addWidget(self.macos_combo)

        # Linux Distribution Selection (initially hidden)
        self.linux_combo = QComboBox()
        self.linux_combo.addItem("Ubuntu 22.04 LTS")
        self.linux_combo.addItem("Ubuntu 23.10")
        self.linux_combo.addItem("Linux Mint 21.2")
        self.linux_combo.addItem("Debian 12")
        self.linux_combo.addItem("Fedora 39")
        self.linux_combo.addItem("Pop!_OS 22.04")
        self.linux_combo.addItem("Manjaro")
        self.linux_combo.addItem("Arch Linux")
        self.linux_combo.addItem("Kali Linux")
        self.linux_combo.addItem("Elementary OS 7")
        self.linux_combo.addItem("Zorin OS 17")
        self.linux_combo.addItem("Other (Custom ISO)")
        self.linux_combo.hide()
        iso_layout.addWidget(self.linux_combo)

        # Browse button for Linux custom ISO (initially hidden)
        self.linux_browse_button = QPushButton("Browse ISO")
        self.linux_browse_button.clicked.connect(self.browse_linux_iso)
        self.linux_browse_button.hide()
        iso_layout.addWidget(self.linux_browse_button)

        main_layout.addWidget(iso_group)
        
        # USB Device Selection Group
        usb_group = QGroupBox("USB Drive")
        usb_layout = QHBoxLayout()
        usb_group.setLayout(usb_layout)
        
        self.usb_combo = QComboBox()
        usb_layout.addWidget(self.usb_combo, 1)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_usb_devices)
        usb_layout.addWidget(self.refresh_button)
        
        main_layout.addWidget(usb_group)
        
        # Warning Label
        warning_label = QLabel("⚠️ WARNING: All data on the selected USB drive will be erased!")
        warning_label.setStyleSheet("color: red; font-weight: bold;")
        warning_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(warning_label)
        
        # Progress Group
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        progress_group.setLayout(progress_layout)
        
        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        main_layout.addWidget(progress_group)
        
        # Action Buttons
        button_layout = QHBoxLayout()
        
        self.flash_button = QPushButton("Flash USB")
        self.flash_button.clicked.connect(self.start_flashing)
        button_layout.addWidget(self.flash_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_flashing)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        
        # Status bar
        self.statusBar().showMessage("Select an ISO file and USB drive to begin")
    
    def mode_changed(self, index):
        """Handle mode selection change"""
        if index == 0:  # Windows ISO Flasher
            self.current_mode = "windows"
            self.iso_path_label.show()
            self.browse_button.show()
            self.macos_combo.hide()
            self.linux_combo.hide()
            self.linux_browse_button.hide()
            self.iso_path_label.setText("No ISO selected" if not self.iso_path else os.path.basename(self.iso_path))
            self.statusBar().showMessage("Windows ISO Flasher mode selected")
        elif index == 1:  # Hackintosh Creator
            self.current_mode = "hackintosh"
            self.iso_path_label.hide()
            self.browse_button.hide()
            self.macos_combo.show()
            self.linux_combo.hide()
            self.linux_browse_button.hide()
            self.statusBar().showMessage("Hackintosh Creator mode selected")
        else:  # Linux Distribution
            self.current_mode = "linux"
            self.iso_path_label.hide()
            self.browse_button.hide()
            self.macos_combo.hide()
            self.linux_combo.show()

            # Show the browse button only if "Other (Custom ISO)" is selected
            if self.linux_combo.currentText() == "Other (Custom ISO)":
                self.linux_browse_button.show()
            else:
                self.linux_browse_button.hide()

            self.statusBar().showMessage("Linux Distribution mode selected")

        # Connect the Linux combo box change event
        self.linux_combo.currentIndexChanged.connect(self.linux_distro_changed)

    def linux_distro_changed(self, index):
        """Handle Linux distribution selection change"""
        selected_distro = self.linux_combo.currentText()

        # Show the browse button only if "Other (Custom ISO)" is selected
        if selected_distro == "Other (Custom ISO)":
            self.linux_browse_button.show()
        else:
            self.linux_browse_button.hide()
            self.linux_iso_path = ""  # Reset custom ISO path

        self.statusBar().showMessage(f"Selected Linux distribution: {selected_distro}")

    def browse_linux_iso(self):
        """Open file dialog to select a Linux ISO file"""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Select Linux ISO", "", "ISO Files (*.iso)"
        )

        if file_path:
            self.linux_iso_path = file_path
            self.statusBar().showMessage(f"Selected Linux ISO: {os.path.basename(file_path)}")

    def browse_iso(self):
        """Open file dialog to select an ISO file"""
        if self.current_mode == "windows":
            file_dialog = QFileDialog()
            file_path, _ = file_dialog.getOpenFileName(
                self, "Select Windows ISO", "", "ISO Files (*.iso)"
            )

            if file_path:
                self.iso_path = file_path
                # Show only the filename, not the full path
                self.iso_path_label.setText(os.path.basename(file_path))
                self.statusBar().showMessage(f"Selected ISO: {os.path.basename(file_path)}")
    
    def refresh_usb_devices(self):
        """Refresh the list of available USB devices"""
        current_selection = self.usb_combo.currentText()
        self.usb_combo.clear()
        self.usb_devices = []
        
        if platform.system() == "Windows":
            self._get_windows_usb_devices()
        elif platform.system() == "Linux":
            self._get_linux_usb_devices()
        elif platform.system() == "Darwin":  # macOS
            self._get_macos_usb_devices()
        
        # Restore previous selection if it still exists
        if current_selection:
            index = self.usb_combo.findText(current_selection)
            if index >= 0:
                self.usb_combo.setCurrentIndex(index)
    
    def _get_windows_usb_devices(self):
        """Get list of USB devices on Windows"""
        try:
            # PowerShell command to get removable drives
            cmd = 'powershell "Get-Disk | Where-Object {$_.BusType -eq \'USB\'} | ForEach-Object { Get-Partition -DiskNumber $_.Number | Get-Volume | Select-Object -Property DriveLetter, SizeRemaining, Size, FileSystemLabel | ForEach-Object { $_.DriveLetter + \': \' + $_.FileSystemLabel + \' (\' + [math]::Round($_.Size/1GB, 2) + \' GB)\' } }"'
            
            result = subprocess.check_output(cmd, shell=True).decode().strip()
            
            if result:
                for drive in result.split('\n'):
                    drive = drive.strip()
                    if drive:
                        self.usb_devices.append(drive.split()[0])  # Get drive letter with colon
                        self.usb_combo.addItem(drive)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to get USB devices: {str(e)}")
    
    def _get_linux_usb_devices(self):
        """Get list of USB devices on Linux"""
        try:
            # Get list of removable devices
            cmd = "lsblk -d -o NAME,SIZE,MODEL,TRAN -J"
            result = subprocess.check_output(cmd, shell=True).decode()
            
            import json
            devices = json.loads(result)
            
            for device in devices.get("blockdevices", []):
                # Only include USB devices and exclude internal drives
                if device.get("tran") == "usb":
                    device_name = f"/dev/{device['name']}"
                    device_info = f"{device_name} ({device['size']}, {device.get('model', 'USB Drive')})"
                    self.usb_devices.append(device_name)
                    self.usb_combo.addItem(device_info)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to get USB devices: {str(e)}")
    
    def _get_macos_usb_devices(self):
        """Get list of USB devices on macOS"""
        try:
            # Get list of external, removable media
            cmd = "diskutil list external physical | grep -v 'virtual' | grep 'disk' | awk '{print $1}'"
            result = subprocess.check_output(cmd, shell=True).decode()
            
            for device in result.splitlines():
                device = device.strip()
                if device and not device.endswith('s1'):  # Exclude partitions
                    # Get more info about the device
                    info_cmd = f"diskutil info {device} | grep 'Device / Media Name\\|Total Size'"
                    info = subprocess.check_output(info_cmd, shell=True).decode()
                    
                    size = "Unknown size"
                    name = "USB Drive"
                    
                    for line in info.splitlines():
                        if "Total Size" in line:
                            size = line.split(':')[1].strip()
                        elif "Device / Media Name" in line:
                            name = line.split(':')[1].strip()
                    
                    device_info = f"{device} ({size}, {name})"
                    self.usb_devices.append(device)
                    self.usb_combo.addItem(device_info)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to get USB devices: {str(e)}")
    
    def start_flashing(self):
        """Start the flashing process"""
        if self.current_mode == "windows":
            self._start_windows_flashing()
        elif self.current_mode == "hackintosh":
            self._start_hackintosh_creation()
        else:
            self._start_linux_creation()

    def _start_windows_flashing(self):
        """Start the Windows ISO flashing process"""
        if not self.iso_path:
            QMessageBox.warning(self, "Error", "Please select an ISO file first")
            return

        if self.usb_combo.count() == 0:
            QMessageBox.warning(self, "Error", "No USB drives detected")
            return

        # Get the selected USB device
        selected_index = self.usb_combo.currentIndex()
        if selected_index < 0 or selected_index >= len(self.usb_devices):
            QMessageBox.warning(self, "Error", "Please select a valid USB drive")
            return

        self.selected_device = self.usb_devices[selected_index]

        # Confirm with the user
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"You are about to erase ALL DATA on {self.usb_combo.currentText()}")
        msg.setInformativeText("This operation cannot be undone. Do you want to continue?")
        msg.setWindowTitle("Confirm USB Flash")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        if msg.exec_() != QMessageBox.Yes:
            return

        # Disable UI elements during flashing
        self.mode_combo.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.flash_button.setEnabled(False)
        self.usb_combo.setEnabled(False)
        self.cancel_button.setEnabled(True)

        # Reset progress
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting Windows ISO flashing...")

        # If on Linux, inform the user we'll use dd for direct writing
        if platform.system() == "Linux":
            info_msg = QMessageBox()
            info_msg.setIcon(QMessageBox.Information)
            info_msg.setText("On Linux, we'll use 'dd' for direct ISO writing")
            info_msg.setInformativeText("This is the most reliable method for creating bootable USB drives on Linux.")
            info_msg.setWindowTitle("Using dd Method")
            info_msg.setStandardButtons(QMessageBox.Ok)
            info_msg.exec_()

        # Start the flashing process in a separate thread
        self.flash_worker = FlashWorker(self.iso_path, self.selected_device)
        self.flash_worker.signals.progress.connect(self.update_progress)
        self.flash_worker.signals.status.connect(self.update_status)
        self.flash_worker.signals.finished.connect(self.flashing_finished)
        self.flash_worker.signals.error.connect(self.flashing_error)

        # Check if we're on Linux and might need a password
        if platform.system() == "Linux":
            # Ask for sudo password
            password_dialog = PasswordDialog(self)
            if password_dialog.exec_() == QDialog.Accepted:
                self.flash_worker.sudo_password = password_dialog.get_password()

        self.flash_worker.start()

    def _start_hackintosh_creation(self):
        """Start the Hackintosh USB creation process"""
        if self.usb_combo.count() == 0:
            QMessageBox.warning(self, "Error", "No USB drives detected")
            return

        # Get the selected USB device
        selected_index = self.usb_combo.currentIndex()
        if selected_index < 0 or selected_index >= len(self.usb_devices):
            QMessageBox.warning(self, "Error", "Please select a valid USB drive")
            return

        self.selected_device = self.usb_devices[selected_index]

        # Get the selected macOS version
        macos_version = self.macos_combo.currentText()

        # Confirm with the user
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"You are about to create a Hackintosh USB for {macos_version} on {self.usb_combo.currentText()}")
        msg.setInformativeText("This will erase ALL DATA on the selected USB drive. This operation cannot be undone. Do you want to continue?")
        msg.setWindowTitle("Confirm Hackintosh USB Creation")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        if msg.exec_() != QMessageBox.Yes:
            return

        # Disable UI elements during creation
        self.mode_combo.setEnabled(False)
        self.macos_combo.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.flash_button.setEnabled(False)
        self.usb_combo.setEnabled(False)
        self.cancel_button.setEnabled(True)

        # Reset progress
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Starting Hackintosh USB creation for {macos_version}...")

        # Start the creation process in a separate thread
        self.flash_worker = HackintoshWorker(macos_version, self.selected_device)
        self.flash_worker.signals.progress.connect(self.update_progress)
        self.flash_worker.signals.status.connect(self.update_status)
        self.flash_worker.signals.finished.connect(self.flashing_finished)
        self.flash_worker.signals.error.connect(self.flashing_error)

        # Check if we're on Linux and might need a password
        if platform.system() == "Linux":
            # Ask for sudo password
            password_dialog = PasswordDialog(self)
            if password_dialog.exec_() == QDialog.Accepted:
                self.flash_worker.sudo_password = password_dialog.get_password()

        self.flash_worker.start()
    
    def cancel_flashing(self):
        """Cancel the flashing process"""
        if self.flash_worker and self.flash_worker.is_alive():
            self.flash_worker.stop()
            self.status_label.setText("Cancelling...")
    
    def update_progress(self, value):
        """Update the progress bar"""
        self.progress_bar.setValue(value)
    
    def update_status(self, message):
        """Update the status label"""
        self.status_label.setText(message)
        self.statusBar().showMessage(message)
    
    def _start_linux_creation(self):
        """Start the Linux USB creation process"""
        if self.usb_combo.count() == 0:
            QMessageBox.warning(self, "Error", "No USB drives detected")
            return

        # Get the selected USB device
        selected_index = self.usb_combo.currentIndex()
        if selected_index < 0 or selected_index >= len(self.usb_devices):
            QMessageBox.warning(self, "Error", "Please select a valid USB drive")
            return

        self.selected_device = self.usb_devices[selected_index]

        # Get the selected Linux distribution
        linux_distro = self.linux_combo.currentText()

        # Check if we need a custom ISO for "Other" option
        if linux_distro == "Other (Custom ISO)" and not self.linux_iso_path:
            QMessageBox.warning(self, "Error", "Please select a Linux ISO file")
            return

        # Confirm with the user
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"You are about to create a {linux_distro} USB on {self.usb_combo.currentText()}")
        msg.setInformativeText("This will erase ALL DATA on the selected USB drive. This operation cannot be undone. Do you want to continue?")
        msg.setWindowTitle("Confirm Linux USB Creation")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        if msg.exec_() != QMessageBox.Yes:
            return

        # Disable UI elements during creation
        self.mode_combo.setEnabled(False)
        self.linux_combo.setEnabled(False)
        self.linux_browse_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.flash_button.setEnabled(False)
        self.usb_combo.setEnabled(False)
        self.cancel_button.setEnabled(True)

        # Reset progress
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Starting {linux_distro} USB creation...")

        # Start the creation process in a separate thread
        self.flash_worker = LinuxWorker(linux_distro, self.linux_iso_path, self.selected_device)
        self.flash_worker.signals.progress.connect(self.update_progress)
        self.flash_worker.signals.status.connect(self.update_status)
        self.flash_worker.signals.finished.connect(self.flashing_finished)
        self.flash_worker.signals.error.connect(self.flashing_error)

        # Check if we're on Linux and might need a password
        if platform.system() == "Linux":
            # Ask for sudo password
            password_dialog = PasswordDialog(self)
            if password_dialog.exec_() == QDialog.Accepted:
                self.flash_worker.sudo_password = password_dialog.get_password()

        self.flash_worker.start()

    def flashing_finished(self):
        """Called when flashing is complete"""
        self.progress_bar.setValue(100)

        if self.current_mode == "windows":
            self.status_label.setText("Flash completed successfully!")
            self.statusBar().showMessage("Flash completed successfully!")
            success_message = "USB flash completed successfully!"
        elif self.current_mode == "hackintosh":
            self.status_label.setText("Hackintosh USB created successfully!")
            self.statusBar().showMessage("Hackintosh USB created successfully!")
            success_message = "Hackintosh USB created successfully!"
        else:
            linux_distro = self.linux_combo.currentText()
            self.status_label.setText(f"{linux_distro} USB created successfully!")
            self.statusBar().showMessage(f"{linux_distro} USB created successfully!")
            success_message = f"{linux_distro} USB created successfully!"

        # Re-enable UI elements
        self.mode_combo.setEnabled(True)
        if self.current_mode == "windows":
            self.browse_button.setEnabled(True)
        else:
            self.macos_combo.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.flash_button.setEnabled(True)
        self.usb_combo.setEnabled(True)
        self.cancel_button.setEnabled(False)

        QMessageBox.information(self, "Success", success_message)
    
    def flashing_error(self, error_message):
        """Called when an error occurs during flashing"""
        self.status_label.setText(f"Error: {error_message}")
        self.statusBar().showMessage(f"Error: {error_message}")

        # Re-enable UI elements
        self.mode_combo.setEnabled(True)
        if self.current_mode == "windows":
            self.browse_button.setEnabled(True)
        elif self.current_mode == "hackintosh":
            self.macos_combo.setEnabled(True)
        else:  # Linux
            self.linux_combo.setEnabled(True)
            if self.linux_combo.currentText() == "Other (Custom ISO)":
                self.linux_browse_button.setEnabled(True)

        self.refresh_button.setEnabled(True)
        self.flash_button.setEnabled(True)
        self.usb_combo.setEnabled(True)
        self.cancel_button.setEnabled(False)

        if self.current_mode == "windows":
            operation = "flashing"
        elif self.current_mode == "hackintosh":
            operation = "creating Hackintosh USB"
        else:
            operation = f"creating {self.linux_combo.currentText()} USB"

        QMessageBox.critical(self, "Error", f"An error occurred during {operation}:\n{error_message}")
    
    def create_menu_bar(self):
        """Create the application menu bar"""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")

        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu = menu_bar.addMenu("Tools")

        # Secure Boot utility action
        secure_boot_action = QAction("Secure Boot Utility", self)
        secure_boot_action.triggered.connect(self.launch_secure_boot_utility)
        tools_menu.addAction(secure_boot_action)

        # Help menu
        help_menu = menu_bar.addMenu("Help")

        # About action
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def launch_secure_boot_utility(self):
        """Launch the Secure Boot utility"""
        try:
            # Check if secure_boot_utility.py exists
            if os.path.exists(os.path.join(os.path.dirname(__file__), "secure_boot_utility.py")):
                # Import the module
                spec = importlib.util.spec_from_file_location(
                    "secure_boot_utility",
                    os.path.join(os.path.dirname(__file__), "secure_boot_utility.py")
                )
                secure_boot_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(secure_boot_module)

                # Create and show the Secure Boot utility window
                self.secure_boot_window = secure_boot_module.SecureBootUtility()
                self.secure_boot_window.show()
            else:
                QMessageBox.warning(
                    self,
                    "Missing Component",
                    "The Secure Boot utility component is missing. Please reinstall the application."
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to launch Secure Boot utility: {str(e)}"
            )

    def show_about(self):
        """Show the about dialog"""
        QMessageBox.about(
            self,
            "About Ruuf USB Flasher",
            """<h3>Ruuf USB Flasher</h3>
            <p>Version 1.0</p>
            <p>A simple utility to flash Windows ISO images to USB drives.</p>
            <p>Features:</p>
            <ul>
                <li>Cross-platform support (Windows, macOS, Linux)</li>
                <li>Automatic USB device detection</li>
                <li>Secure Boot utility</li>
            </ul>
            <p>&copy; 2023 Ruuf USB Flasher Team</p>"""
        )

    def closeEvent(self, event):
        """Handle application close event"""
        if self.flash_worker and self.flash_worker.is_alive():
            # Ask for confirmation before closing
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("A flashing operation is in progress.")
            msg.setInformativeText("Are you sure you want to quit? This will cancel the operation.")
            msg.setWindowTitle("Confirm Exit")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.No)

            if msg.exec_() == QMessageBox.Yes:
                self.flash_worker.stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = USBFlasherApp()
    window.show()
    sys.exit(app.exec_())
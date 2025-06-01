# Ruuf USB Flasher

A simple GUI application to create bootable USB drives for Windows, macOS (Hackintosh), and Linux distributions, with properly bootable configurations.

## Features

- User-friendly graphical interface
- Support for Windows, macOS, and Linux
- Automatic detection of USB drives
- Proper bootable USB creation with UEFI support
- Advanced partitioning for Windows installation media
- Hackintosh USB creation with OpenCore bootloader
- Support for multiple macOS versions (Sonoma, Ventura, Monterey, etc.)
- Linux distribution installer creation
- Support for popular Linux distributions (Ubuntu, Debian, Fedora, etc.)
- Option to use custom ISO files
- Automatic ISO downloading for selected distributions
- Real-time progress tracking
- Safety confirmations to prevent accidental data loss
- Secure Boot utility to check and enable Secure Boot

## Requirements

- Python 3.6 or higher
- PyQt5 library
- Administrative privileges (required for disk operations)

## Installation

1. Clone this repository:
   ```
   
   cd ruuf-usb-flasher
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Option 1: All-in-One Setup Wizard

For a guided experience that combines USB flashing and Secure Boot setup:

```
python secure_boot_setup.py
```

This wizard will guide you through:
1. Creating a bootable Windows USB drive
2. Checking and enabling Secure Boot on your system

### Option 2: USB Flasher Only

1. Run the application:
   ```
   python ruuf_usb_flasher.py
   ```

   Note: On Linux and macOS, you may need to run with sudo:
   ```
   sudo python ruuf_usb_flasher.py
   ```

2. Choose your operation mode:
   - **Windows ISO Flasher**: For creating Windows installation media
   - **Hackintosh Creator**: For creating macOS installation media

3. For Windows ISO mode:
   - Select a Windows ISO file using the "Browse" button
   - Choose your USB drive from the dropdown menu
   - Click "Flash USB" to begin the flashing process
   - Confirm the operation when prompted

4. For Hackintosh Creator mode:
   - Select your desired macOS version from the dropdown
   - Choose your USB drive from the dropdown menu
   - Click "Flash USB" to begin the creation process
   - Confirm the operation when prompted

5. For Linux Distribution mode:
   - Select your desired Linux distribution from the dropdown
   - For custom ISOs, select "Other (Custom ISO)" and click "Browse ISO"
   - Choose your USB drive from the dropdown menu
   - Click "Flash USB" to begin the creation process
   - Confirm the operation when prompted

### Option 3: Secure Boot Utility Only

1. Run the Secure Boot utility directly:
   ```
   python secure_boot_utility.py
   ```

   Or from the main application:
   1. Click on "Tools" in the menu bar
   2. Select "Secure Boot Utility"

2. The utility will check your current Secure Boot status
3. Click "Show Guide" for detailed instructions on enabling Secure Boot for your system

## Warning

**This application will erase ALL data on the selected USB drive.** Make sure to back up any important files before proceeding.

## Troubleshooting

- **Permission denied errors**: Make sure you're running the application with administrative privileges.
- **USB drive not detected**: Click the "Refresh" button to scan for newly connected drives.
- **Flashing fails**: Ensure the ISO file is a valid Windows installation image and that the USB drive is properly connected.
- **USB not bootable**: The application now uses advanced methods to create properly bootable Windows installation media:
  - On Windows: Uses diskpart to create an active partition and bootsect.exe for proper boot sector setup
  - On Linux: Creates proper EFI System Partition (ESP) for UEFI boot support
  - On macOS: Uses GPT partitioning and proper file copying to ensure bootability
- **UEFI boot issues**: Make sure your system's BIOS/UEFI is configured to boot from USB and that Secure Boot settings are appropriate for your Windows version.
- **Hackintosh boot issues**:
  - You need to customize the config.plist file for your specific hardware
  - Use the included ProperTree tool to edit the config.plist
  - Add necessary kexts for your hardware
  - Refer to the OpenCore Install Guide for detailed instructions: https://dortania.github.io/OpenCore-Install-Guide/
- **macOS download fails**: Internet connection issues or Apple server problems can cause downloads to fail. Try again later or use a different network connection.
- **Linux boot issues**:
  - When running on Linux, the application **always** uses `dd` for direct ISO writing
  - This is the most reliable method for creating bootable USB drives on Linux systems
  - For UEFI systems, make sure your BIOS is configured to boot from USB in UEFI mode
  - For legacy systems, ensure boot order is set correctly in BIOS
  - If using a custom ISO, ensure it's a valid bootable Linux distribution image
  - Some distributions may have specific boot requirements - refer to their documentation
- **Linux download fails**: The application attempts to download from official mirrors which may change over time. If download fails, select "Other (Custom ISO)" and download the ISO manually from the distribution's website.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
#!/bin/bash
# Fix script for Ruuf USB Flasher

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Run the fix script
python3 fix_script.py

# Make the main script executable
chmod +x ruuf_usb_flasher.py

echo "Fix completed. You can now run ./ruuf_usb_flasher.py"
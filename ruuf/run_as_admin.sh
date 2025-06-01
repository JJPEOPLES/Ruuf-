#!/bin/bash
echo "Running Ruuf USB Flasher with administrative privileges..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sudo python3 ruuf_usb_flasher.py
else
    # Linux
    sudo python3 ruuf_usb_flasher.py
fi
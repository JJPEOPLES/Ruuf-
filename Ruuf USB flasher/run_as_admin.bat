@echo off
echo Running Ruuf USB Flasher with administrative privileges...
powershell -Command "Start-Process python -ArgumentList 'ruuf_usb_flasher.py' -Verb RunAs"
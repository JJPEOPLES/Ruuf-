#!/usr/bin/env python3
"""
Fix script for Ruuf USB Flasher
This script fixes the f-string backslash issue in ruuf_usb_flasher.py
"""

import os
import re

def fix_powershell_script():
    """Fix the PowerShell script in ruuf_usb_flasher.py"""
    file_path = "ruuf_usb_flasher.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the problematic f-string
    pattern = r'ps_script = f""".*?\$iso = \[System\.IO\.File\]::OpenRead\(\'.*?\'\).*?"""'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        # Extract the problematic code
        old_code = match.group(0)
        
        # Replace with fixed code
        new_code = """            # Create a PowerShell script for direct writing
            # Handle backslashes in the path properly
            safe_iso_path = iso_path.replace("\\\\", "\\\\\\\\")
            
            ps_script = """
            ps_script += """
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
            """.format(safe_iso_path, disk_number)"""
        
        # Replace in the content
        content = content.replace(old_code, new_code)
        
        # Write back to the file
        with open(file_path, 'w') as f:
            f.write(content)
        
        print("Fixed PowerShell script in ruuf_usb_flasher.py")
    else:
        print("No problematic f-string found")

if __name__ == "__main__":
    fix_powershell_script()
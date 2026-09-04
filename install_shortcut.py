"""
Helper script to install or refresh the JARVIS AI Desktop shortcut with custom icon.
"""

import os
import sys
import subprocess

def create_shortcut():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    app_script = os.path.join(project_dir, "app.py")
    ico_path = os.path.join(project_dir, "assets", "jarvis.ico")

    # Find pythonw.exe to run without a console window
    python_dir = os.path.dirname(sys.executable)
    pythonw_path = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw_path):
        pythonw_path = sys.executable

    ps_script = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktop 'JARVIS AI.lnk'
    $shortcut = $WshShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = '{pythonw_path}'
    $shortcut.Arguments = '"{app_script}"'
    $shortcut.WorkingDirectory = '{project_dir}'
    $shortcut.IconLocation = '{ico_path},0'
    $shortcut.Description = 'JARVIS - Personal AI Assistant'
    $shortcut.Save()
    Write-Output "Installed shortcut at: $shortcutPath"
    """

    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True)
        print("✅ JARVIS AI Desktop icon created successfully!")
    except Exception as e:
        print(f"❌ Error creating shortcut: {e}")

if __name__ == "__main__":
    create_shortcut()

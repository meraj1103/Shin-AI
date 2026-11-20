import os
import sys
import subprocess

def create_desktop_shortcut():
    # Find the pythonw.exe in the virtual environment if it exists, otherwise fall back to sys.executable
    work_dir = os.path.dirname(os.path.abspath(__file__))
    venv_pythonw = os.path.join(work_dir, ".venv", "Scripts", "pythonw.exe")
    parent_venv_pythonw = os.path.join(os.path.dirname(work_dir), ".venv", "Scripts", "pythonw.exe")
    if os.path.exists(venv_pythonw):
        python_exe = venv_pythonw
    elif os.path.exists(parent_venv_pythonw):
        python_exe = parent_venv_pythonw
    else:
        python_exe = sys.executable.replace("python.exe", "pythonw.exe")
    script_path = os.path.join(work_dir, "assistant.py")
    
    # We use a temporary VBScript to natively create the .lnk file in Windows
    vbs_script = os.path.join(work_dir, "temp_create_shortcut.vbs")
    
    vbs_content = f"""
Set ws = WScript.CreateObject("WScript.Shell")
DesktopPath = ws.SpecialFolders("Desktop")
ShortcutPath = DesktopPath & "\\Shin Assistant.lnk"
Set oLink = ws.CreateShortcut(ShortcutPath)
oLink.TargetPath = "{python_exe}"
oLink.Arguments = Chr(34) & "{script_path}" & Chr(34)
oLink.WorkingDirectory = "{work_dir}"
oLink.Description = "Launch Shin Voice Assistant"
oLink.Save
WScript.Echo ShortcutPath
"""
    
    with open(vbs_script, "w", encoding="utf-8") as f:
        f.write(vbs_content)
        
    try:
        result = subprocess.run(["cscript.exe", "//Nologo", vbs_script], check=True, capture_output=True, text=True)
        actual_shortcut_path = result.stdout.strip()
        print(f"Success: Desktop shortcut created successfully at:\n{actual_shortcut_path}")
    except Exception as e:
        print(f"Error: Failed to create shortcut: {e}")
    finally:
        if os.path.exists(vbs_script):
            os.remove(vbs_script)

if __name__ == "__main__":
    create_desktop_shortcut()
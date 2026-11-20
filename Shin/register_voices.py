import sys
import os
import ctypes
import winreg

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def copy_values(src_key, dest_key):
    try:
        num_values = winreg.QueryInfoKey(src_key)[1]
        for i in range(num_values):
            name, value, val_type = winreg.EnumValue(src_key, i)
            winreg.SetValueEx(dest_key, name, 0, val_type, value)
    except Exception as e:
        print(f"Error copying values: {e}")

def copy_key_recursive(src_hive, src_path, dest_hive, dest_path):
    try:
        # Open source key
        src_key = winreg.OpenKey(src_hive, src_path)
    except Exception as e:
        print(f"Error opening source key {src_path}: {e}")
        return

    # Create destination key
    dest_key = winreg.CreateKey(dest_hive, dest_path)
    
    # Copy values
    copy_values(src_key, dest_key)
    
    # Recursively copy subkeys
    try:
        num_subkeys = winreg.QueryInfoKey(src_key)[0]
        for i in range(num_subkeys):
            subkey_name = winreg.EnumKey(src_key, i)
            copy_key_recursive(
                src_hive, 
                src_path + "\\" + subkey_name, 
                dest_hive, 
                dest_path + "\\" + subkey_name
            )
    except Exception as e:
        print(f"Error listing subkeys of {src_path}: {e}")
        
    winreg.CloseKey(src_key)
    winreg.CloseKey(dest_key)

def register_onecore_voices():
    # Source path of Windows OneCore voices
    onecore_base = r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens"
    
    # Destination paths for SAPI5 (64-bit and 32-bit WoW64)
    dest_sapi = r"SOFTWARE\Microsoft\Speech\Voices\Tokens"
    dest_wow = r"SOFTWARE\Microsoft\WOW6432Node\Microsoft\Speech\Voices\Tokens"
    
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, onecore_base)
        num_voices = winreg.QueryInfoKey(key)[0]
        voices = [winreg.EnumKey(key, i) for i in range(num_voices)]
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Could not read OneCore voices registry: {e}")
        return

    if not voices:
        print("No OneCore voices found to register.")
        return

    print(f"Found OneCore voices: {voices}")
    for voice in voices:
        print(f"Registering voice: {voice}")
        # Copy to standard SAPI5 path
        copy_key_recursive(
            winreg.HKEY_LOCAL_MACHINE, 
            onecore_base + "\\" + voice, 
            winreg.HKEY_LOCAL_MACHINE, 
            dest_sapi + "\\" + voice
        )
        # Copy to WoW64 SAPI5 path
        copy_key_recursive(
            winreg.HKEY_LOCAL_MACHINE, 
            onecore_base + "\\" + voice, 
            winreg.HKEY_LOCAL_MACHINE, 
            dest_wow + "\\" + voice
        )
    print("\nRegistration complete! All OneCore voices are now registered in SAPI5.")

if __name__ == "__main__":
    if is_admin():
        print("Running with Administrator privileges.")
        register_onecore_voices()
        input("\nPress Enter to close...")
    else:
        print("Requesting Administrator privileges to access system registry...")
        # Relaunch the script with admin rights
        # sys.executable is the Python interpreter path, e.g. path to python.exe
        ctypes.windll.shell32.ShellExecuteW(
            None, 
            "runas", 
            sys.executable, 
            f'"{__file__}"', 
            None, 
            1
        )

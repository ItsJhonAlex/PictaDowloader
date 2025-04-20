import os
import sys
import subprocess

def build_executable():
    print("Building Picta Downloader executable...")
    
    # Create spec file
    spec_content = """
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['picta_downloader_ui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PictaDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
    """
    
    with open("picta_downloader.spec", "w") as f:
        f.write(spec_content)
    
    # Run PyInstaller
    subprocess.run(["pyinstaller", "--clean", "picta_downloader.spec"], check=True)
    
    print("Build completed successfully!")
    print("Executable is located in the 'dist' folder.")

if __name__ == "__main__":
    build_executable()
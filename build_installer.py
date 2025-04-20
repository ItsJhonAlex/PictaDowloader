import os
import sys
import subprocess

def build_executable():
    """
    Función principal para construir el ejecutable de Picta Downloader.
    Crea un archivo spec para PyInstaller y ejecuta el proceso de compilación.
    """
    print("Building Picta Downloader executable...")
    
    # Crear archivo spec con la configuración necesaria para PyInstaller
    spec_content = """
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['picta_downloader_ui.py'],  # Archivo principal de la aplicación
    pathex=[],                   # Rutas adicionales para buscar módulos
    binaries=[],                 # Archivos binarios adicionales
    datas=[],                    # Archivos de datos adicionales
    hiddenimports=[],            # Importaciones ocultas que PyInstaller podría no detectar
    hookspath=[],                # Rutas para hooks personalizados
    hooksconfig={},              # Configuración de hooks
    runtime_hooks=[],            # Hooks de tiempo de ejecución
    excludes=[],                 # Módulos a excluir
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
    name='PictaDownloader',      # Nombre del ejecutable final
    debug=False,                 # Desactivar modo de depuración
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                    # Usar UPX para comprimir el ejecutable
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,               # Sin consola (aplicación GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',             # Icono para el ejecutable
)
    """
    
    # Escribir el contenido del spec en un archivo
    with open("picta_downloader.spec", "w") as f:
        f.write(spec_content)
    
    # Ejecutar PyInstaller con el archivo spec creado
    subprocess.run(["pyinstaller", "--clean", "picta_downloader.spec"], check=True)
    
    print("Build completed successfully!")
    print("Executable is located in the 'dist' folder.")

if __name__ == "__main__":
    # Punto de entrada cuando se ejecuta directamente este script
    build_executable()
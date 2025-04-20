import os
import sys
import subprocess
import platform

def build_executable():
    """
    Función principal para construir el ejecutable de Picta Downloader.
    Crea un archivo spec para PyInstaller y ejecuta el proceso de compilación.
    """
    print("Building Picta Downloader executable...")
    
    # Detectar el sistema operativo
    current_os = platform.system()
    
    if current_os == "Windows":
        build_windows_executable()
    elif current_os == "Linux":
        build_linux_executable()
    else:
        print(f"Sistema operativo no soportado: {current_os}")
        sys.exit(1)

def build_windows_executable():
    """
    Construye el ejecutable para Windows usando PyInstaller.
    """
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

def build_linux_executable():
    """
    Construye el ejecutable para Linux y crea un paquete .deb para Linux Mint.
    """
    print("Construyendo ejecutable para Linux...")
    
    # Crear archivo spec para Linux
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
    name='pictadownloader',
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
    
    with open("picta_downloader_linux.spec", "w") as f:
        f.write(spec_content)
    
    # Ejecutar PyInstaller para Linux
    subprocess.run(["pyinstaller", "--clean", "picta_downloader_linux.spec"], check=True)
    
    print("Ejecutable construido correctamente.")
    
    # Crear estructura de directorios para el paquete .deb
    print("Creando paquete .deb para Linux Mint...")
    
    # Crear directorios necesarios
    deb_root = "deb_package"
    if os.path.exists(deb_root):
        import shutil
        shutil.rmtree(deb_root)
    
    # Estructura de directorios para el paquete .deb
    os.makedirs(f"{deb_root}/DEBIAN")
    os.makedirs(f"{deb_root}/usr/bin")
    os.makedirs(f"{deb_root}/usr/share/applications")
    os.makedirs(f"{deb_root}/usr/share/icons/hicolor/256x256/apps")
    os.makedirs(f"{deb_root}/usr/share/pictadownloader")
    
    # Copiar el ejecutable
    subprocess.run(["cp", "dist/pictadownloader", f"{deb_root}/usr/bin/"], check=True)
    
    # Copiar el icono (asumiendo que existe icon.png)
    if os.path.exists("icon.png"):
        subprocess.run(["cp", "icon.png", f"{deb_root}/usr/share/icons/hicolor/256x256/apps/pictadownloader.png"], check=True)
    
    # Crear archivo .desktop
    desktop_file = f"""[Desktop Entry]
Name=Picta Downloader
Comment=Descarga videos de Picta.cu
Exec=/usr/bin/pictadownloader
Icon=/usr/share/icons/hicolor/256x256/apps/pictadownloader.png
Terminal=false
Type=Application
Categories=Utility;Network;
"""
    
    with open(f"{deb_root}/usr/share/applications/pictadownloader.desktop", "w") as f:
        f.write(desktop_file)
    
    # Crear archivo de control para el paquete .deb
    control_file = f"""Package: pictadownloader
Version: 1.0.0
Section: utils
Priority: optional
Architecture: amd64
Depends: ffmpeg, python3, python3-pyqt5, python3-requests, python3-bs4, python3-selenium
Maintainer: PictaDownloader Team <example@example.com>
Description: Descargador de videos para Picta.cu
 PictaDownloader es una aplicación que permite descargar
 videos de la plataforma Picta.cu con diferentes opciones
 de calidad, audio y subtítulos.
"""
    
    with open(f"{deb_root}/DEBIAN/control", "w") as f:
        f.write(control_file)
    
    # Crear script postinst para manejar dependencias
    postinst_script = """#!/bin/bash
# Asegurar que todas las dependencias estén instaladas
apt-get update
apt-get install -y ffmpeg python3 python3-pyqt5 python3-requests python3-bs4 python3-selenium

# Dar permisos de ejecución al binario
chmod +x /usr/bin/pictadownloader

# Actualizar caché de iconos
if [ -x "$(command -v update-icon-caches)" ]; then
    update-icon-caches /usr/share/icons/hicolor
fi

exit 0
"""
    
    with open(f"{deb_root}/DEBIAN/postinst", "w") as f:
        f.write(postinst_script)
    
    # Dar permisos de ejecución al script postinst
    os.chmod(f"{deb_root}/DEBIAN/postinst", 0o755)
    
    # Construir el paquete .deb
    subprocess.run(["dpkg-deb", "--build", "--root-owner-group", deb_root, "pictadownloader_1.0.0_amd64.deb"], check=True)
    
    print("Paquete .deb creado correctamente: pictadownloader_1.0.0_amd64.deb")
    print("Este paquete incluye todas las dependencias necesarias para Linux Mint.")

if __name__ == "__main__":
    # Punto de entrada cuando se ejecuta directamente este script
    build_executable()
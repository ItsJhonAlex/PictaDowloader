import os
import re
import json
import time
import sys
import requests
import tempfile
import subprocess
import threading
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QLineEdit, QPushButton, QProgressBar, QComboBox, 
                            QFileDialog, QMessageBox, QTextEdit, QGroupBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon, QFont

class DownloaderThread(QThread):
    """
    Hilo de descarga que maneja todo el proceso de extracción y descarga de videos.
    Utiliza señales para comunicarse con la interfaz de usuario.
    """
    # Señales para comunicación con la interfaz de usuario
    progress_signal = pyqtSignal(int, int)      # Señal para actualizar el progreso (valor actual, total)
    status_signal = pyqtSignal(str)             # Señal para actualizar el estado textual
    finished_signal = pyqtSignal(bool, str)     # Señal para indicar finalización (éxito, mensaje)
    video_info_signal = pyqtSignal(dict)        # Señal para enviar información del video
    
    def __init__(self, url, output_dir, custom_filename=None):
        """
        Inicializa el hilo de descarga con los parámetros necesarios.
        
        Args:
            url (str): URL del video de Picta
            output_dir (str): Directorio donde se guardará el video
            custom_filename (str, opcional): Nombre personalizado para el archivo
        """
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.custom_filename = custom_filename
        self.downloader = PictaDownloader()
        self.video_info = None
        self.selected_video = None
        self.selected_audio = None
        self.selected_subtitle = None
        self.output_file = None
        
    def run(self):
        """
        Método principal que se ejecuta cuando se inicia el hilo.
        Maneja todo el proceso de extracción y descarga del video.
        """
        try:
            # Convertir URL de formato /medias/ a /embed/ si es necesario
            # (El formato /embed/ es necesario para extraer correctamente la información)
            if "/medias/" in self.url:
                self.url = self.url.replace("/medias/", "/embed/")
                self.status_signal.emit(f"Convertido URL a formato embed: {self.url}")
            
            self.status_signal.emit("Configurando navegador...")
            driver = self.downloader.setup_browser()
            
            try:
                self.status_signal.emit("Obteniendo información del video...")
                # Extraer información del video analizando las solicitudes de red
                self.video_info = self.downloader.extract_network_requests(driver, self.url)
                
                # Verificar si se encontró información válida
                if not self.video_info or not self.video_info['video_sources']:
                    self.status_signal.emit("No se pudo encontrar información del video.")
                    self.finished_signal.emit(False, "No se encontraron fuentes de video.")
                    return
                
                # Enviar información del video a la interfaz
                self.video_info_signal.emit(self.video_info)
                
                # Esperar a que el usuario seleccione las opciones de descarga
                while not self.selected_video:
                    time.sleep(0.5)
                
                # Crear nombre de archivo seguro (sin caracteres problemáticos)
                if self.custom_filename and self.custom_filename.strip():
                    # Usar nombre personalizado si se proporciona
                    safe_filename = re.sub(r'[^\w\-_\. ]', '_', self.custom_filename.strip())
                    if not safe_filename.lower().endswith('.mp4'):
                        safe_filename += '.mp4'
                    self.output_file = os.path.join(self.output_dir, safe_filename)
                else:
                    # Usar título del video como nombre de archivo
                    safe_title = re.sub(r'[^\w\-_\. ]', '_', self.video_info['title'])
                    self.output_file = os.path.join(self.output_dir, f"{safe_title}.mp4")
                
                # Descargar archivos temporales (video, audio, subtítulos)
                self.status_signal.emit("Descargando video...")
                video_temp = os.path.join(self.downloader.temp_dir, "video.mp4")
                if not self.downloader.download_file(self.selected_video['url'], video_temp, self.progress_signal):
                    self.status_signal.emit("Error al descargar el video.")
                    self.finished_signal.emit(False, "Error al descargar el video.")
                    return
                
                # Descargar audio si está seleccionado
                audio_temp = None
                if self.selected_audio:
                    self.status_signal.emit("Descargando audio...")
                    audio_temp = os.path.join(self.downloader.temp_dir, "audio.m4a")
                    if not self.downloader.download_file(self.selected_audio['url'], audio_temp, self.progress_signal):
                        self.status_signal.emit("Error al descargar el audio.")
                
                # Descargar subtítulos si están seleccionados
                subtitle_temp = None
                if self.selected_subtitle:
                    self.status_signal.emit("Descargando subtítulos...")
                    subtitle_temp = os.path.join(self.downloader.temp_dir, "subtitle.vtt")
                    if not self.downloader.download_file(self.selected_subtitle['url'], subtitle_temp, self.progress_signal):
                        self.status_signal.emit("Error al descargar los subtítulos.")
                
                # Combinar archivos con FFmpeg para crear el video final
                self.status_signal.emit("Combinando archivos...")
                try:
                    # Construir comando FFmpeg según los componentes disponibles
                    ffmpeg_cmd = ['ffmpeg', '-i', video_temp]
                    
                    if audio_temp:
                        ffmpeg_cmd.extend(['-i', audio_temp])
                    
                    ffmpeg_cmd.extend(['-c:v', 'copy'])  # Copiar video sin recodificar
                    
                    if audio_temp:
                        # Mapear video del primer input y audio del segundo
                        ffmpeg_cmd.extend(['-c:a', 'aac', '-map', '0:v', '-map', '1:a'])
                    else:
                        # Si no hay audio separado, copiar el audio del video
                        ffmpeg_cmd.extend(['-c:a', 'copy'])
                    
                    if subtitle_temp:
                        # Añadir subtítulos si están disponibles
                        ffmpeg_cmd.extend(['-i', subtitle_temp, '-c:s', 'mov_text', '-map', '2'])
                    
                    # Especificar archivo de salida y sobrescribir si existe
                    ffmpeg_cmd.extend(['-y', self.output_file])
                    
                    # Imprimir comando para depuración
                    print(f"Executing command: {' '.join(ffmpeg_cmd)}")
                    
                    # Ejecutar FFmpeg
                    result = subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
                    
                    if result.stderr:
                        print(f"FFmpeg stderr: {result.stderr}")
                    
                    self.status_signal.emit("¡Descarga completada!")
                    self.finished_signal.emit(True, self.output_file)
                    
                except subprocess.CalledProcessError as e:
                    self.status_signal.emit(f"Error al ejecutar FFmpeg: {e}")
                    print(f"FFmpeg stderr: {e.stderr}")
                    self.finished_signal.emit(False, f"Error al ejecutar FFmpeg: {e}")
                except Exception as e:
                    self.status_signal.emit(f"Error al combinar archivos: {e}")
                    self.finished_signal.emit(False, f"Error al combinar archivos: {e}")
                finally:
                    # Limpiar archivos temporales
                    if os.path.exists(video_temp):
                        os.remove(video_temp)
                    if audio_temp and os.path.exists(audio_temp):
                        os.remove(audio_temp)
                    if subtitle_temp and os.path.exists(subtitle_temp):
                        os.remove(subtitle_temp)
            
            finally:
                # Cerrar el navegador
                driver.quit()
                
        except Exception as e:
            self.status_signal.emit(f"Error: {e}")
            self.finished_signal.emit(False, f"Error: {e}")

class PictaDownloader:
    """
    Clase principal que maneja la extracción de información y descarga de archivos.
    Utiliza Selenium para extraer información y requests para descargar archivos.
    """
    def __init__(self):
        """Inicializa el descargador con la configuración necesaria."""
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        self.base_url = "https://www.picta.cu"
        self.temp_dir = tempfile.mkdtemp()  # Directorio temporal para archivos intermedios
        
    def setup_browser(self):
        """
        Configura el navegador Chrome para capturar solicitudes de red.
        
        Returns:
            WebDriver: Instancia configurada del navegador Chrome
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Ejecutar en modo sin cabeza (sin interfaz gráfica)
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        # Habilitar registro de red (crucial para capturar las URLs de los archivos)
        chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        # Instalar y configurar el driver de Chrome
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
        
    def extract_network_requests(self, driver, url):
        """
        Extrae solicitudes de red para encontrar archivos de video, audio y subtítulos.
        
        Args:
            driver (WebDriver): Instancia del navegador Chrome
            url (str): URL del video de Picta
            
        Returns:
            dict: Información del video incluyendo fuentes de video, audio y subtítulos
        """
        driver.get(url)
        
        # Esperar a que se cargue el reproductor de video
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "video"))
            )
        except Exception as e:
            print(f"Error al esperar el reproductor de video: {e}")
        
        # Dar tiempo para que se inicien las solicitudes de red
        time.sleep(5)
        
        # Hacer clic en el reproductor para iniciar la reproducción
        # (necesario para que se carguen todos los recursos)
        try:
            video_element = driver.find_element(By.CSS_SELECTOR, "video")
            driver.execute_script("arguments[0].play();", video_element)
            time.sleep(3)  # Esperar a que comience la reproducción
        except Exception as e:
            print(f"Error al iniciar la reproducción: {e}")
        
        # Extraer el título del video de la página
        try:
            title_element = driver.find_element(By.CSS_SELECTOR, "h1.title")
            title = title_element.text.strip()
        except:
            try:
                title_element = driver.find_element(By.CSS_SELECTOR, "h1")
                title = title_element.text.strip()
            except:
                title = "Video de Picta"
        
        # Analizar los registros de rendimiento para encontrar solicitudes de red
        logs = driver.get_log('performance')
        
        video_sources = []
        audio_tracks = []
        subtitle_tracks = []
        
        # Procesar cada entrada de log para identificar recursos multimedia
        for log in logs:
            try:
                log_entry = json.loads(log["message"])["message"]
                if "Network.responseReceived" in log_entry["method"]:
                    request_url = log_entry["params"]["response"]["url"]
                    
                    # Buscar archivos de video por patrones en la URL
                    if "video%2F" in request_url and request_url.endswith(".mp4"):
                        quality = "Unknown"
                        if "480p" in request_url:
                            quality = "480p"
                        elif "720p" in request_url:
                            quality = "720p"
                        elif "1080p" in request_url:
                            quality = "1080p"
                        
                        video_sources.append({
                            'url': request_url,
                            'quality': quality,
                            'type': 'video/mp4'
                        })
                    
                    # Buscar archivos de audio por patrones en la URL
                    if "audio%2F" in request_url and request_url.endswith(".mp4"):
                        language = "Desconocido"
                        if "eng" in request_url:
                            language = "Inglés"
                        elif "spa" in request_url or "es" in request_url:
                            language = "Español"
                        
                        bitrate = "Unknown"
                        if "128k" in request_url:
                            bitrate = "128k"
                        elif "192k" in request_url:
                            bitrate = "192k"
                        
                        audio_tracks.append({
                            'url': request_url,
                            'language': f"{language} ({bitrate})"
                        })
                    
                    # Buscar archivos de subtítulos por extensión
                    if request_url.endswith(".vtt") or request_url.endswith(".srt"):
                        language = "Desconocido"
                        if "eng" in request_url:
                            language = "Inglés"
                        elif "spa" in request_url or "es" in request_url:
                            language = "Español"
                        
                        subtitle_tracks.append({
                            'url': request_url,
                            'language': language
                        })
            except Exception as e:
                continue
        
        # Eliminar duplicados en las listas de recursos
        video_sources = [dict(t) for t in {tuple(d.items()) for d in video_sources}]
        audio_tracks = [dict(t) for t in {tuple(d.items()) for d in audio_tracks}]
        subtitle_tracks = [dict(t) for t in {tuple(d.items()) for d in subtitle_tracks}]
        
        # Devolver toda la información recopilada
        return {
            'title': title,
            'video_sources': video_sources,
            'audio_tracks': audio_tracks,
            'subtitles': subtitle_tracks
        }
    
    def download_file(self, url, output_path, progress_signal=None):
        """
        Descarga un archivo desde una URL con seguimiento de progreso.
        
        Args:
            url (str): URL del archivo a descargar
            output_path (str): Ruta donde guardar el archivo
            progress_signal (pyqtSignal, opcional): Señal para reportar progreso
            
        Returns:
            bool: True si la descarga fue exitosa, False en caso contrario
        """
        try:
            response = self.session.get(url, headers=self.headers, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024  # 1 KB
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:  # filtrar chunks de keep-alive
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Enviar señal de progreso si está disponible
                        if progress_signal and total_size > 0:
                            progress_signal.emit(downloaded, total_size)
            
            return True
        except Exception as e:
            print(f"Error al descargar {url}: {e}")
            return False

class PictaDownloaderUI(QMainWindow):
    """
    Interfaz gráfica principal de la aplicación.
    Permite al usuario interactuar con el descargador de videos.
    """
    def __init__(self):
        """Inicializa la ventana principal y configura la interfaz."""
        super().__init__()
        self.setWindowTitle("Picta Downloader")
        self.setMinimumSize(700, 500)
        
        # Configuración de la interfaz
        self.init_ui()
        
        # Variables de estado
        self.downloader_thread = None
        self.video_info = None
        
    def init_ui(self):
        """Configura todos los elementos de la interfaz de usuario."""
        # Widget principal que contiene todos los elementos
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal vertical
        main_layout = QVBoxLayout(central_widget)
        
        # Grupo de entrada de URL (parte superior)
        url_group = QGroupBox("URL del Video")
        url_layout = QHBoxLayout()
        
        # Campo para ingresar la URL del video
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.picta.cu/medias/...")
        url_layout.addWidget(self.url_input)
        
        # Botón para analizar la URL
        self.analyze_button = QPushButton("Analizar")
        self.analyze_button.clicked.connect(self.analyze_url)
        url_layout.addWidget(self.analyze_button)
        
        # Botón para recargar la información (útil si hay problemas)
        self.reload_button = QPushButton("Recargar")
        self.reload_button.clicked.connect(self.reload_url)
        self.reload_button.setEnabled(False)
        url_layout.addWidget(self.reload_button)
        
        url_group.setLayout(url_layout)
        main_layout.addWidget(url_group)
        
        # Grupo de opciones de descarga (parte central)
        self.options_group = QGroupBox("Opciones de Descarga")
        options_layout = QVBoxLayout()
        
        # Etiqueta para mostrar el título del video
        self.title_label = QLabel("Título: ")
        options_layout.addWidget(self.title_label)
        
        # Campo para personalizar el nombre del archivo
        filename_layout = QHBoxLayout()
        filename_layout.addWidget(QLabel("Nombre del archivo:"))
        self.custom_filename_input = QLineEdit()
        filename_layout.addWidget(self.custom_filename_input)
        options_layout.addLayout(filename_layout)
        
        # Selector de calidad de video
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Calidad de Video:"))
        self.video_quality_combo = QComboBox()
        quality_layout.addWidget(self.video_quality_combo)
        options_layout.addLayout(quality_layout)
        
        # Selector de pista de audio
        audio_layout = QHBoxLayout()
        audio_layout.addWidget(QLabel("Pista de Audio:"))
        self.audio_track_combo = QComboBox()
        audio_layout.addWidget(self.audio_track_combo)
        options_layout.addLayout(audio_layout)
        
        # Selector de subtítulos
        subtitle_layout = QHBoxLayout()
        subtitle_layout.addWidget(QLabel("Subtítulos:"))
        self.subtitle_combo = QComboBox()
        subtitle_layout.addWidget(self.subtitle_combo)
        options_layout.addLayout(subtitle_layout)
        
        # Selector de directorio de salida
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Guardar en:"))
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setText(os.getcwd())  # Directorio actual por defecto
        output_layout.addWidget(self.output_dir_input)
        
        # Botón para examinar directorios
        self.browse_button = QPushButton("Examinar")
        self.browse_button.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(self.browse_button)
        options_layout.addLayout(output_layout)
        
        self.options_group.setLayout(options_layout)
        self.options_group.setEnabled(False)  # Deshabilitado hasta que se analice una URL
        main_layout.addWidget(self.options_group)
        
        # Botón de descarga (parte inferior)
        self.download_button = QPushButton("Descargar")
        self.download_button.clicked.connect(self.start_download)
        self.download_button.setEnabled(False)  # Deshabilitado hasta que se analice una URL
        main_layout.addWidget(self.download_button)
        
        # Barra de progreso para mostrar el avance de la descarga
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        
        # Área de texto para mostrar mensajes de estado
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        main_layout.addWidget(self.status_text)
        
    def analyze_url(self):
        """
        Analiza la URL ingresada para extraer información del video.
        Inicia un hilo de descarga para el análisis.
        """
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Por favor, introduce una URL válida.")
            return
        
        # Verificar que la URL sea de Picta (formatos /medias/ o /embed/)
        if not (url.startswith("https://www.picta.cu/medias/") or url.startswith("https://www.picta.cu/embed/")):
            QMessageBox.warning(self, "Error", "La URL debe ser de picta.cu/medias/ o picta.cu/embed/")
            return
        
        # Deshabilitar botón de análisis durante el proceso
        self.analyze_button.setEnabled(False)
        self.status_text.append("Analizando URL...")
        
        # Iniciar hilo de descarga para análisis (sin descargar, solo extraer info)
        self.downloader_thread = DownloaderThread(url, self.output_dir_input.text())
        self.downloader_thread.status_signal.connect(self.update_status)
        self.downloader_thread.video_info_signal.connect(self.update_video_info)
        self.downloader_thread.finished_signal.connect(self.analysis_finished)
        self.downloader_thread.start()
    
    def reload_url(self):
        """
        Recarga la información del video desde la URL actual.
        Útil si la carga inicial falló o si se quiere actualizar la información.
        """
        self.analyze_url()  # Reutilizamos el método de análisis
    
    def update_video_info(self, video_info):
        """
        Actualiza la interfaz con la información del video extraída.
        
        Args:
            video_info (dict): Información del video incluyendo título y fuentes
        """
        self.video_info = video_info
        
        # Actualizar título mostrado
        self.title_label.setText(f"Título: {video_info['title']}")
        
        # Establecer el título como nombre de archivo predeterminado
        safe_title = re.sub(r'[^\w\-_\. ]', '_', video_info['title'])
        self.custom_filename_input.setText(safe_title)
        
        # Actualizar opciones de calidad de video en el combo box
        self.video_quality_combo.clear()
        for source in video_info['video_sources']:
            self.video_quality_combo.addItem(source['quality'], source)
        
        # Actualizar opciones de audio en el combo box
        self.audio_track_combo.clear()
        self.audio_track_combo.addItem("Ninguno", None)
        for track in video_info['audio_tracks']:
            self.audio_track_combo.addItem(track['language'], track)
        
        # Actualizar opciones de subtítulos en el combo box
        self.subtitle_combo.clear()
        self.subtitle_combo.addItem("Ninguno", None)
        for subtitle in video_info['subtitles']:
            self.subtitle_combo.addItem(subtitle['language'], subtitle)
        
        # Habilitar opciones y botón de descarga
        self.options_group.setEnabled(True)
        self.download_button.setEnabled(True)
    
    def analysis_finished(self, success, message):
        """
        Maneja la finalización del análisis de la URL.
        
        Args:
            success (bool): Si el análisis fue exitoso
            message (str): Mensaje de resultado o error
        """
        self.analyze_button.setEnabled(True)
        self.reload_button.setEnabled(True)  # Habilitar botón de recarga
        if not success:
            QMessageBox.warning(self, "Error", message)
    
    def start_download(self):
        """
        Inicia el proceso de descarga con las opciones seleccionadas.
        Crea un nuevo hilo de descarga con la configuración actual.
        """
        if not self.video_info:
            return
        
        # Obtener opciones seleccionadas de los combo boxes
        video_index = self.video_quality_combo.currentIndex()
        audio_index = self.audio_track_combo.currentIndex()
        subtitle_index = self.subtitle_combo.currentIndex()
        
        if video_index < 0:
            QMessageBox.warning(self, "Error", "Por favor, selecciona una calidad de video.")
            return
        
        # Obtener nombre de archivo personalizado si se proporcionó
        custom_filename = self.custom_filename_input.text().strip()
        
        # Crear un nuevo hilo de descarga con las opciones seleccionadas
        url = self.url_input.text().strip()
        self.downloader_thread = DownloaderThread(url, self.output_dir
        
        # Configurar opciones en el hilo de descarga
        self.downloader_thread.selected_video = self.video_quality_combo.currentData()
        self.downloader_thread.selected_audio = self.audio_track_combo.currentData() if audio_index > 0 else None
        self.downloader_thread.selected_subtitle = self.subtitle_combo.currentData() if subtitle_index > 0 else None
        
        # Conectar señales para actualizar la interfaz durante la descarga
        self.downloader_thread.status_signal.connect(self.update_status)
        self.downloader_thread.progress_signal.connect(self.update_progress)
        self.downloader_thread.finished_signal.connect(self.download_finished)
        
        # Deshabilitar controles durante la descarga para evitar operaciones simultáneas
        self.download_button.setEnabled(False)
        self.options_group.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.reload_button.setEnabled(False)
        
        # Iniciar descarga
        self.downloader_thread.start()
    
    def update_status(self, status):
        """
        Actualiza el área de texto de estado con nuevos mensajes.
        
        Args:
            status (str): Mensaje de estado a mostrar
        """
        self.status_text.append(status)
        # Desplazar al final para mostrar siempre el mensaje más reciente
        self.status_text.verticalScrollBar().setValue(self.status_text.verticalScrollBar().maximum())
    
    def update_progress(self, current, total):
        """
        Actualiza la barra de progreso según el avance de la descarga.
        
        Args:
            current (int): Bytes descargados actualmente
            total (int): Tamaño total en bytes
        """
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
    
    def download_finished(self, success, message):
        """
        Maneja la finalización del proceso de descarga.
        
        Args:
            success (bool): Si la descarga fue exitosa
            message (str): Mensaje de resultado o ruta del archivo descargado
        """
        # Habilitar controles nuevamente
        self.download_button.setEnabled(True)
        self.options_group.setEnabled(True)
        self.analyze_button.setEnabled(True)
        self.reload_button.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Éxito", f"Descarga completada: {message}")
            self.progress_bar.setValue(100)
        else:
            QMessageBox.warning(self, "Error", message)
            self.progress_bar.setValue(0)
    
    def browse_output_dir(self):
        """
        Abre un diálogo para seleccionar el directorio de salida para los archivos descargados.
        """
        directory = QFileDialog.getExistingDirectory(self, "Seleccionar Directorio de Salida")
        if directory:
            self.output_dir_input.setText(directory)

if __name__ == "__main__":
    """
    Punto de entrada principal de la aplicación.
    Inicializa la aplicación Qt y muestra la ventana principal.
    """
    app = QApplication(sys.argv)
    window = PictaDownloaderUI()
    window.show()
    sys.exit(app.exec_())
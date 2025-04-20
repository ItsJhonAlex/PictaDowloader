import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
import tempfile
import argparse
import subprocess
from urllib.parse import urlparse, unquote
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class PictaDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        self.base_url = "https://www.picta.cu"
        self.temp_dir = tempfile.mkdtemp()
        
    def setup_browser(self):
        """Configura el navegador Chrome para capturar solicitudes de red"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Ejecutar en modo sin cabeza
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        # Habilitar registro de red
        chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
        
    def extract_network_requests(self, driver, url):
        """Extrae solicitudes de red para encontrar archivos de video y audio"""
        print("Navegando a la página del video...")
        driver.get(url)
        
        # Esperar a que se cargue el reproductor de video
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "video"))
            )
        except Exception as e:
            print(f"Error al esperar el reproductor de video: {e}")
        
        # Dar tiempo para que se inicien las solicitudes de red
        print("Esperando a que se carguen los recursos del video...")
        time.sleep(5)
        
        # Hacer clic en el reproductor para iniciar la reproducción
        try:
            video_element = driver.find_element(By.CSS_SELECTOR, "video")
            driver.execute_script("arguments[0].play();", video_element)
            time.sleep(3)  # Esperar a que comience la reproducción
        except Exception as e:
            print(f"Error al iniciar la reproducción: {e}")
        
        # Extraer el título del video
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
        print("Analizando solicitudes de red...")
        logs = driver.get_log('performance')
        
        video_sources = []
        audio_tracks = []
        subtitle_tracks = []
        
        for log in logs:
            try:
                log_entry = json.loads(log["message"])["message"]
                if "Network.responseReceived" in log_entry["method"]:
                    request_url = log_entry["params"]["response"]["url"]
                    
                    # Buscar archivos de video
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
                    
                    # Buscar archivos de audio
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
                    
                    # Buscar archivos de subtítulos
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
        
        # Eliminar duplicados
        video_sources = [dict(t) for t in {tuple(d.items()) for d in video_sources}]
        audio_tracks = [dict(t) for t in {tuple(d.items()) for d in audio_tracks}]
        subtitle_tracks = [dict(t) for t in {tuple(d.items()) for d in subtitle_tracks}]
        
        return {
            'title': title,
            'video_sources': video_sources,
            'audio_tracks': audio_tracks,
            'subtitles': subtitle_tracks
        }
    
    def download_file(self, url, output_path):
        """Descarga un archivo desde una URL"""
        try:
            response = self.session.get(url, headers=self.headers, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024  
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Mostrar progreso
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\rProgreso: {percent:.1f}% [{downloaded} / {total_size} bytes]", end="")
            
            print()  # Nueva línea después de la barra de progreso
            return True
        except Exception as e:
            print(f"Error al descargar {url}: {e}")
            return False
    
    def download_video(self, url, output_dir=None):
        """Proceso principal para descargar el video"""
        if output_dir is None:
            output_dir = os.getcwd()
        
        # Configurar el navegador y obtener información del video
        driver = self.setup_browser()
        try:
            video_info = self.extract_network_requests(driver, url)
            
            if not video_info or not video_info['video_sources']:
                print("No se pudo encontrar información del video o no se encontraron fuentes de video.")
                return False
            
            print(f"\nTítulo: {video_info['title']}")
            
            # Mostrar opciones de calidad de video
            print("\nCalidades de video disponibles:")
            for i, source in enumerate(video_info['video_sources'], 1):
                print(f"{i}. {source['quality']}")
            
            video_choice = int(input("\nSelecciona la calidad de video (número): ")) - 1
            if video_choice < 0 or video_choice >= len(video_info['video_sources']):
                print("Selección inválida.")
                return False
            
            selected_video = video_info['video_sources'][video_choice]
            
            # Mostrar opciones de audio
            selected_audio = None
            if video_info['audio_tracks']:
                print("\nPistas de audio disponibles:")
                for i, track in enumerate(video_info['audio_tracks'], 1):
                    print(f"{i}. {track['language']}")
                
                audio_choice = int(input("\nSelecciona la pista de audio (número, 0 para ninguna): "))
                if audio_choice > 0 and audio_choice <= len(video_info['audio_tracks']):
                    selected_audio = video_info['audio_tracks'][audio_choice - 1]
            
            # Mostrar opciones de subtítulos
            selected_subtitle = None
            if video_info['subtitles']:
                print("\nSubtítulos disponibles:")
                for i, sub in enumerate(video_info['subtitles'], 1):
                    print(f"{i}. {sub['language']}")
                
                sub_choice = int(input("\nSelecciona los subtítulos (número, 0 para ninguno): "))
                if sub_choice > 0 and sub_choice <= len(video_info['subtitles']):
                    selected_subtitle = video_info['subtitles'][sub_choice - 1]
            
            # Crear nombre de archivo seguro
            safe_title = re.sub(r'[^\w\-_\. ]', '_', video_info['title'])
            output_file = os.path.join(output_dir, f"{safe_title}.mp4")
            
            # Descargar archivos temporales
            print("\nDescargando video...")
            video_temp = os.path.join(self.temp_dir, "video.mp4")
            if not self.download_file(selected_video['url'], video_temp):
                print("Error al descargar el video.")
                return False
            
            audio_temp = None
            if selected_audio:
                print("\nDescargando audio...")
                audio_temp = os.path.join(self.temp_dir, "audio.m4a")
                if not self.download_file(selected_audio['url'], audio_temp):
                    print("Error al descargar el audio.")
            
            subtitle_temp = None
            if selected_subtitle:
                print("\nDescargando subtítulos...")
                subtitle_temp = os.path.join(self.temp_dir, "subtitle.vtt")
                if not self.download_file(selected_subtitle['url'], subtitle_temp):
                    print("Error al descargar los subtítulos.")
            
            # Combinar archivos con FFmpeg
            print("\nCombinando archivos...")
            try:
                ffmpeg_cmd = ['ffmpeg', '-i', video_temp]
                
                if audio_temp:
                    ffmpeg_cmd.extend(['-i', audio_temp])
                
                ffmpeg_cmd.extend(['-c:v', 'copy'])
                
                if audio_temp:
                    ffmpeg_cmd.extend(['-c:a', 'aac', '-map', '0:v', '-map', '1:a'])
                else:
                    ffmpeg_cmd.extend(['-c:a', 'copy'])
                
                if subtitle_temp:
                    ffmpeg_cmd.extend(['-i', subtitle_temp, '-c:s', 'mov_text', '-map', '2'])
                
                ffmpeg_cmd.extend(['-y', output_file])
                
                subprocess.run(ffmpeg_cmd, check=True)
                
                print(f"\n¡Descarga completada! Archivo guardado en: {output_file}")
                return True
                
            except Exception as e:
                print(f"Error al combinar archivos: {e}")
                return False
            finally:
               
                if os.path.exists(video_temp):
                    os.remove(video_temp)
                if audio_temp and os.path.exists(audio_temp):
                    os.remove(audio_temp)
                if subtitle_temp and os.path.exists(subtitle_temp):
                    os.remove(subtitle_temp)
        
        finally:
            # Cerrar el navegador
            driver.quit()

def main():
    parser = argparse.ArgumentParser(description='Descargar videos de Picta.cu')
    parser.add_argument('url', help='URL del video de Picta.cu')
    parser.add_argument('-o', '--output-dir', help='Directorio de salida para guardar el video')
    
    args = parser.parse_args()
    
    downloader = PictaDownloader()
    downloader.download_video(args.url, args.output_dir)

if __name__ == "__main__":
    main()
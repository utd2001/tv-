import subprocess
import requests
import re
import socket
from datetime import datetime
import os
import time
from urllib.parse import urlparse
from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException
import json
import copy

M3U8_DIR = "m3u8"
CONFIG_FILE = "config.json"

def log(message):
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    try:
        with open("log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except IOError as e:
        print(f"Log dosyasına yazma hatası: {e}")

def get_ipv4_address():
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    try:
        result = subprocess.run(
             ["ipconfig"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        matches = re.findall(r"(?:IPv4.*?:\s*)(\d+\.\d+\d+\.\d+)", result.stdout)
        if matches:
            return matches[0]
    except Exception:
        pass
    return "127.0.0.1"

SERVER_HOST = get_ipv4_address()
log(f"Kullanılan SERVER_HOST: {SERVER_HOST}")

def sanitize_filename(filename):
    replacements = {
        'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
        'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'
    }
    try:
        for turkish, english in replacements.items():
            filename = filename.replace(turkish, english)
        filename = re.sub(r'\s+', '_', filename)
        filename = re.sub(r'[^A-Za-z0-9_.-]', '', filename)
        if not filename:
            raise ValueError("Dosya adı boş olamaz")
        return filename
    except Exception as e:
        log(f"Dosya adı temizleme hatası: {e}")
        raise

def load_config():
    """Config dosyasını yükler ve kanalları ve diğer ayarları döndürür."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            only_highest = data.get("ONLY_HIGHEST", 1)
            
            channels_raw = data.get("channels", [])
            migrated_channels = []

            # Eski formattan (list) yeni formata (dict) geçiş ve uyumluluk
            for ch in channels_raw:
                if isinstance(ch, list):
                    # Eski format: ["NAME", "URL", (opsiyonel) AUTO_BOOL]
                    migrated_channels.append({
                        "name": ch[0] if len(ch) > 0 else "",
                        "url": ch[1] if len(ch) > 1 else "",
                        "auto": ch[2] if len(ch) > 2 else False
                    })
                elif isinstance(ch, dict):
                    # Yeni format: {"name": ..., "url": ..., "auto": ...}
                    migrated_channels.append({
                        "name": ch.get("name", ""),
                        "url": ch.get("url", ""),
                        "auto": ch.get("auto", False)
                    })
                    
            return migrated_channels, only_highest
            
    except Exception as e:
        log(f"Config dosyasından kanallar okunamadı: {e}")
        return [], 1

def save_config(channels, only_highest):
    """Verilen kanal listesini ve ayarları config dosyasına kaydeder."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            config_data = {
                "ONLY_HIGHEST": only_highest,
                "channels": channels
            }
            json.dump(config_data, f, indent=4, ensure_ascii=False)
            log("Config dosyası 'Oto' güncellemeleriyle kaydedildi.")
    except Exception as e:
        log(f"Config kaydetme hatası: {e}")

def search_youtube_innertube(query):
    """YouTube InnerTube API kullanarak canlı yayın araması yapar."""
    log(f"InnerTube ile YouTube araması yapılıyor: '{query}'")
    headers = {'origin': 'https://www.youtube.com', 'referer': 'https://www.youtube.com/', 'user-agent': 'Mozilla/5.0'}
    payload = {
        'context': {
            'client': { 'clientName': 'WEB', 'clientVersion': '2.20240101.00.00' }
        },
        'query': query,
        'params': 'EgJAAQ%3D%3D'
    }
    try:
        response = requests.post('https://www.youtube.com/youtubei/v1/search', headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        contents = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents']
        for item in contents:
            if 'videoRenderer' in item:
                video_id = item['videoRenderer'].get('videoId')
                badges = item['videoRenderer'].get('badges', [])
                is_live = any(b.get('metadataBadgeRenderer', {}).get('style') == 'BADGE_STYLE_TYPE_LIVE_NOW' for b in badges)
                if video_id and is_live:
                    log(f"Canlı yayın bulundu: Video ID = {video_id}")
                    return video_id
        for item in contents:
            if 'videoRenderer' in item and item['videoRenderer'].get('videoId'):
                video_id = item['videoRenderer']['videoId']
                log(f"Canlı yayın bulunamadı, ilk sonuç döndürülüyor: Video ID = {video_id}")
                return video_id
    except Exception as e:
        log(f"YouTube arama (InnerTube) hatası: {e}")
    return None

def auto_update_channel_ids():
    """'Oto' olarak işaretlenmiş kanalların video ID'lerini günceller."""
    log("Otomatik Video ID güncelleme süreci başlatılıyor...")
    channels, only_highest = load_config()
    original_channels = copy.deepcopy(channels)
    
    # Yeni obje formatına göre filtrele
    channels_to_update = [channel for channel in channels if channel.get('auto', False)]
    
    if not channels_to_update:
        log("'Oto' olarak işaretlenmiş kanal bulunamadı. Güncelleme atlanıyor.")
        return

    log(f"{len(channels_to_update)} adet 'Oto' kanal güncellenecek.")

    for channel in channels_to_update:
        channel_name = channel.get('name', '')
        if not channel_name:
            continue
            
        log(f"'{channel_name}' için canlı yayın aranıyor...")
        search_query = f"{channel_name} canlı yayını"
        new_video_id = search_youtube_innertube(search_query)
        
        current_video_id = channel.get('url', '')
        
        if new_video_id and new_video_id != current_video_id:
            log(f"'{channel_name}' için yeni Video ID bulundu: {new_video_id}. Config güncelleniyor.")
            channel['url'] = new_video_id # Objeyi güncelle
        elif new_video_id:
            log(f"'{channel_name}' için bulunan ID ({new_video_id}) zaten mevcut. Değişiklik yapılmadı.")
        else:
            log(f"'{channel_name}' için yeni canlı yayın ID'si bulunamadı. Mevcut ID korunuyor.")
            
    if original_channels != channels:
        log("Değişiklikler tespit edildi, config.json dosyası güncelleniyor.")
        save_config(channels, only_highest) # channels artık obje listesi
    else:
        log("Config dosyasında herhangi bir değişiklik yapılmadı.")

# --- SCRIPT BAŞLANGICI ---
auto_update_channel_ids()

def get_github_details_from_remote():
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            check=True, capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        url = result.stdout.strip()
        match = re.search(r'(?:[:/])([^/]+)/([^/]+?)(?:\.git)?$', url)
        if match:
            user, repo = match.groups()
            log(f"GitHub detayları bulundu: Kullanıcı={user}, Repo={repo}")
            return user, repo
        log("Hata: Git remote URL'si anlaşılamadı.")
        return None, None
    except Exception as e:
        log(f"GitHub detayları alınamadı: {e}")
        return None, None

def get_resolution_label(height):
    if not isinstance(height, int) or height <= 0:
        return ""
    if height >= 1080:
        return " FULL HD"
    elif height >= 720:
        return " HD"
    else:
        return " SD"

# ===================================================================
# === YENİ FONKSİYON (ADIM 2) =======================================
# ===================================================================
def generate_offline_playlist(user, repo):
    """Mutlak GitHub URL'leri ile offline_master.m3u8 dosyasını oluşturur."""
    log("Mutlak URL'ler ile 'offline_master.m3u8' oluşturuluyor...")
    # 'offline_stream' klasörünün var olduğundan emin ol
    os.makedirs("offline_stream", exist_ok=True)
    
    base_url = f"https://raw.githubusercontent.com/{user}/{repo}/main/offline_stream"
    
    content = [
        "#EXTM3U",
        f'#EXT-X-STREAM-INF:PROGRAM-ID=1,AVERAGE-BANDWIDTH=4000000,BANDWIDTH=4400000,NAME="1080p",RESOLUTION=1920x1080',
        f"{base_url}/1080p/index.m3u8",
        f'#EXT-X-STREAM-INF:PROGRAM-ID=1,AVERAGE-BANDWIDTH=2000000,BANDWIDTH=2200000,NAME="720p",RESOLUTION=1280x720',
        f"{base_url}/720p/index.m3u8",
        f'#EXT-X-STREAM-INF:PROGRAM-ID=1,AVERAGE-BANDWIDTH=900000,BANDWIDTH=1000000,NAME="480p",RESOLUTION=854x480',
        f"{base_url}/480p/index.m3u8",
        f'#EXT-X-STREAM-INF:PROGRAM-ID=1,AVERAGE-BANDWIDTH=500000,BANDWIDTH=550000,NAME="360p",RESOLUTION=640x360',
        f"{base_url}/360p/index.m3u8",
        f'#EXT-X-STREAM-INF:PROGRAM-ID=1,AVERAGE-BANDWIDTH=300000,BANDWIDTH=330000,NAME="240p",RESOLUTION=426x240',
        f"{base_url}/240p/index.m3u8",
        f'#EXT-X-STREAM-INF:PROGRAM-ID=1,AVERAGE-BANDWIDTH=150000,BANDWIDTH=165000,NAME="144p",RESOLUTION=256x144',
        f"{base_url}/144p/index.m3u8"
    ]
    
    try:
        # Bu dosyayı server.pyw'nin okuması için offline_stream klasörüne kaydet
        with open(os.path.join("offline_stream", "offline_master.m3u8"), "w", encoding="utf-8") as f:
            f.write("\n".join(content))
        log("'offline_master.m3u8' başarıyla oluşturuldu.")
    except IOError as e:
        log(f"Offline master playlist yazılırken hata: {e}")
# ===================================================================
# === SON ===========================================================
# ===================================================================

# ===================================================================
# === GÜNCELLENMİŞ FONKSİYON (ADIM 2) ===============================
# ===================================================================
def generate_master_playlist(channel_data, user, repo):
    base_url = f"https://raw.githubusercontent.com/{user}/{repo}/main/m3u8"
    # Offline stream için mutlak URL
    base_offline_url = f"https://raw.githubusercontent.com/{user}/{repo}/main/offline_stream/offline_master.m3u8"
    
    playlist_content = ['#EXTM3U']
    for data in channel_data:
        channel_name = data['name']
        resolution_label = data['label']
        is_offline = data.get('is_offline', False) # Değişiklik

        if is_offline:
            # Kanal çevrimdışıysa, offline master playlist'in mutlak URL'sini kullan
            full_url = base_offline_url
            log(f"'{channel_name}' çevrimdışı, offline master playlist'e yönlendiriliyor.")
        else:
            # Kanal çevrimiçiyse, normal m3u8 dosyasının URL'sini kullan
            sanitized_name = sanitize_filename(channel_name).upper()
            file_name = f"{sanitized_name}.m3u8"
            full_url = f"{base_url}/{file_name}"

        final_channel_name = f"{channel_name}{resolution_label}"
        extinf_line = f'#EXTINF:-1,{final_channel_name}'

        playlist_content.append(extinf_line)
        playlist_content.append(full_url)
    try:
        with open("tv.m3u8", "w", encoding="utf-8") as f:
            f.write("\n".join(playlist_content))
        log("Ana playlist dosyası 'tv.m3u8' başarıyla oluşturuldu/güncellendi.")
    except IOError as e:
        log(f"Ana playlist dosyası yazılırken hata: {e}")
# ===================================================================
# === SON ===========================================================
# ===================================================================

channels_config, _ = load_config()
channels = []
for item in channels_config:
    name = item.get('name', '')
    if not name:
        continue
    sanitized_name = sanitize_filename(name).upper()
    url = f"http://{SERVER_HOST}:5000/{sanitized_name}.m3u8"
    channels.append((name, url)) 

def wait_for_server(base_url: str, timeout_seconds: int = 120, interval_seconds: int = 2) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            resp = requests.get(base_url, timeout=5)
            if resp.status_code < 500:
                return True
        except (ConnectionError, Timeout):
            pass
        time.sleep(interval_seconds)
    return False

def get_base_url(sample_url: str) -> str:
    parsed = urlparse(sample_url)
    return f"{parsed.scheme}://{parsed.hostname}:{parsed.port or 5000}/"

os.makedirs(M3U8_DIR, exist_ok=True)
log(f"'{M3U8_DIR}' klasörü kontrol edildi/oluşturuldu.")

try:
    base_url = get_base_url(channels[0][1]) if channels else f"http://{SERVER_HOST}:5000/"
    if not wait_for_server(base_url):
        log(f"Sunucuya bağlanılamadı: {base_url} (hazır değil)")
    else:
        log(f"Sunucu hazır: {base_url}")
except Exception as e:
    log(f"Sunucu hazırlık kontrolü hatası: {e}")

channel_data_for_playlist = []

for name, hls_url in channels:
    log(f"İşleniyor: {name} - {hls_url}")
    max_attempts = 6
    attempt = 0
    hls_response = None
    while attempt < max_attempts and hls_response is None:
        attempt += 1
        try:
            hls_response = requests.get(hls_url, timeout=60)
            hls_response.raise_for_status()
        except (ConnectionError, Timeout) as e:
            log(f"Deneme {attempt}/{max_attempts} bağlantı sorunu ({name}): {e}")
            hls_response = None
            time.sleep(3)
        except HTTPError as e:
            log(f"Deneme {attempt}/{max_attempts} HTTP hatası ({name}): {e}")
            hls_response = None
            time.sleep(2)
        except RequestException as e:
            log(f"Deneme {attempt}/{max_attempts} genel istek hatası ({name}): {e}")
            hls_response = None
            time.sleep(2)

    # ===================================================================
    # === GÜNCELLENMİŞ BLOK (ADIM 2) ====================================
    # ===================================================================
    if hls_response is None:
        log(f"Kanal alınamadı, denemeler tükendi ({name}). Offline stream'e yönlendirilecek.")
        # Değişiklik: 'is_offline' anahtarı eklendi
        channel_data_for_playlist.append({'name': name, 'label': '', 'is_offline': True})
        continue
    # ===================================================================
    # === SON ===========================================================
    # ===================================================================

    max_height = 0
    if hls_response.text:
        lines = hls_response.text.splitlines()
        for line in lines:
            if line.startswith('#EXT-X-STREAM-INF'):
                match = re.search(r'RESOLUTION=\d+x(\d+)', line)
                if match:
                    try:
                        height = int(match.group(1))
                        if height > max_height:
                            max_height = height
                    except (ValueError, IndexError):
                        continue
        
        if max_height == 0:
            log(f"'{name}' için RESOLUTION etiketi bulunamadı. URL'ler taranıyor...")
            found_height = 0
            for line in lines:
                if not line.startswith('#'): # Bu bir URL veya segment satırıdır
                    if '1080' in line:
                        found_height = max(found_height, 1080)
                    elif '720' in line:
                        found_height = max(found_height, 720)
                    elif '480' in line:
                        found_height = max(found_height, 480)
                    elif '360' in line:
                        found_height = max(found_height, 360)
            
            if found_height > 0:
                log(f"URL'den tahmini çözünürlük bulundu: {found_height}p")
                max_height = found_height
    
    # ===================================================================
    # === GÜNCELLENMİŞ BLOK (ADIM 2) ====================================
    # ===================================================================
    resolution_label = get_resolution_label(max_height)
    # Değişiklik: 'is_offline' anahtarı eklendi
    channel_data_for_playlist.append({'name': name, 'label': resolution_label, 'is_offline': False})
    log(f"'{name}' için en yüksek çözünürlük bulundu: {max_height}p, Etiket: '{resolution_label.strip()}'")
    # ===================================================================
    # === SON ===========================================================
    # ===================================================================

    filename = f"{sanitize_filename(name).upper()}.m3u8"
    filepath = os.path.join(M3U8_DIR, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(hls_response.text)
        log(f"Kaydedildi: {filepath}")
    except IOError as e:
        log(f"Dosya yazma hatası ({name}): {e}")
        continue

# ===================================================================
# === GÜNCELLENMİŞ BLOK (ADIM 2) ====================================
# ===================================================================
github_user, github_repo = get_github_details_from_remote()
if github_user and github_repo:
    # Önce 'offline_master.m3u8' dosyasını (yeniden) oluştur
    generate_offline_playlist(github_user, github_repo) 
    # Sonra ana 'tv.m3u8' dosyasını oluştur
    generate_master_playlist(channel_data_for_playlist, github_user, github_repo)
else:
    log("GitHub kullanıcı/repo bilgisi alınamadığı için ana playlist oluşturulamadı.")
# ===================================================================
# === SON ===========================================================
# ===================================================================

try:
    if not os.path.exists(".git"):
        log("Hata: Git deposu bulunamadı")
        raise RuntimeError("Git deposu bulunamadı")

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    if not result.stdout.strip():
         log("Değişiklik yok, Git işlemleri atlanıyor")
    else:
        log("Git değişiklikleri:\n" + result.stdout.strip())
        # Değişiklik: Sadece m3u8, offline_stream, tv.m3u8 ve config.json'u ekle
        subprocess.run(["git", "add", M3U8_DIR, "offline_stream", "tv.m3u8", CONFIG_FILE, "log.txt"], check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        try:
            subprocess.run(["git", "commit", "-m", timestamp], check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            log("Commit başarılı")
        except subprocess.CalledProcessError as e:
            if "nothing to commit" in (e.stderr or ""):
                log("Commit atlandı (değişiklik yok)")
            else:
                log(f"Commit hatası: {e.stderr or e.stdout}")
                raise

        def try_push():
            try:
                push_result = subprocess.run(["git", "push"], check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                log(push_result.stdout.strip() or "git push başarılı")
                return True
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr or e.stdout
                log(f"git push hatası: {error_msg}")
                if "fetch first" in error_msg or "rejected" in error_msg:
                    log("Push reddedildi, önce pull --rebase deneniyor...")
                    try:
                        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        subprocess.run(["git", "push"], check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        log("Pull + Push başarılı")
                        return True
                    except subprocess.CalledProcessError as e2:
                        log(f"Pull + Push başarısız: {e2.stderr or e2.stdout}")
                        log("Son çare: force push deneniyor...")
                        try:
                            subprocess.run(["git", "push", "--force"], check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                            log("Force push başarılı")
                            return True
                        except subprocess.CalledProcessError as e3:
                            log(f"Force push da başarısız: {e3.stderr or e3.stdout}")
                            return False
                else:
                    return False

        if not try_push():
            raise RuntimeError("Git push tüm yöntemlerle başarısız oldu")

    
        
    try:
        shutdown_url = f"http://{SERVER_HOST}:5000/kapat"
        shutdown_response = requests.get(shutdown_url, timeout=30)
        shutdown_response.raise_for_status()
        log(f"Sunucu kapatma isteği gönderildi: {shutdown_url} - Status: {shutdown_response.status_code}")
    except Exception as e:
        log(f"Sunucu kapatma hatası: {e}")

except subprocess.CalledProcessError as e:
    log(f"Git komut hatası: {e.stderr or e.stdout}")
except RuntimeError as e:
    log(str(e))
except Exception as e:
    log(f"Beklenmeyen hata: {e}")
import re
import requests
from flask import Flask, Response, abort, render_template_string, request, redirect, url_for, jsonify, send_from_directory
from datetime import datetime
import os
import signal
import json
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import html
import threading
import time

app = Flask(__name__)
CONFIG_FILE = "config.json"

def log(message):
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    try:
        with open("log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except IOError as e:
        print(f"Log dosyasına yazma hatası: {e}")

def sanitize_filename(filename):
    replacements = {
        'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
        'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'
    }
    for turkish, english in replacements.items():
        filename = filename.replace(turkish, english)
    filename = re.sub(r'\s+', '_', filename)
    filename = re.sub(r'[^A-Za-z0-9_.-]', '', filename)
    return filename

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                app.config["ONLY_HIGHEST"] = data.get("ONLY_HIGHEST", 1)
                
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
                        
                app.config["CHANNELS"] = migrated_channels
                log(f"Config yüklendi: ONLY_HIGHEST={app.config['ONLY_HIGHEST']}, {len(app.config.get('CHANNELS', []))} kanal bulundu.")
        except Exception as e:
            log(f"Config okuma hatası: {e}")
            app.config["ONLY_HIGHEST"] = 1
            app.config["CHANNELS"] = []
    else:
        log(f"{CONFIG_FILE} bulunamadı. Varsayılan config ile başlanıyor.")
        app.config["ONLY_HIGHEST"] = 1
        app.config["CHANNELS"] = []

def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            config_data = {
                "ONLY_HIGHEST": app.config.get("ONLY_HIGHEST", 1),
                "channels": app.config.get("CHANNELS", [])
            }
            json.dump(config_data, f, indent=4, ensure_ascii=False)
            log(f"Config kaydedildi: ONLY_HIGHEST={app.config['ONLY_HIGHEST']}")
    except Exception as e:
        log(f"Config kaydetme hatası: {e}")

@app.route('/')
def index():
    kanal_links = []
    load_config() 
    for channel_data in app.config.get('CHANNELS', []):
        name = channel_data.get('name', 'İsimsiz Kanal') # Yeni obje formatı
        filename = f"{sanitize_filename(name).upper()}.m3u8"
        kanal_links.append((name, filename))
        
    html_template = '''
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Yerel IPTV Server</title>
        <style>
            body { 
                background: #181818; color: #f1f1f1; 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 0;
                -webkit-text-size-adjust: 100%;
            }
            .container { 
                background: #232323;
                padding: 20px; 
                box-sizing: border-box;
                min-height: 100vh;
            }
            h1 { 
                color: #ff5252;
                text-align: center;
                font-size: 2em;
                margin-top: 0;
                padding-top: 20px;
            }
            a { 
                color: #90caf9;
                text-decoration: none;
            }
            ol {
                padding-left: 40px;
                max-width: 800px;
                margin: 20px auto;
            }
            li {
                background: #333;
                margin-bottom: 12px;
                border-radius: 8px;
                transition: transform 0.2s ease;
            }
            li:hover {
                transform: scale(1.02);
            }
            li a {
                display: block;
                padding: 18px 20px;
                font-size: 1.1em;
            }
            .button-container {
                text-align: center;
                margin-top: 30px;
                padding-bottom: 20px;
                display: flex;
                flex-direction: row; /* Düğmeleri yan yana getirmek için değiştirildi */
                flex-wrap: wrap;
                gap: 15px;
                justify-content: center; /* Yatayda ortalamak için eklendi */
            }
            .edit-link a {
                display: inline-block;
                background: #90caf9;
                color: #181818;
                padding: 12px 25px;
                border-radius: 8px;
                font-weight: bold;
                transition: background-color 0.2s ease;
            }
            .edit-link a:hover {
                background: #64b5f6;
                text-decoration: none;
            }
            .shutdown-link a {
                display: inline-block;
                background: #B22222;
                color: white;
                padding: 12px 25px;
                border-radius: 8px;
                font-weight: bold;
                transition: background-color 0.2s ease;
            }
            .shutdown-link a:hover {
                background: #C53333;
                text-decoration: none;
            }
            
            @media screen and (max-width: 600px) {
                h1 { font-size: 1.7em; }
                ol { padding-left: 30px; }
                li a { 
                    font-size: 1.2em;
                    padding: 20px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Yerel IPTV Server</h1>
            <ol>
                {% for kanal_adi, dosya_adi in kanal_links %}
                    <li><a href="/{{ dosya_adi }}" target="_blank">{{ kanal_adi }}</a></li>
                {% endfor %}
            </ol>
            <div class="button-container">
                <div class="edit-link">
                    <a href="/editor">Config Düzenle</a>
                </div>
                <div class="shutdown-link">
                    <a href="/kapat" onclick="return confirm('Sunucuyu kapatmak istediğinizden emin misiniz?');">Sunucuyu Kapat</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(html_template, kanal_links=kanal_links)

@app.route('/editor')
def editor():
    # editor.html dosyasının ana dizinde olduğunu varsayar
    return send_from_directory('.', 'editor.html')

@app.route('/api/channels', methods=['GET', 'POST'])
def api_channels():
    if request.method == 'GET':
        load_config()
        return jsonify({
            "channels": app.config.get("CHANNELS", []),
            "ONLY_HIGHEST": app.config.get("ONLY_HIGHEST", 1)
        })

    if request.method == 'POST':
        data = request.get_json()
        if data and 'channels' in data and isinstance(data['channels'], list):
            
            # Gelen veriyi doğrula ve temizle
            new_channels = []
            for item in data.get('channels', []):
                if isinstance(item, dict) and 'name' in item and 'url' in item:
                    new_channels.append({
                        "name": item.get("name", "").strip(),
                        "url": item.get("url", "").strip(),
                        "auto": item.get("auto", False)
                    })
            
            app.config['CHANNELS'] = new_channels
            app.config['ONLY_HIGHEST'] = data.get('ONLY_HIGHEST', 1)
            save_config()
            load_config() # Kaydedilen config'i tekrar yükle (doğrulama için)
            return jsonify({"message": "Config başarıyla güncellendi."}), 200
        
        return jsonify({"error": "Geçersiz veri formatı. Kanal listesi (channels) eksik veya formatı bozuk."}), 400

def clean_link(link):
    decoded_link = html.unescape(link)
    stripped_link = decoded_link.strip().rstrip("'\",)")
    return stripped_link

def scrape_m3u8_from_website(url):
    try:
        log(f"Web sitesi taranıyor: {url}")
        r = requests.get(url, timeout=15, verify=False, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        
        content = r.text
        regex_patterns = [
            r'(https?://[^\s"\'`<>]+?\.m3u8\?[^\s"\'`<>]*app=[^\s"\'`<>]+)',
            r'(https?://[^\s"\'`<>]+?\.m3u8\?[^\s"\'`<>]+)',
            r'(https?://[^\s"\'`<>]+?\.m3u8)'
        ]
        found_links = set()
        for pattern in regex_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                found_links.add(clean_link(match))
            if found_links:
                break
        log(f"{len(found_links)} adet M3U8 linki bulundu: {found_links}")
        return list(found_links)[0] if found_links else None
    except requests.RequestException as e:
        log(f"Web sitesi kazıma hatası ({url}): {e}")
        return None

def get_youtube_m3u8_url(video_or_channel_id):
    headers = {'origin': 'https://www.youtube.com', 'referer': 'https://www.youtube.com/', 'user-agent': 'Mozilla/5.0'}
    video_id = None
    if not video_or_channel_id.startswith(('UC', '@')):
        log(f"Girdi bir Video ID'si olarak kabul ediliyor: {video_or_channel_id}")
        video_id = video_or_channel_id
    else:
        live_url = None
        if video_or_channel_id.startswith('@'):
            log(f"Girdi bir Kanal Handle (@) olarak kabul ediliyor: {video_or_channel_id}")
            live_url = f"https://www.youtube.com/{video_or_channel_id}/live"
        else: # UC ile başlıyorsa
            log(f"Girdi bir Kanal ID (UC) olarak kabul ediliyor: {video_or_channel_id}")
            live_url = f"https://www.youtube.com/channel/{video_or_channel_id}/live"
        try:
            r = requests.get(live_url, headers=headers, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            canonical_link = soup.find("link", rel="canonical")
            if canonical_link and canonical_link.get("href"):
                match = re.search(r"v=([a-zA-Z0-9_-]{11})", canonical_link.get("href"))
                if match:
                    video_id = match.group(1)
                    log(f"Kanalın canlı yayın videosu bulundu: {video_id}")
        except requests.RequestException as e:
            log(f"Canlı yayın sayfası alınamadı ({live_url}): {e}")
            return None
    if not video_id:
        log(f"Canlı yayın videosu bulunamadı. Kanal çevrimdışı olabilir.")
        return None
    params = {'key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'}
    json_data = {'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20231101.05.00'}}, 'videoId': video_id}
    try:
        response = requests.post('https://www.youtube.com/youtubei/v1/player', params=params, headers=headers, json=json_data)
        response.raise_for_status()
        data = response.json()
        return data.get("streamingData", {}).get("hlsManifestUrl")
    except requests.RequestException as e:
        log(f"m3u8 URL alma hatası (video_id: {video_id}): {e}")
        return None

def search_youtube_innertube(query):
    """YouTube InnerTube API kullanarak canlı yayın araması yapar."""
    log(f"InnerTube ile YouTube araması yapılıyor: '{query}'")
    headers = {'origin': 'https://www.youtube.com', 'referer': 'https://www.youtube.com/', 'user-agent': 'Mozilla/5.0'}
    payload = {
        'context': {
            'client': {
                'clientName': 'WEB',
                'clientVersion': '2.20240101.00.00'
            }
        },
        'query': query,
        'params': 'EgJAAQ%3D%3D'
    }
    
    try:
        response = requests.post('https://www.youtube.com/youtubei/v1/search', headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        contents = data.get('contents', {}) \
                       .get('twoColumnSearchResultsRenderer', {}) \
                       .get('primaryContents', {}) \
                       .get('sectionListRenderer', {}) \
                       .get('contents', [{}])[0] \
                       .get('itemSectionRenderer', {}) \
                       .get('contents', [])

        for item in contents:
            if 'videoRenderer' in item:
                video_id = item['videoRenderer'].get('videoId')
                badges = item['videoRenderer'].get('badges', [])
                is_live = any(
                    badge.get('metadataBadgeRenderer', {}).get('style') == 'BADGE_STYLE_TYPE_LIVE_NOW'
                    for badge in badges
                )
                if video_id and is_live:
                    log(f"Canlı yayın bulundu: Video ID = {video_id}")
                    return video_id
        
        for item in contents:
            if 'videoRenderer' in item and item['videoRenderer'].get('videoId'):
                video_id = item['videoRenderer'].get('videoId')
                log(f"Canlı yayın bulunamadı, ilk sonuç döndürülüyor: Video ID = {video_id}")
                return video_id

    except requests.RequestException as e:
        log(f"YouTube arama (InnerTube) hatası: {e}")
    except (KeyError, IndexError) as e:
        log(f"YouTube arama yanıtını işleme hatası: {e}")
    
    return None

def search_youtube_channel(query):
    """YouTube InnerTube API kullanarak kanal araması yapar."""
    log(f"InnerTube ile YouTube Kanal araması yapılıyor: '{query}'")
    headers = {'origin': 'https://www.youtube.com', 'referer': 'https://www.youtube.com/', 'user-agent': 'Mozilla/5.0'}
    payload = {
        'context': {
            'client': {
                 'clientName': 'WEB',
                 'clientVersion': '2.20240101.00.00'
            }
        },
        'query': query,
        'params': 'EgIQAg=='
    }
    
    try:
        response = requests.post('https://www.youtube.com/youtubei/v1/search', headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        contents = data.get('contents', {}) \
                       .get('twoColumnSearchResultsRenderer', {}) \
                       .get('primaryContents', {}) \
                       .get('sectionListRenderer', {}) \
                       .get('contents', [{}])[0] \
                       .get('itemSectionRenderer', {}) \
                       .get('contents', [])

        for item in contents:
            if 'channelRenderer' in item:
                channel_id = item['channelRenderer'].get('channelId')
                if channel_id:
                    log(f"Kanal bulundu: ID = {channel_id}")
                    return channel_id

    except requests.RequestException as e:
        log(f"YouTube Kanal Arama (InnerTube) hatası: {e}")
    except (KeyError, IndexError) as e:
        log(f"YouTube Kanal Arama yanıtını işleme hatası: {e}")
        
    return None

@app.route('/api/youtube-search', methods=['POST'])
def api_youtube_search():
    data = request.get_json()
    query = data.get('query')
    if not query:
        return jsonify({"error": "Arama sorgusu eksik."}), 400
    
    video_id = search_youtube_innertube(query)
    
    if video_id:
        return jsonify({"videoId": video_id}), 200
    else:
        return jsonify({"error": "Sonuç bulunamadı."}), 404

@app.route('/api/youtube-channel-search', methods=['POST'])
def api_youtube_channel_search():
    data = request.get_json()
    query = data.get('query')
    if not query:
        return jsonify({"error": "Arama sorgusu eksik."}), 400
    
    channel_id = search_youtube_channel(query)
    
    if channel_id:
        return jsonify({"channelId": channel_id}), 200
    else:
        return jsonify({"error": "Kanal bulunamadı."}), 404

# ===================================================================
# === YENİ YARDIMCI FONKSİYON =======================================
# ===================================================================
def serve_offline_stream():
    """'Yayın Yok' master playlist'ini okur ve bir Flask Response olarak döndürür."""
    # Bu dosya github.pyw tarafından oluşturulur ve mutlak GitHub URL'leri içerir
    offline_playlist_path = os.path.join('offline_stream', 'offline_master.m3u8')
    try:
        with open(offline_playlist_path, "r", encoding="utf-8") as f:
            content = f.read()
        log("Bir kanal için 'Yayın Yok' (offline) akışının içeriği sunuluyor.")
        return Response(content, content_type='application/vnd.apple.mpegurl')
    except FileNotFoundError:
        log(f"KRİTİK HATA: {offline_playlist_path} dosyası bulunamadı! github.pyw scriptini çalıştırdığınızdan emin olun.")
        # Bu, yalnızca offline_master.m3u8 dosyası eksikse görünür
        return "Çevrimdışı akış dosyası sunucuda eksik. Lütfen 'github.pyw' scriptini çalıştırın.", 404
    except Exception as e:
        log(f"Offline stream sunulurken hata oluştu: {e}")
        return "Sunucu hatası (offline stream).", 500
# ===================================================================
# === SON ===========================================================
# ===================================================================


@app.route('/offline_stream/<path:filename>')
def offline_stream_files(filename):
    """
    Çevrimdışı 'Yayın Yok' HLS segmentlerini ve playlistlerini sunar.
    NOT: Bu rota artık ana hata yönetimi için kullanılmıyor, ancak
    github.pyw tarafından oluşturulan offline_master.m3u8 (GitHub linkli)
    içeriği sunulduğu için, istemciler segmentleri (.ts) doğrudan GitHub'dan 
    çekecektir. Bu rota yine de bir yedek olarak veya
    yerel testler için tutulabilir.
    """
    log(f"Çevrimdışı akış dosyası isteniyor (eski yol): {filename}")
    return send_from_directory('offline_stream', filename, cache_timeout=0)


@app.route('/<m3u8_file>')
def stream_m3u8(m3u8_file):
    if not m3u8_file.endswith('.m3u8'):
        abort(404)
        
    # 'offline_master.m3u8' için özel kontrol (doğrudan istek gelirse)
    if m3u8_file == "offline_master.m3u8":
        log("Offline master playlist doğrudan istendi...")
        return serve_offline_stream()

    # Yeni obje formatına göre arama
    channel_info = next((ch for ch in app.config.get('CHANNELS', [])
                         if f"{sanitize_filename(ch.get('name', 'INVALID_NAME')).upper()}.m3u8" == m3u8_file), None)
    
    if not channel_info:
        log(f"Kanal bulunamadı: {m3u8_file}")
        abort(404)
    
    channel_name = channel_info.get('name')
    channel_id = channel_info.get('url') # URL veya YouTube ID
    
    m3u8_url = None
    
    # 1. ÖNCE: Linkin doğrudan .m3u8 olup olmadığını kontrol et
    if channel_id.endswith('.m3u8'):
        log(f"Direkt M3U8 linki işleniyor: {channel_name} ({channel_id})")
        m3u8_url = channel_id
    
    # 2. SONRA: Web sitesi (scrape edilecek) olup olmadığını kontrol et
    elif channel_id.startswith(('http://', 'https://')):
        log(f"Web sitesi kanalı işleniyor: {channel_name} ({channel_id})")
        m3u8_url = scrape_m3u8_from_website(channel_id)

    # 3. SONRA: YouTube kanalı/videosu olup olmadığını kontrol et
    else:
        log(f"YouTube kanalı/videosu işleniyor: {channel_name} ({channel_id})")
        m3u8_url = get_youtube_m3u8_url(channel_id)
        
    # ===================================================================
    # === GÜNCELLENMİŞ HATA YÖNETİMİ ===================================
    # ===================================================================
    if not m3u8_url:
        log(f"'{channel_name}' için nihai m3u8 URL'si alınamadı. 'Yayın Yok' içeriği sunuluyor.")
        # Hata vermek veya yönlendirmek yerine offline akışın İÇERİĞİNİ sun
        return serve_offline_stream()
    # ===================================================================
    # === SON ===========================================================
    # ===================================================================
        
    log(f"Alınan M3U8 adresi: {m3u8_url}")

    try:
        headers = {'user-agent': 'Mozilla/5.0'}
        r = requests.get(m3u8_url, headers=headers, timeout=15)
        r.raise_for_status()
        
        original_lines = r.text.splitlines()
        processed_lines = [] # Bütün URL'lerin mutlak hale getirildiği liste
        
        # Göreli URL'leri çözmek için M3U8'in kendi URL'ini temel al
        base_to_use = m3u8_url
        
        for line in original_lines:
            line = line.strip()
            if not line:
                continue
            
            # Eğer satır bir tag değilse (#) VE http ile başlamıyorsa, bu göreli bir URL'dir.
            if not line.startswith('#') and not line.startswith('http'):
                line = urljoin(base_to_use, line)
            
            processed_lines.append(line)

        # --- ONLY_HIGHEST / Stream Parse Mantığı ---
        streams = []
        for i, line in enumerate(processed_lines):
            if line.startswith('#EXT-X-STREAM-INF'):
                resolution_match = re.search(r'RESOLUTION=(\d+x\d+)', line)
                resolution_str = "0x0"
                if resolution_match:
                    resolution_str = resolution_match.group(1)

                if i + 1 < len(processed_lines) and processed_lines[i+1] and not processed_lines[i+1].startswith('#'):
                    stream_url = processed_lines[i+1]
                    streams.append((line, stream_url, resolution_str))

        if not streams:
            log(f"Master playlist (akış listesi) bulunamadı. Göreli URL'ler düzeltilmiş içerik döndürülüyor.")
            return Response('\n'.join(processed_lines), content_type='application/vnd.apple.mpegurl')
        
        if app.config.get("ONLY_HIGHEST", 1):
            try:
                highest_stream = max(streams, key=lambda x: int(x[2].split('x')[1]))
                new_m3u8_content = ['#EXTM3U', '#EXT-X-INDEPENDENT-SEGMENTS', highest_stream[0], highest_stream[1]]
            except Exception as e:
                log(f"En yüksek çözürlük bulunamadı ({e}), ilk akış seçiliyor.")
                new_m3u8_content = ['#EXTM3U', '#EXT-X-INDEPENDENT-SEGMENTS', streams[0][0], streams[0][1]]
        else:
            new_m3u8_content = ['#EXTM3U', '#EXT-X-INDEPENDENT-SEGMENTS']
            for s in streams:
                new_m3u8_content.extend([s[0], s[1]])

        return Response('\n'.join(new_m3u8_content), content_type='application/vnd.apple.mpegurl')
    
    # ===================================================================
    # === GÜNCELLENMİŞ HATA YÖNETİMİ ===================================
    # ===================================================================
    except requests.RequestException as e:
        log(f"Nihai m3u8 içeriği indirilemedi ({m3u8_url}): {e}. 'Yayın Yok' içeriği sunuluyor.")
        # Hata vermek veya yönlendirmek yerine offline akışın İÇERİĞİNİ sun
        return serve_offline_stream()
    # ===================================================================
    # === SON ===========================================================
    # ===================================================================

def delayed_shutdown():
    time.sleep(1)
    os.kill(os.getpid(), signal.SIGINT)

@app.route('/kapat')
def shutdown():
    log("Sunucu kapatma isteği alındı. Yanıt gönderiliyor ve sunucu kapatılacak.")
    threading.Thread(target=delayed_shutdown).start()
    return "Sunucu kapatılıyor..."

@app.errorhandler(404)
def page_not_found(e):
    log(f"404 hatası: {str(e)}")
    return render_template_string('<body style="background: #181818; color: #f1f1f1; text-align: center;"><h1>404 - Kanal veya Dosya Bulunamadı</h1><p><a href="/">Ana Sayfaya Dön</a></p></body>'), 404

if __name__ == "__main__":
    load_config()
    # 'offline_stream' klasörünün var olduğundan emin ol
    os.makedirs("offline_stream", exist_ok=True)
    log("Flask streaming server başlatılıyor: http://0.0.0.0:5000/")
    app.run(host="0.0.0.0", port=5000)
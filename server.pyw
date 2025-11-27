import re
import requests
from flask import Flask, Response, abort, render_template_string, request, jsonify, send_from_directory
from datetime import datetime
import os
import signal
import json
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import html
import threading
import time
import urllib3
import subprocess # Gerekli kütüphane eklendi

# SSL sertifika hatalarını konsola basmamak için
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CONFIG_FILE = "config.json"

def log(message):
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    try:
        with open("log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except IOError as e:
        print(f"Log hatası: {e}")

def sanitize_filename(filename):
    replacements = {'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u', 'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'}
    for tr, en in replacements.items():
        filename = filename.replace(tr, en)
    filename = re.sub(r'\s+', '_', filename)
    filename = re.sub(r'[^A-Za-z0-9_.-]', '', filename)
    return filename

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                app.config["ONLY_HIGHEST"] = data.get("ONLY_HIGHEST", 1)
                app.config["VIEW_MODE"] = data.get("VIEW_MODE", 0) 
                
                channels_raw = data.get("channels", [])
                migrated = []
                for ch in channels_raw:
                    if isinstance(ch, list):
                        migrated.append({"name": ch[0] if len(ch)>0 else "", "url": ch[1] if len(ch)>1 else "", "auto": ch[2] if len(ch)>2 else False})
                    elif isinstance(ch, dict):
                        migrated.append({"name": ch.get("name", ""), "url": ch.get("url", ""), "auto": ch.get("auto", False)})
                app.config["CHANNELS"] = migrated
        except Exception as e:
            log(f"Config okuma hatası: {e}")
            app.config["CHANNELS"] = []
    else:
        app.config["CHANNELS"] = []
        app.config["ONLY_HIGHEST"] = 1
        app.config["VIEW_MODE"] = 0

def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            config_data = {
                "ONLY_HIGHEST": app.config.get("ONLY_HIGHEST", 1),
                "VIEW_MODE": app.config.get("VIEW_MODE", 0),
                "channels": app.config.get("CHANNELS", [])
            }
            json.dump(config_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log(f"Config kaydetme hatası: {e}")

@app.route('/')
def index():
    load_config()
    kanal_links = []
    for channel_data in app.config.get('CHANNELS', []):
        name = channel_data.get('name', 'İsimsiz')
        filename = f"{sanitize_filename(name).upper()}.m3u8"
        kanal_links.append((name, filename))
    
    view_mode = app.config.get("VIEW_MODE", 0)

    # --- HTML ŞABLONU GÜNCELLENDİ (OTOMASYON, EMOJİSİZ, TÜRKÇE) ---
    html_template = '''
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IPTV Server</title>
        <style>
            body { background: #181818; color: #f1f1f1; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; }
            .container { background: #232323; padding: 20px; min-height: 100vh; max-width: 1200px; margin: 0 auto; }
            h1 { color: #ff5252; text-align: center; margin-top: 0; padding-top: 10px; }
            a { color: #90caf9; text-decoration: none; }
            
            /* TABLO STİLLERİ */
            .channel-table { width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 20px; background: #333; border-radius: 8px; overflow: hidden; }
            .channel-table th, .channel-table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #444; vertical-align: middle; }
            .channel-table th { background: #2c2c2c; color: #ff5252; text-transform: uppercase; font-size: 0.85em; letter-spacing: 1px; }
            .channel-table tr:hover { background: #3a3a3a; transition: background 0.2s; }
            .channel-table td a { font-weight: 600; font-size: 1.1em; display: block; }
            
            /* DETAYLI MOD (3 Sütun) */
            .status-cell { display: flex; align-items: center; gap: 8px; font-size: 0.9em; }
            .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
            .dot.operational { background: #238636; box-shadow: 0 0 5px #238636; }
            .dot.outage { background: #da3633; box-shadow: 0 0 5px #da3633; }
            .dot.checking { background: #e3b341; animation: pulse 1s infinite; }

            /* EYLEM ODAKLI MOD */
            .action-badge {
                display: inline-flex; flex-direction: column; align-items: center; justify-content: center;
                padding: 6px 12px; border-radius: 6px; min-width: 110px; text-align: center;
                transition: transform 0.2s; cursor: default;
            }
            .action-badge:hover { transform: scale(1.02); }
            
            .action-title { font-weight: 800; font-size: 0.95em; text-transform: uppercase; letter-spacing: 0.5px; line-height: 1.2; }
            .action-reason { font-weight: 400; font-size: 0.75em; opacity: 0.9; margin-top: 2px; }

            /* Renk Temaları */
            .theme-success { background: rgba(35, 134, 54, 0.2); border: 1px solid #238636; color: #4cd964; }
            .theme-purple  { background: rgba(142, 68, 173, 0.2); border: 1px solid #8e44ad; color: #d2b4de; }
            .theme-orange  { background: rgba(211, 84, 0, 0.2); border: 1px solid #d35400; color: #e59866; }
            .theme-red     { background: rgba(192, 57, 43, 0.2); border: 1px solid #c0392b; color: #e6b0aa; }
            .theme-gray    { background: rgba(127, 140, 141, 0.2); border: 1px solid #7f8c8d; color: #bdc3c7; }
            .theme-check   { background: rgba(241, 196, 15, 0.1); border: 1px solid #f1c40f; color: #f1c40f; animation: pulse 1.5s infinite; }

            @keyframes pulse { 0% { opacity: 0.6; } 50% { opacity: 1; } 100% { opacity: 0.6; } }

            .btn-group { margin-top: 30px; text-align: center; display: flex; justify-content: center; gap: 15px; }
            .btn { padding: 10px 20px; border-radius: 5px; font-weight: bold; background: #333; color: white; border: 1px solid #555; }
            .btn:hover { background: #444; }
            .btn-red { background: #922b21; border-color: #c0392b; }
            .btn-red:hover { background: #c0392b; }

            @media (max-width: 600px) {
                .container { padding: 10px; }
                .channel-table th, .channel-table td { padding: 10px 5px; }
                .action-badge { min-width: 90px; padding: 5px 8px; }
                .action-title { font-size: 0.85em; }
                .action-reason { font-size: 0.7em; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>IPTV Server</h1>
            <table class="channel-table">
                <thead>
                    <tr>
                        <th style="width: 30px; text-align: center;">#</th>
                        <th>Kanal</th>
                        {% if view_mode == 0 %}
                            <th>Kaynak</th>
                            <th>GitHub</th>
                            <th>Yayın</th>
                        {% else %}
                            <th style="text-align: center; width: 140px;">Durum & Eylem</th>
                        {% endif %}
                    </tr>
                </thead>
                <tbody>
                {% for kanal_adi, dosya_adi in kanal_links %}
                    <tr>
                        <td style="text-align: center; color: #666;">{{ loop.index }}</td>
                        <td>
                            <a href="/{{ dosya_adi }}" target="_blank">{{ kanal_adi }}</a>
                        </td>
                        
                        {% if view_mode == 0 %}
                            <td><div class="status-cell" id="status-source-{{ loop.index }}"><span class="dot checking"></span><span class="text">...</span></div></td>
                            <td><div class="status-cell" id="status-github-{{ loop.index }}"><span class="dot checking"></span><span class="text">...</span></div></td>
                            <td><div class="status-cell" id="status-stream-{{ loop.index }}"><span class="dot checking"></span><span class="text">...</span></div></td>
                        {% else %}
                            <td style="text-align: center;">
                                <div id="status-action-{{ loop.index }}">
                                    <div class="action-badge theme-check">
                                        <span class="action-title">ANALİZ</span>
                                        <span class="action-reason">Kontrol Ediliyor...</span>
                                    </div>
                                </div>
                            </td>
                        {% endif %}
                    </tr>
                {% endfor %}
                </tbody>
            </table>

            <div class="btn-group">
                <a href="/editor" class="btn">Ayarlar & Görünüm</a>
                
                <button id="manualUpdateBtn" onclick="runUpdate(false)" class="btn" style="display:none; background:#e67e22; border-color:#d35400; cursor:pointer;">
                    Manuel Güncelle (Zorla)
                </button>

                <a href="/kapat" class="btn btn-red" onclick="return confirm('Sunucu kapatılsın mı?');">Sunucuyu Kapat</a>
            </div>
            
            <div id="auto-status" style="text-align:center; margin-top:15px; font-weight:bold; color:#f1c40f; display:none;"></div>
        </div>

        <script>
            const channels = {{ kanal_links | tojson }};
            const VIEW_MODE = {{ view_mode }};
            let autoHealTriggered = false; // Tekrarı önlemek için session flag

            function updateDetailedUI(index, type, status, msg) {
                const el = document.getElementById(`status-${type}-${index}`);
                if(!el) return;
                const dot = el.querySelector('.dot');
                const txt = el.querySelector('.text');
                if(status === 'operational') {
                    dot.className = 'dot operational';
                    txt.textContent = 'OK';
                    txt.style.color = '#4cd964';
                } else {
                    dot.className = 'dot outage';
                    txt.textContent = msg || 'Hata';
                    txt.style.color = '#e74c3c';
                }
            }

            // Eylem Modu UI Güncelleme (Action + Reason) + OTO İYİLEŞTİRME TETİĞİ
            function updateActionUI(index, data) {
                const el = document.getElementById(`status-action-${index}`);
                if(!el) return;
                
                el.innerHTML = `
                    <div class="action-badge ${data.theme}">
                        <span class="action-title">${data.action}</span>
                        <span class="action-reason">${data.reason}</span>
                    </div>
                `;

                // --- OTO İYİLEŞTİRME MANTIĞI ---
                // Eğer Eylem "YENİLE" veya "YÜKLE" içeriyorsa ve henüz bu oturumda tetiklemediysek
                if (VIEW_MODE === 1 && (data.action.includes('YENİLE') || data.action.includes('YÜKLE')) && !autoHealTriggered ) {
                    attemptAutoHeal();
                }
            }

            function attemptAutoHeal() {
                autoHealTriggered = true; // Flag'i kaldır, bir daha deneme
                
                const lastRun = localStorage.getItem('lastAutoHealTime');
                const now = Date.now();
                const COOLDOWN = 300000; // 5 Dakika (Milisaniye cinsinden)

                // Eğer son 5 dakikada zaten çalıştırdıysak tekrar yapma, Butonu göster
                if (lastRun && (now - lastRun < COOLDOWN)) {
                    document.getElementById('manualUpdateBtn').style.display = 'inline-block';
                    const sDiv = document.getElementById('auto-status');
                    sDiv.style.display = 'block';
                    // Emoji yok, Türkçe var:
                    sDiv.innerText = "Otomatik onarım yakın zamanda denendi. Sorun devam ediyorsa butona basın.";
                    return;
                }

                // Süre geçmiş veya ilk kez deneniyor: OTO BAŞLAT
                runUpdate(true);
            }

            async function runUpdate(isAuto) {
                if (!isAuto) {
                    if(!confirm("Güncelleme betiği manuel çalıştırılsın mı?\\n\\nBu işlem sunucuyu kapatacaktır.")) return;
                } else {
                    // Otomatik modda kullanıcıya bilgi ver
                    const statusDiv = document.getElementById('auto-status');
                    statusDiv.style.display = 'block';
                    // Emoji yok, Türkçe var:
                    statusDiv.innerHTML = "Sorun tespit edildi. Otomatik onarım başlatılıyor... <br> (Sunucu birazdan kapanacak)";
                }

                // Zaman damgasını kaydet
                localStorage.setItem('lastAutoHealTime', Date.now());

                try {
                    await fetch('/api/trigger_update');
                    if (!isAuto) alert("İşlem başlatıldı. Sunucu kapanacak.");
                } catch(e) {
                    console.error("API Hatası:", e);
                    // Hata olursa butonu yine de göster
                    document.getElementById('manualUpdateBtn').style.display = 'inline-block';
                }
            }

            async function checkChannel(name, index) {
                let sSrc = { status: 'checking' };
                let sGit = { status: 'checking' };
                let sStrm = { status: 'checking' };
                
                // 1. Kaynak Kontrolü
                try {
                    let r = await fetch('/api/check_status', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ name: name, type: 'source' }) });
                    sSrc = await r.json();
                    if(VIEW_MODE === 0) updateDetailedUI(index, 'source', sSrc.status, 'Yok');
                } catch(e) { sSrc.status = 'outage'; }

                // 2. GitHub Kontrolü
                try {
                    let r = await fetch('/api/check_status', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ name: name, type: 'github' }) });
                    sGit = await r.json();
                    if(VIEW_MODE === 0) updateDetailedUI(index, 'github', sGit.status, 'Yok');
                } catch(e) { sGit.status = 'outage'; }

                // 3. Yayın Kontrolü
                try {
                    let r = await fetch('/api/check_status', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ name: name, type: 'stream' }) });
                    sStrm = await r.json();
                    if(VIEW_MODE === 0) updateDetailedUI(index, 'stream', sStrm.status, sStrm.error);
                } catch(e) { sStrm.status = 'outage'; sStrm.error = 'Hata'; }

                // --- EYLEM KARAR MOTORU ---
                if (VIEW_MODE === 1) {
                    let result = { action: '?', reason: '?', theme: 'theme-gray' };
                    const isSrcOK = sSrc.status === 'operational';
                    const isGitOK = sGit.status === 'operational';
                    const isStrmOK = sStrm.status === 'operational';
                    const is403 = sStrm.error && sStrm.error.includes('403');
                    const is404 = sStrm.error && sStrm.error.includes('404');
                    
                    if (isSrcOK && isGitOK && isStrmOK) {
                        result = { action: 'OYNAT', reason: 'Yayın Aktif', theme: 'theme-success' };
                    }
                    else if (isSrcOK && isGitOK && !isStrmOK) {
                        if (is403) {
                            result = { action: 'YENİLE', reason: 'Token Bitti', theme: 'theme-purple' };
                        } else if (is404) {
                            result = { action: 'ID BUL', reason: 'Video Silindi', theme: 'theme-red' };
                        } else {
                            result = { action: 'YENİLE', reason: 'Yayın Hatası', theme: 'theme-purple' };
                        }
                    }
                    else if (isSrcOK && !isGitOK) {
                        result = { action: 'YÜKLE', reason: 'Dosya Yok', theme: 'theme-orange' };
                    }
                    else if (!isSrcOK && isGitOK && !isStrmOK) {
                        result = { action: 'BEKLE', reason: 'Kanal Kapalı', theme: 'theme-red' };
                    }
                    else if (!isSrcOK && isGitOK && isStrmOK) {
                        result = { action: 'İZLE', reason: 'Kaynak Koptu', theme: 'theme-success' };
                    }
                    else {
                         result = { action: 'DÜZELT', reason: 'Kaynak Yok', theme: 'theme-gray' };
                    }

                    updateActionUI(index, result);
                }
            }

            channels.forEach((ch, i) => {
                setTimeout(() => checkChannel(ch[0], i + 1), i * 300);
            });
        </script>
    </body>
    </html>
    '''
    return render_template_string(html_template, kanal_links=kanal_links, view_mode=view_mode)

@app.route('/editor')
def editor():
    return send_from_directory('.', 'editor.html')

@app.route('/api/channels', methods=['GET', 'POST'])
def api_channels():
    if request.method == 'GET':
        load_config()
        return jsonify({
            "channels": app.config.get("CHANNELS", []),
            "ONLY_HIGHEST": app.config.get("ONLY_HIGHEST", 1),
            "VIEW_MODE": app.config.get("VIEW_MODE", 0)
        })

    if request.method == 'POST':
        data = request.get_json()
        if data and 'channels' in data and isinstance(data['channels'], list):
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
            app.config['VIEW_MODE'] = data.get('VIEW_MODE', 0)
            save_config()
            load_config()
            return jsonify({"message": "Config başarıyla güncellendi."}), 200
        return jsonify({"error": "Geçersiz veri formatı."}), 400

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
        log(f"{len(found_links)} adet M3U8 linki bulundu.")
        return list(found_links)[0] if found_links else None
    except requests.RequestException as e:
        log(f"Web sitesi kazıma hatası ({url}): {e}")
        return None

def get_youtube_m3u8_url(video_or_channel_id):
    headers = {'origin': 'https://www.youtube.com', 'referer': 'https://www.youtube.com/', 'user-agent': 'Mozilla/5.0'}
    video_id = None
    if not video_or_channel_id.startswith(('UC', '@')):
        video_id = video_or_channel_id
    else:
        live_url = None
        if video_or_channel_id.startswith('@'):
            live_url = f"https://www.youtube.com/{video_or_channel_id}/live"
        else:
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
        except requests.RequestException as e:
            log(f"Canlı yayın sayfası alınamadı: {e}")
            return None
    
    if not video_id:
        return None
    
    params = {'key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'}
    json_data = {'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20231101.05.00'}}, 'videoId': video_id}
    try:
        response = requests.post('https://www.youtube.com/youtubei/v1/player', params=params, headers=headers, json=json_data)
        response.raise_for_status()
        data = response.json()
        return data.get("streamingData", {}).get("hlsManifestUrl")
    except requests.RequestException as e:
        log(f"m3u8 URL alma hatası: {e}")
        return None

def search_youtube_innertube(query):
    headers = {'origin': 'https://www.youtube.com', 'referer': 'https://www.youtube.com/', 'user-agent': 'Mozilla/5.0'}
    payload = {
        'context': {'client': { 'clientName': 'WEB', 'clientVersion': '2.20240101.00.00' }},
        'query': query,
        'params': 'EgJAAQ%3D%3D'
    }
    try:
        response = requests.post('https://www.youtube.com/youtubei/v1/search', headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [{}])[0].get('itemSectionRenderer', {}).get('contents', [])
        for item in contents:
            if 'videoRenderer' in item:
                video_id = item['videoRenderer'].get('videoId')
                badges = item['videoRenderer'].get('badges', [])
                is_live = any(badge.get('metadataBadgeRenderer', {}).get('style') == 'BADGE_STYLE_TYPE_LIVE_NOW' for badge in badges)
                if video_id and is_live:
                    return video_id
        for item in contents:
            if 'videoRenderer' in item and item['videoRenderer'].get('videoId'):
                return item['videoRenderer'].get('videoId')
    except Exception as e:
        log(f"YouTube arama hatası: {e}")
    return None

def search_youtube_channel(query):
    headers = {'origin': 'https://www.youtube.com', 'referer': 'https://www.youtube.com/', 'user-agent': 'Mozilla/5.0'}
    payload = {
        'context': {'client': { 'clientName': 'WEB', 'clientVersion': '2.20240101.00.00' }},
        'query': query,
        'params': 'EgIQAg=='
    }
    try:
        response = requests.post('https://www.youtube.com/youtubei/v1/search', headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [{}])[0].get('itemSectionRenderer', {}).get('contents', [])
        for item in contents:
            if 'channelRenderer' in item:
                return item['channelRenderer'].get('channelId')
    except Exception as e:
        log(f"YouTube Kanal Arama hatası: {e}")
    return None

@app.route('/api/youtube-search', methods=['POST'])
def api_youtube_search():
    data = request.get_json()
    query = data.get('query')
    if not query: return jsonify({"error": "Eksik"}), 400
    video_id = search_youtube_innertube(query)
    if video_id: return jsonify({"videoId": video_id}), 200
    return jsonify({"error": "Bulunamadı"}), 404

@app.route('/api/youtube-channel-search', methods=['POST'])
def api_youtube_channel_search():
    data = request.get_json()
    query = data.get('query')
    if not query: return jsonify({"error": "Eksik"}), 400
    channel_id = search_youtube_channel(query)
    if channel_id: return jsonify({"channelId": channel_id}), 200
    return jsonify({"error": "Bulunamadı"}), 404

def resolve_channel_url(channel_info):
    channel_name = channel_info.get('name')
    channel_id = channel_info.get('url') 
    m3u8_url = None
    if channel_id.endswith('.m3u8'):
        m3u8_url = channel_id
    elif channel_id.startswith(('http://', 'https://')):
        m3u8_url = scrape_m3u8_from_website(channel_id)
    else:
        m3u8_url = get_youtube_m3u8_url(channel_id)
    return m3u8_url, channel_name

@app.route('/api/check_status', methods=['POST'])
def api_check_status():
    data = request.get_json()
    channel_name = data.get('name')
    check_type = data.get('type', 'github')
    
    if not channel_name: return jsonify({"status": "outage", "error": "No name"}), 400

    filename = f"{sanitize_filename(channel_name).upper()}.m3u8"
    github_url = None
    try:
        if os.path.exists("tv.m3u8"):
            with open("tv.m3u8", "r", encoding="utf-8") as f:
                for line in f:
                    if filename in line and line.strip().startswith("http"):
                        github_url = line.strip()
                        break
    except: pass

    if check_type == 'github':
        if not github_url: return jsonify({"status": "outage", "error": "Playlist'te Yok"}), 200
        try:
            r = requests.get(github_url, headers={'user-agent': 'Mozilla/5.0'}, timeout=5)
            if r.status_code == 200: return jsonify({"status": "operational"}), 200
            return jsonify({"status": "outage", "code": r.status_code}), 200
        except Exception as e: return jsonify({"status": "outage", "error": str(e)}), 200

    elif check_type == 'stream':
        if not github_url: return jsonify({"status": "outage", "error": "Dosya Yok"}), 200
        try:
            headers = {'user-agent': 'Mozilla/5.0'}
            r = requests.get(github_url, headers=headers, timeout=5)
            if r.status_code != 200: return jsonify({"status": "outage", "error": "Github Dosya Hatası"}), 200

            stream_url = None
            for line in r.text.splitlines():
                if line.strip() and not line.strip().startswith('#') and line.strip().startswith('http'):
                    stream_url = line.strip()
                    break
            
            if stream_url:
                try:
                    r_stream = requests.get(stream_url, headers=headers, stream=True, timeout=5, verify=False)
                    if r_stream.status_code < 400:
                        return jsonify({"status": "operational"}), 200
                    else:
                        # 403 ve 404 ayrımı için hata kodunu döndür
                        return jsonify({"status": "outage", "error": f"Hata ({r_stream.status_code})"}), 200
                except: return jsonify({"status": "outage", "error": "Timeout"}), 200
            else: return jsonify({"status": "outage", "error": "Boş İçerik"}), 200
        except Exception as e: return jsonify({"status": "outage", "error": str(e)}), 200

    elif check_type == 'source':
        load_config()
        ch = next((c for c in app.config.get('CHANNELS', []) if c.get('name') == channel_name), None)
        if not ch: return jsonify({"status": "outage", "error": "Config Yok"}), 200
        try:
            m3u8, _ = resolve_channel_url(ch)
            if m3u8: return jsonify({"status": "operational"}), 200
            return jsonify({"status": "outage", "error": "Bulunamadı"}), 200
        except Exception as e: return jsonify({"status": "outage", "error": str(e)}), 200
            
    return jsonify({"status": "outage", "error": "Geçersiz"}), 400

@app.route('/<m3u8_file>')
def stream_m3u8(m3u8_file):
    if not m3u8_file.endswith('.m3u8'): abort(404)
    channel_info = next((ch for ch in app.config.get('CHANNELS', []) if f"{sanitize_filename(ch.get('name', '')).upper()}.m3u8" == m3u8_file), None)
    if not channel_info: abort(404)
    
    m3u8_url, _ = resolve_channel_url(channel_info)
    if not m3u8_url: abort(404)

    try:
        r = requests.get(m3u8_url, headers={'user-agent': 'Mozilla/5.0'}, timeout=15, verify=False)
        r.raise_for_status()
        
        processed_lines = []
        base_to_use = m3u8_url
        for line in r.text.splitlines():
            line = line.strip()
            if not line: continue
            if not line.startswith('#') and not line.startswith('http'):
                line = urljoin(base_to_use, line)
            processed_lines.append(line)

        streams = []
        for i, line in enumerate(processed_lines):
            if line.startswith('#EXT-X-STREAM-INF'):
                resolution_match = re.search(r'RESOLUTION=(\d+x\d+)', line)
                resolution_str = resolution_match.group(1) if resolution_match else "0x0"
                if i + 1 < len(processed_lines) and not processed_lines[i+1].startswith('#'):
                    streams.append((line, processed_lines[i+1], resolution_str))

        if not streams:
            return Response('\n'.join(processed_lines), content_type='application/vnd.apple.mpegurl')
        
        content = ['#EXTM3U', '#EXT-X-INDEPENDENT-SEGMENTS']
        if app.config.get("ONLY_HIGHEST", 1):
            try:
                highest = max(streams, key=lambda x: int(x[2].split('x')[1]))
                content.extend([highest[0], highest[1]])
            except:
                content.extend([streams[0][0], streams[0][1]])
        else:
            for s in streams: content.extend([s[0], s[1]])

        return Response('\n'.join(content), content_type='application/vnd.apple.mpegurl')
    except: abort(404)

# --- YENİ EKLENEN API: OTOMATİK GÜNCELLEME TETİKLEYİCİSİ ---
@app.route('/api/trigger_update')
def trigger_update():
    try:
        # github.pyw dosyasını başlatır
        subprocess.Popen(["python", "github.pyw"], shell=True)
        return jsonify({"status": "started", "message": "Onarım başlatıldı."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def delayed_shutdown():
    time.sleep(1)
    os.kill(os.getpid(), signal.SIGINT)

@app.route('/kapat')
def shutdown():
    threading.Thread(target=delayed_shutdown).start()
    return "Sunucu kapatılıyor..."

@app.errorhandler(404)
def page_not_found(e):
    return render_template_string('<body style="background:#181818;color:#f1f1f1;text-align:center;"><h1>404</h1><p><a href="/">Ana Sayfa</a></p></body>'), 404

if __name__ == "__main__":
    load_config()
    app.run(host="0.0.0.0", port=5000)
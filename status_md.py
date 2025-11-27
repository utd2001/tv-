import re
import requests
import json
import os
import html
import urllib3
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import datetime
import concurrent.futures
import time

# SSL Warning Disable
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_FILE = "config.json"
TV_M3U8_FILE = "tv.m3u8"

def log(message):
    print(f"[Log] {message}")

def sanitize_filename(filename):
    replacements = {'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u', 'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'}
    for tr, en in replacements.items():
        filename = filename.replace(tr, en)
    filename = re.sub(r'\s+', '_', filename)
    filename = re.sub(r'[^A-Za-z0-9_.-]', '', filename)
    return filename

def clean_link(link):
    decoded_link = html.unescape(link)
    stripped_link = decoded_link.strip().rstrip("'\",)")
    return stripped_link

def scrape_m3u8_from_website(url):
    try:
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
        return list(found_links)[0] if found_links else None
    except Exception:
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
        except Exception:
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
    except Exception:
        return None

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

def load_channels():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                channels_raw = data.get("channels", [])
                migrated = []
                for ch in channels_raw:
                    if isinstance(ch, list):
                        migrated.append({"name": ch[0] if len(ch)>0 else "", "url": ch[1] if len(ch)>1 else "", "auto": ch[2] if len(ch)>2 else False})
                    elif isinstance(ch, dict):
                        migrated.append({"name": ch.get("name", ""), "url": ch.get("url", ""), "auto": ch.get("auto", False)})
                return migrated
        except Exception as e:
            print(f"Config Error: {e}")
            return []
    return []

def get_github_url(channel_name):
    filename = f"{sanitize_filename(channel_name).upper()}.m3u8"
    if os.path.exists(TV_M3U8_FILE):
        try:
            with open(TV_M3U8_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if filename in line and line.strip().startswith("http"):
                        return line.strip()
        except:
            pass
    return None

def check_single_channel(channel):
    name = channel.get('name')
    
    # 1. Source Check
    source_status = "outage"
    try:
        m3u8, _ = resolve_channel_url(channel)
        if m3u8:
            source_status = "operational"
    except:
        pass

    # 2. GitHub Check
    github_status = "outage"
    github_url = get_github_url(name)
    
    # Check local file existence first (to avoid false "YÜKLE" status before push)
    local_filename = f"{sanitize_filename(name).upper()}.m3u8"
    local_filepath = os.path.join("m3u8", local_filename)
    is_local_present = os.path.exists(local_filepath)

    if github_url:
        try:
            r = requests.get(f"{github_url}?t={int(time.time())}", headers={'user-agent': 'Mozilla/5.0'}, timeout=5)
            if r.status_code == 200:
                github_status = "operational"
            elif is_local_present:
                 # If not on GitHub but exists locally, assume it will be pushed soon
                 github_status = "operational"
        except:
            if is_local_present:
                github_status = "operational"
    elif is_local_present:
        # If no GitHub URL yet but file exists locally
        github_status = "operational"
    
    # 3. Stream Check
    stream_status = "outage"
    stream_error = ""
    if github_url:
        try:
            r = requests.get(f"{github_url}?t={int(time.time())}", headers={'user-agent': 'Mozilla/5.0'}, timeout=5)
            if r.status_code == 200:
                stream_url = None
                for line in r.text.splitlines():
                    if line.strip() and not line.strip().startswith('#') and line.strip().startswith('http'):
                        stream_url = line.strip()
                        break
                
                if stream_url:
                    try:
                        r_stream = requests.get(stream_url, headers={'user-agent': 'Mozilla/5.0'}, stream=True, timeout=5, verify=False)
                        if r_stream.status_code < 400:
                            stream_status = "operational"
                        else:
                            stream_error = str(r_stream.status_code)
                    except:
                        stream_error = "Timeout"
                else:
                    stream_error = "Empty"
        except Exception as e:
            stream_error = str(e)

    return {
        "name": name,
        "source": source_status,
        "github": github_status,
        "stream": stream_status,
        "stream_error": stream_error
    }

def determine_action(status):
    isSrcOK = status['source'] == 'operational'
    isGitOK = status['github'] == 'operational'
    isStrmOK = status['stream'] == 'operational'
    error = status['stream_error']
    
    is403 = '403' in error
    is404 = '404' in error

    if isSrcOK and isGitOK and isStrmOK:
        return {'action': 'OYNAT', 'reason': 'Yayın Aktif', 'emoji': '🟢'}
    elif isSrcOK and isGitOK and not isStrmOK:
        if is403:
            return {'action': 'YENİLE', 'reason': 'Token Bitti', 'emoji': '🟣'}
        elif is404:
            return {'action': 'ID BUL', 'reason': 'Video Silindi', 'emoji': '🔴'}
        else:
            return {'action': 'YENİLE', 'reason': 'Yayın Hatası', 'emoji': '🟣'}
    elif isSrcOK and not isGitOK:
        return {'action': 'YÜKLE', 'reason': 'Dosya Yok', 'emoji': '🟠'}
    elif not isSrcOK and isGitOK and not isStrmOK:
        return {'action': 'BEKLE', 'reason': 'Kanal Kapalı', 'emoji': '🔴'}
    elif not isSrcOK and isGitOK and isStrmOK:
        return {'action': 'İZLE', 'reason': 'Kaynak Koptu', 'emoji': '🟢'}
    else:
        return {'action': 'DÜZELT', 'reason': 'Kaynak Yok', 'emoji': '⚪'}

def generate_markdown():
    """README.md için HTML tablo oluşturur (tüm kanallar)."""
    channels = load_channels()
    results = []
    
    print(f"Checking {len(channels)} channels...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_channel = {executor.submit(check_single_channel, ch): ch for ch in channels}
        for future in concurrent.futures.as_completed(future_to_channel):
            results.append(future.result())
    
    # Preserve original list order from config.json
    results_dict = {r['name']: r for r in results}
    results = [results_dict[ch['name']] for ch in channels if ch['name'] in results_dict]

    md_output = "# Kanal Durum Raporu\n\n"
    
    # HTML Table
    md_output += "<table>\n"
    md_output += "  <thead>\n"
    md_output += "    <tr>\n"
    md_output += "      <th>#</th>\n"
    md_output += "      <th>Kanal</th>\n"
    md_output += "      <th>Kaynak</th>\n"
    md_output += "      <th>GitHub</th>\n"
    md_output += "      <th>Yayın</th>\n"
    md_output += "      <th>Durum</th>\n"
    md_output += "      <th>Eylem</th>\n"
    md_output += "      <th>Sebep</th>\n"
    md_output += "    </tr>\n"
    md_output += "  </thead>\n"
    md_output += "  <tbody>\n"
    
    for i, res in enumerate(results):
        # 3-state icons
        src_icon = "🟢" if res['source'] == 'operational' else "🔴"
        git_icon = "🟢" if res['github'] == 'operational' else "🔴"
        strm_icon = "🟢" if res['stream'] == 'operational' else "🔴"
        
        # Action data
        action_data = determine_action(res)
        
        md_output += "    <tr>\n"
        md_output += f"      <td>{i+1}</td>\n"
        md_output += f"      <td>{res['name']}</td>\n"
        md_output += f"      <td align='center'>{src_icon}</td>\n"
        md_output += f"      <td align='center'>{git_icon}</td>\n"
        md_output += f"      <td align='center'>{strm_icon}</td>\n"
        md_output += f"      <td align='center'>{action_data['emoji']}</td>\n"
        md_output += f"      <td><strong>{action_data['action']}</strong></td>\n"
        md_output += f"      <td>{action_data['reason']}</td>\n"
        md_output += "    </tr>\n"

    # Merged bottom cell
    timestamp = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    md_output += "    <tr>\n"
    md_output += f"      <td colspan='8' align='center'>Son Güncelleme: {timestamp}</td>\n"
    md_output += "    </tr>\n"

    md_output += "  </tbody>\n"
    md_output += "</table>\n"

    return md_output

def generate_errors_markdown():
    """Sadece hatalı kanalları içeren, yerelden okunabilir Markdown dosyası oluşturur."""
    channels = load_channels()
    results = []
    
    print(f"Checking {len(channels)} channels for errors...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_channel = {executor.submit(check_single_channel, ch): ch for ch in channels}
        for future in concurrent.futures.as_completed(future_to_channel):
            results.append(future.result())
    
    # Preserve original list order from config.json
    results_dict = {r['name']: r for r in results}
    results = [results_dict[ch['name']] for ch in channels if ch['name'] in results_dict]
    
    # Filter only error channels (status emoji is not 🟢)
    error_results = []
    for res in results:
        action_data = determine_action(res)
        if action_data['emoji'] != '🟢':
            error_results.append((res, action_data))
    
    # Generate readable Markdown
    timestamp = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    md_output = f"# Hatalı Kanallar\n\n"
    md_output += f"**Son Güncelleme:** {timestamp}\n\n"
    
    if not error_results:
        md_output += "✅ Tüm kanallar çalışıyor!\n"
        return md_output
    
    md_output += f"**Toplam Hatalı Kanal:** {len(error_results)}\n\n"
    md_output += "---\n\n"
    
    for i, (res, action_data) in enumerate(error_results, 1):
        src_icon = "🟢" if res['source'] == 'operational' else "🔴"
        git_icon = "🟢" if res['github'] == 'operational' else "🔴"
        strm_icon = "🟢" if res['stream'] == 'operational' else "🔴"
        
        md_output += f"## {i}. {res['name']}\n\n"
        md_output += f"- **Durum:** {action_data['emoji']} {action_data['reason']}\n"
        md_output += f"- **Eylem:** {action_data['action']}\n"
        md_output += f"- **Kaynak:** {src_icon}\n"
        md_output += f"- **GitHub:** {git_icon}\n"
        md_output += f"- **Yayın:** {strm_icon}\n"
        if res['stream_error']:
            md_output += f"- **Hata Detayı:** {res['stream_error']}\n"
        md_output += "\n"
    
    return md_output

def update_readme_status(md_content):
    """README.md dosyasındaki STATUS_TABLE_START ve STATUS_TABLE_END arasını günceller."""
    readme_path = "README.md"
    
    if not os.path.exists(readme_path):
        print("README.md bulunamadı.")
        return False
    
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # STATUS_TABLE_START ve STATUS_TABLE_END arasındaki içeriği bul ve değiştir
        start_marker = "<!-- STATUS_TABLE_START -->"
        end_marker = "<!-- STATUS_TABLE_END -->"
        
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)
        
        if start_idx == -1 or end_idx == -1:
            print("README.md'de STATUS_TABLE markerları bulunamadı.")
            return False
        
        # Yeni içeriği oluştur (markerlar dahil)
        new_content = (
            content[:start_idx] +
            start_marker + "\n" +
            md_content +
            "\n" + end_marker +
            content[end_idx + len(end_marker):]
        )
        
        # README.md'yi güncelle
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        print("README.md başarıyla güncellendi.")
        return True
        
    except Exception as e:
        print(f"README.md güncellenirken hata: {e}")
        return False

if __name__ == "__main__":
    # README.md için HTML tablo oluştur
    md = generate_markdown()
    update_readme_status(md)
    
    # ERRORS.md için sadece hatalı kanalları içeren Markdown oluştur
    errors_md = generate_errors_markdown()
    with open("ERRORS.md", "w", encoding="utf-8") as f:
        f.write(errors_md)
    print("ERRORS.md oluşturuldu.")

# fox.py
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

START_URL = "https://www.nowtv.com.tr/canli-yayin"
BASE_URL = "https://nowtv-live-ad.ercdn.net/nowtv/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# playlist.m3u8 URL'sini yakalamak için regex
PATTERN = re.compile(
    r"https?://nowtv-live-ad\.ercdn\.net/nowtv/playlist\.m3u8\?[^'\"<>\s]*\bst=[^&\s'\"<>]+[^'\"<>\s]*\&e=\d+[^'\"<>\s]*",
    flags=re.IGNORECASE
)

def get_fox_m3u8_playlist(only_highest=True):
    """
    FOX (NOWTV) canlı yayını için playlist oluşturur.
    
    Parametreler:
        only_highest=True  → sadece en yüksek çözünürlük
        only_highest=False → tüm çözünürlükler
    """
    try:
        r = requests.get(START_URL, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except requests.RequestException:
        return None

    # playlist.m3u8 URL'sini bul
    match = PATTERN.search(r.text)
    if not match:
        # Harici scriptlerde ara
        soup = BeautifulSoup(r.text, "html.parser")
        for s in soup.find_all("script", src=True):
            try:
                js_url = urljoin(START_URL, s["src"])
                js_r = requests.get(js_url, headers=HEADERS, timeout=10)
                if js_r.ok:
                    m = PATTERN.search(js_r.text)
                    if m:
                        match = m
                        break
            except requests.RequestException:
                continue

    if not match:
        return None

    playlist_url = match.group(0)

    # playlist.m3u8 dosyasını indir
    try:
        r = requests.get(playlist_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        lines = r.text.splitlines()
    except requests.RequestException:
        return None

    # Başlangıç satırlarını ve streamleri ayır
    header_lines = []
    streams = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXT-X-STREAM-INF'):
            # çözünürlük bilgisi
            res_match = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
            if res_match and i + 1 < len(lines):
                width = int(res_match.group(1))
                height = int(res_match.group(2))
                url_line = lines[i + 1].strip()
                if not url_line.startswith("http"):
                    url_line = urljoin(BASE_URL, url_line)
                streams.append((width*height, line, url_line))
            i += 2
        else:
            if line != '':
                header_lines.append(line)
            i += 1

    if not streams:
        return None

    if only_highest:
        # Sadece en yüksek çözünürlük
        highest_stream = max(streams, key=lambda x: x[0])
        new_playlist = header_lines + [highest_stream[1], highest_stream[2]]
    else:
        # Tüm çözünürlükler
        new_playlist = header_lines
        for s in streams:
            new_playlist.extend([s[1], s[2]])

    return "\n".join(new_playlist)


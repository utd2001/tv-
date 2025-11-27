import os
import glob
# Eski .m3u8 dosyalarını temizle
for old_file in glob.glob("*.m3u8"):
    try:
        os.remove(old_file)
        print(f"🗑️ Silindi: {old_file}")
    except Exception as e:
        print(f"❌ Silme hatası ({old_file}): {e}")

# Silinen dosyaları GitHub'a push et
import subprocess
try:
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "Eski m3u8 dosyaları silindi"], check=True)
    subprocess.run(["git", "push"], check=True)
    print("🚀 Silinen dosyalar GitHub'a push edildi.")
except subprocess.CalledProcessError as e:
    print(f"❌ GitHub push hatası (silme): {e}")
import json
import requests
import urllib.parse as urlparse
import subprocess

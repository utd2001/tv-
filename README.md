
<!-- STATUS_TABLE_START -->
# Kanal Durum Raporu

<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Kanal</th>
      <th>Kaynak</th>
      <th>GitHub</th>
      <th>Yayın</th>
      <th>Durum</th>
      <th>Eylem</th>
      <th>Sebep</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>HALK TV</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td><strong>OYNAT</strong></td>
      <td>Yayın Aktif</td>
    </tr>
    <tr>
      <td>2</td>
      <td>TELE2 HABER</td>
      <td align='center'>🔴</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td><strong>İZLE</strong></td>
      <td>Kaynak Koptu</td>
    </tr>
    <tr>
      <td>3</td>
      <td>BİRGÜN TV</td>
      <td align='center'>🔴</td>
      <td align='center'>🟢</td>
      <td align='center'>🔴</td>
      <td align='center'>🔴</td>
      <td><strong>BEKLE</strong></td>
      <td>Kanal Kapalı</td>
    </tr>
    <tr>
      <td>4</td>
      <td>SÖZCÜ TV</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td><strong>OYNAT</strong></td>
      <td>Yayın Aktif</td>
    </tr>
    <tr>
      <td>5</td>
      <td>MAVİ KARADENİZ TV</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td><strong>OYNAT</strong></td>
      <td>Yayın Aktif</td>
    </tr>
    <tr>
      <td>6</td>
      <td>FOX TV</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td><strong>OYNAT</strong></td>
      <td>Yayın Aktif</td>
    </tr>
    <tr>
      <td>7</td>
      <td>TV8</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td><strong>OYNAT</strong></td>
      <td>Yayın Aktif</td>
    </tr>
    <tr>
      <td>8</td>
      <td>TV8.5</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td><strong>OYNAT</strong></td>
      <td>Yayın Aktif</td>
    </tr>
    <tr>
      <td>9</td>
      <td>KANAL D</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td><strong>OYNAT</strong></td>
      <td>Yayın Aktif</td>
    </tr>
    <tr>
      <td>10</td>
      <td>TEVE2</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td align='center'>🟢</td>
      <td><strong>OYNAT</strong></td>
      <td>Yayın Aktif</td>
    </tr>
    <tr>
      <td colspan='8' align='center'>Son Güncelleme: 27.11.2025 23:19:22</td>
    </tr>
  </tbody>
</table>

<!-- STATUS_TABLE_END -->

# IPTV Yayın Yöneticisi ve Proxy Sunucusu

Bu proje, dağınık IPTV kaynaklarını, YouTube canlı yayınlarını ve m3u8 akışlarını tek bir merkezi sunucu üzerinden yönetmek, izlemek ve otomatik olarak iyileştirmek için geliştirilmiş gelişmiş bir ara katman yazılımıdır.

## 🌟 Temel Özellikler

### 1. Akıllı Yayın Motoru
*   **Otomatik Çözünürlük Seçimi:** `ONLY_HIGHEST` modu aktifken, master playlist içerisindeki en yüksek çözünürlüklü akışı otomatik olarak seçer ve sunar. Bu sayede bant genişliği optimizasyonu sağlanır ve oynatıcı uyumsuzlukları önlenir.
*   **M3U8 Proxy ve Yeniden Yazma:** Kaynak m3u8 dosyalarını anlık olarak analiz eder. İçerisindeki parçalı (chunk) URL'lerini mutlak (absolute) yollara çevirerek, yerel ağdaki tüm oynatıcıların sorunsuz çalışmasını sağlar.
*   **Dinamik Akış Yönetimi:** İstemciye her zaman çalışan, güncel bir yayın linki sunmak için arkaplanda kaynakları yönetir.

### 2. Gelişmiş YouTube Entegrasyonu
*   **Canlı Yayın Yakalayıcı:** YouTube kanal ID'si (`UC...`) veya kullanıcı adı (`@kanal`) girildiğinde, o kanalın o anki canlı yayınının ham `.m3u8` linkini (HLS Manifest) otomatik olarak bulur ve çeker.
*   **YouTubei API Kullanımı:** Resmi olmayan YouTube dahili API'lerini (InnerTube) ve özel header manipülasyonlarını kullanarak, standart web sayfalarından daha hızlı, güvenilir ve engellere takılmayan sonuçlar üretir.
*   **Kanal ve Video Arama:** Editör arayüzü üzerinden doğrudan YouTube üzerinde "canlı yayın" veya "kanal" araması yapabilir; bulunan ID'leri tek tıkla sisteme entegre edebilirsiniz.

### 3. Akıllı Sağlık Kontrolü ve Otomasyon
*   **3 Katmanlı Analiz Sistemi:** Her kanal için üç aşamalı derinlemesine kontrol yapar:
    1.  **Kaynak Kontrolü:** Konfigürasyondaki URL geçerli ve erişilebilir mi?
    2.  **Liste Kontrolü:** Kanal, uzak sunucudaki (GitHub vb.) ana yayın listesinde mevcut mu?
    3.  **Yayın Kontrolü:** Akışın kendisi (Stream URL) HTTP 200 OK yanıtı veriyor mu?
*   **Gelişmiş Hata Sınıflandırma:** Basit bir "hata" mesajı yerine, sorunun kök nedenini analiz eder ve raporlar:
    *   `403 Forbidden`: Token süresi dolmuş (Yenileme gerekir).
    *   `404 Not Found`: Video silinmiş, yayın bitmiş veya ID değişmiş.
    *   `Timeout`: Kaynak sunucu yanıt vermiyor veya aşırı yavaş.
*   **Otomatik İyileştirme:** Arayüzde "YENİLE" veya "YÜKLE" durumu tespit edildiğinde (özellikle 403 hatalarında), sistem otomatik olarak onarım betiğini (`github.pyw`) tetikleyerek tokenleri yenilemeyi dener.

### 4. Kullanıcı Arayüzü ve Deneyim
*   **İki Farklı Görünüm Modu:**
    *   **Detaylı Mod:** Teknik analiz için her kontrol katmanını (Kaynak, GitHub, Yayın) ayrı ayrı durum ışıklarıyla gösterir.
    *   **Eylem Odaklı Mod:** Karmaşık teknik detayları gizleyerek, kullanıcıya o an yapması gerekeni söyler (Örn: "OYNAT", "YENİLE", "ID BUL", "BEKLE").
*   **Web Tabanlı Yönetim Paneli:** `config.json` dosyasını elle düzenlemeye gerek kalmadan, modern ve responsive bir web arayüzü (`/editor`) ile kanal ekleme, silme, sıralama ve düzenleme imkanı sunar.
*   **Modern Tasarım:** Göz yormayan, profesyonel koyu tema, renk kodlu durum bildirimleri ve animasyonlu geçişler.
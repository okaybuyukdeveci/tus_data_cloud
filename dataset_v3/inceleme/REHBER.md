# TUS SFT v3 — elle inceleme rehberi

Amaç: model eğitimi için **kusursuz** bir soru-cevap seti. Her kayıt tek tek okunur ve
**ok / duzelt / at** kararı verilir. Kayıtlar otomatik temizlikten geçmiş halde gösterilir
(LaTeX/HTML temizlendi, şıklar ayrıştırıldı, açıklamaya karışan sonraki soru kesildi,
OCR çöpü cümleler atıldı). Gördüğün hal = eğitime girecek hal (karar vermezsen).

## Araç

```
cd ~/tusdata-mineru
export KARAR_DOSYA=kararlar_ajanN.jsonl          # N = sana verilen numara
.venv/bin/python dataset_build/incele.py goster dataset_v3/inceleme/parcalar/parca_N.txt 25
.venv/bin/python dataset_build/incele.py ok <id> <id> ...
.venv/bin/python dataset_build/incele.py karar '<json>' ['<json>' ...]
.venv/bin/python dataset_build/incele.py durum dataset_v3/inceleme/parcalar/parca_N.txt
```
`goster` yalnızca henüz karar verilmemiş kayıtları gösterir; karar yazdıkça ilerlersin.
Çok uzun JSON'u tek tırnak içinde vermek zorsa bir dosyaya yazıp
`.venv/bin/python dataset_build/incele.py karar "$(cat /tmp/k.json)"` kullan (liste de olur).
**Kaynak dosyalara, v2 datasetine, başka ajanların karar dosyalarına dokunma.**

## Kararlar

### ok — sorun yok
Soru anlaşılır ve eksiksiz, 4–5 şık düzgün, cevap doğru, açıklama cevabı destekliyor ve
okunaklı. Küçük yazım hataları (tek tük harf) ok'u engellemez.

### duzelt — onarılabilir sorun
Alanlar (yalnızca değişeni ver):
- `"govde"`: soru gövdesinin düzeltilmiş hali (OCR hatası, eksik Roma rakamı, yapışık kelime...).
  Anlamı değiştirme, bilgi ekleme.
- `"siklar"`: `{"A":"...","B":"...",...}` — şıkları yeniden ver (bölünmüş/yapışık/eksik harfli şık).
  **siklar verirsen `"cevap"` ZORUNLU** (yeni harflere göre).
  Şık metni kaynakta tamamen yoksa uydurma. Kalan şıkları A'dan sırayla harfle ve cevabı
  eşle — yalnızca kaybolan şık doğru cevap DEĞİLSE; doğru cevapsa `at` (sik_kayip).
- `"cevap"`: **kitabın açıklaması kendi cevap harfiyle çelişiyorsa** düzelt. Ölçüt harflerin
  komşu olması DEĞİL; ölçüt şu iki şartın birlikte sağlanması:
  1. Açıklama metni açıkça başka bir şıkkı anlatıyor, ve
  2. Tıbben de o şık doğru.
  Bu durumda bozuk olan cevap satırıdır, içerik sağlamdır → `duzelt` + `cevap`.
  (Örnek: açıklama "antimetabolit olmayan doksorubisindir" diyor ama anahtar B'yi gösteriyor;
  doksorubisin E şıkkı → `cevap: "E"`. B ile E komşu olmaması önemli değil.)

  Yalnızca **kendi tıbbi görüşün** kitaptan farklıysa — açıklama anahtarı destekliyor ama sen
  katılmıyorsan — düzeltme; `at` (cevap_supheli).
- `"aciklama_kes"`: açıklamada bu metnin başladığı yerden sonrasını at (metin açıklamada birebir
  geçmeli; genelde bir paragrafın ilk 30–60 karakteri). Konu anlatımı taşması, başka sorunun
  açıklaması, "SPOT BİLGİLER" gibi alakasız bölümler için.
- `"aciklama_paragraf"`: paragraf seçimi (gösterimdeki `[k]` numaralarına göre).
  - Sayı: `3` → ilk 3 paragrafı tut (`[0] [1] [2]`).
  - Aralık: `"2-"` → `[2]` ve sonrasını tut (**baştaki OCR çöpünü atmak için**).
  - Aralık: `"1-4"` → yalnızca `[1]`..`[4]` arasını tut (baştan ve sondan kırpma).
- `"aciklama"`: açıklamayı TAMAMEN yeniden yaz (2-6 cümle). Üç durumda kullan:
  1. Açıklama boş, okunmaz ya da OCR çöpü.
  2. Açıklama alakasız (başka sorunun metni).
  3. **Açıklama okunaklı ama sorunun cevabını gerekçelendirmiyor** — kitaptan kopyalanmış
     bir konu bloğu olup "doğru şık neden bu" sorusuna değmiyorsa yeniden yaz.

  > **Önce kaynak, sonra bilgin.** Yeniden yazarken kaynaktaki (soru + orijinal açıklama +
  > kesilen blok) bilgiyi kullan. Kaynak doğru şıkkı gerekçelendirmeye **yetmiyorsa** —
  > örneğin açıklama yalnızca "SIRS kriterleri bilinmelidir" diyorsa — eksik halkayı kendi
  > tıbbi bilginle tamamlayabilirsin. Koşul şu:
  >
  > - Eklediğin her şey **doğru şıkkı gerekçelendirmeye hizmet etsin.** Konuyu genişleten
  >   ek oran, tarih, sınıflama ya da yan liste ekleme — soru bunu sormuyor.
  > - Kaynakta bir bilgi **varsa** onu kullan; kendi versiyonunla değiştirme.
  > - Emin olmadığın bir bilgiyi yazma; o kaydı `at` (`eksik_bilgi`) etmek daha iyidir.
  >
  > Bu bir yasak değil, bir öncelik sırası: kaynak → gerekli tamamlama → fazlası yok.
  **Düzgün Türkçe, Türkçe karakterlerle (ş ğ ı ö ü ç İ)**, 2–6 cümle, cevabın neden doğru
  olduğunu ve önemli çeldiricileri açıklayan, kesin tıbbi bilgi. Uydurma kaynak/oran yazma.
- `"not"`: kısa açıklama (ne yaptın).

Örnek:
```
{"id":"abc","karar":"duzelt","siklar":{"A":"Kolostomi açılması","B":"Rezeksiyon","C":"Barsak istirahati ve antibiyotik","D":"Açık karın ameliyatı","E":"Kolonoskopik dekompresyon"},"cevap":"C","not":"B-C harfleri kayıptı"}
{"id":"def","karar":"duzelt","aciklama_kes":"SPOT BİLGİLER","not":"konu anlatımı taşması kesildi"}
```

### at — eğitimden çıkar
`"neden"` şunlardan biri: `soru_bozuk` (gövde okunmaz/eksik, anlam kurulamıyor),
`gorsel_gerekli` (görsel olmadan çözülemez), `cevap_supheli` (anahtar tıbben yanlış ya da
iki şık doğru), `eksik_bilgi` (soruyu çözmek için gerekli veri eksik: tablo, öncül listesi...),
`sik_kayip` (doğru şıkkın metni kayıp), `baglam_gerekli` (önceki soruya/olguya bağlı),
`tekrar` (aynı sorunun bariz kopyası — yalnızca aynı parçada gördüysen), `diger`.
`"not"` ile kısa gerekçe yaz.

## Kontrol listesi (her kayıt)
1. **Gövde** tam ve anlaşılır mı? Öncül listesi (I, II, III...) varsa numaralar yerinde mi?
   Soru önceki bir soruya/olguya atıf yapıyor mu ("bir önceki sorudaki hasta") → at baglam_gerekli.
2. **Şıklar** 5 (ya da doğal 4) tane, her biri tek bir seçenek mi? İki şık birbirine yapışmış,
   bir şıkkın metni gövdeye kaçmış, harf metnin başında kalmış ("DÇiğneme") → duzelt.
   `SIK_SAYISI=4` görürsen: soru gerçekten 4 şıklı mı, yoksa bir şık başka şıkka mı yapışmış bak.
3. **Cevap** tıbben doğru mu? Sen de soruyu çöz. Emin olmadığın tartışmalı konularda kitaba
   güven; açıkça yanlışsa at cevap_supheli. `CEVAP: E -> D` gösterimi otomatik yeniden
   harflendirme demektir — yeni harfin gerçekten doğru şıkkı gösterdiğini kontrol et.
4. **Açıklama** bu soruya mı ait ve cevabı destekliyor mu? Sonunda başka sorunun metni,
   konu anlatımı sayfaları, "Doğru cevap: X" satırı, anlamsız OCR parçaları varsa kes/düzelt.
   Açıklama çoğunlukla okunmaz/alakasız ise yeniden yaz (`aciklama`). Uzun ama tamamen ilgili
   açıklamalar (tablolar dahil) kalabilir.
   Açıklamada soruyla ilgisiz sınav yorumu ("kolay bir soru", "çeldirici sevmiyoruz") tek başına
   sorun değil.
5. **SORUDA_GORSEL**: satırdaki dosya yolunu Read aracıyla aç. Görsel tablo/şema ve soruyu
   çözmek için gerekliyse (metinde karşılığı yoksa) → at gorsel_gerekli. Görselin bilgisi
   metinde zaten varsa ya da süs/logo ise → normal değerlendir.
6. **ELLE_ONARILMIS** kayıtlar daha önce elle yazıldı; açıklamanın Türkçe karakterlerle düzgün
   olduğunu ve cevabı desteklediğini kontrol et, genelde ok.

## Tempo
Parçanın tamamını bitir. Her `goster` çıktısındaki kayıtların HEPSİ için karar yaz, sonra
bir sonrakini göster. Temiz kayıtları toplu `ok` ile geç. İş bitince `durum` ile
`N/N` gördüğünü doğrula ve kısa bir özet ver: kaç ok / duzelt / at, en sık sorun türleri,
emin olamadığın kayıt id'leri.

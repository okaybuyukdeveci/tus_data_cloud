# TUS veri seti kontrolü — cloud oturumu talimatı

> **Claude'a ne diyeceksin:**
> *"BASLA_BURADAN.md'yi oku ve PARÇA 03 üzerinde çalış."* (numarayı sen seç)
>
> Her cloud oturumu **tek bir parça** üzerinde çalışır. Parçalar çakışmaz;
> iki oturum asla aynı kaydı görmez.

---

## 1. Ne yapıyoruz?

Türkçe TUS (Tıpta Uzmanlık Sınavı) soru bankalarından, bir dil modelini eğitmek için
**soru + şıklar + doğru cevap + açıklama** veri seti çıkardık. Kaynak 278 PDF'ti; OCR ile
metne çevrildi, sorular otomatik ayrıştırıldı. Otomatik çıkarımda kaçınılmaz bozulmalar oldu:
şık harfleri kayboldu, açıklamaların arkasına başka soruların metni karıştı, bazı açıklamalar
OCR çöpüne dönüştü.

Otomatik bir temizlik hattı bunların büyük kısmını onardı. **Kalan iş: kayıtları tek tek okuyup
karar vermek** — sorun yok mu, düzeltilmeli mi, yoksa eğitime hiç girmemeli mi?

24.945 kaydın **7.753'ü** karara bağlandı. Kalan **17.192 kayıt 8 parçaya** bölündü
(`paylar/parca_01.txt` … `parca_08.txt`), her biri 2.149 kayıt.

Bölme sıralı değil, **dönüşümlü** yapıldı: liste risk sırasına dizildi, sonra kayıtlar parçalara
tek tek dağıtıldı. Yani her parçada aynı zorluk karışımı var — hiçbir parça "kolay" ya da "zor"
değil, yarım kalan bir parça da dengeyi bozmaz.

---

## 2. Kurulum

**Hiçbir şey kurmana gerek yok.** Salt Python 3.10+ standart kütüphanesi kullanılıyor;
üçüncü parti paket yok, internet gerekmiyor. Tüm komutlar depo kökünden çalıştırılır.

```bash
python3 dataset_build/v3_uret.py     # veriyi üretir — İLK KOMUT BU OLMALI
```

Bu komut `dataset_v2`'yi temizlik hattından geçirip `dataset_v3/sft/` altına çıkarır ve
şimdiye kadarki tüm kararları uygular. Çıktılar depoda tutulmaz, her oturumda yeniden üretilir.

---

## 3. Çalışma döngüsü

Aşağıda **parça 03** örneklendi — kendi parça numaranı yaz. Karar dosyan parçanla aynı
numarayı taşımalı (`kararlar_p03.jsonl`), başka bir oturumun dosyasına asla yazma.

```bash
export KARAR_DOSYA=kararlar_p03.jsonl
export PAY=paylar/parca_03.txt

# 1) Sıradaki 20 kaydı göster
python3 dataset_build/incele.py goster $PAY 20 --kisa

# 2) Sorunsuz olanları toplu geç
python3 dataset_build/incele.py ok <id> <id> <id>

# 3) Düzeltme/eleme kararlarını JSON ile ver
cat > /tmp/karar.json <<'EOF'
[
  {"id":"abc123","karar":"duzelt","siklar":{"A":"...","B":"...","C":"...","D":"...","E":"..."},"cevap":"C","not":"B-C harfleri kayıptı"},
  {"id":"def456","karar":"at","neden":"cevap_supheli","not":"iki şık da doğru"}
]
EOF
python3 dataset_build/incele.py karar "$(cat /tmp/karar.json)"

# 4) İlerlemeyi gör
python3 dataset_build/incele.py durum $PAY
```

`goster` yalnızca **henüz karar verilmemiş** kayıtları gösterir; nerede kalırsan kal, bir sonraki
oturum oradan devam eder. Kararlar dosyaya eklenir, hiçbir şeyin üzerine yazılmaz.

**JSON'u heredoc ile dosyaya yaz**, komut satırına gömme: metinlerde kesme işareti (`'`) çok
geçiyor ve shell'i bozuyor.

### Üç kural — önceki turlarda bunlar yüzünden sorun çıktı
1. **Gösterilen her kayıt için karar yazmadan bir sonraki partiyi açma.** Önce yaz, sonra devam et.
2. **Bir kayıtta takılırsan bırak, ilerle.** Emin olamadığın kaydı atlayıp sonunda raporla;
   tek kayıt için oturumu tıkama.
3. **Her `duzelt` kararına `not` yaz.** Tek cümle yeter ("B-C harfleri kayıptı", "açıklamaya
   sonraki soru karışmıştı"). Notsuz düzeltme sonradan denetlenemiyor — bir turda 606 düzeltmenin
   508'i notsuz geldi, bu tekrarlanmamalı.

---

## 4. Karar kuralları

Ayrıntılı kurallar: **`dataset_v3/inceleme/REHBER.md`** — bunu da oku. Özet:

### `ok` — sorun yok
Soru anlaşılır ve eksiksiz, 4–5 şık düzgün, cevap doğru, açıklama cevabı destekliyor ve okunaklı.
Tek tük harf hatası `ok` vermeni engellemez.

### `duzelt` — onarılabilir sorun
Yalnızca değiştirdiğin alanı yaz:

| Alan | Ne işe yarar |
|---|---|
| `govde` | Soru gövdesinin düzeltilmiş hali (OCR hatası, kayıp Roma rakamı…) |
| `siklar` | `{"A":"...","B":"...",...}` — şıkları yeniden yaz. **`cevap` zorunlu olur** |
| `cevap` | Yalnızca bariz harf kaymasında (`"C"` gibi) |
| `aciklama_paragraf` | Paragraf seçimi (gösterimdeki `[0] [1] [2]`): `3` = ilk 3 paragraf · `"2-"` = `[2]` ve sonrası (**baştaki çöpü atar**) · `"1-4"` = yalnızca o aralık |
| `aciklama_kes` | Verdiğin metnin başladığı yerden sonrasını at |
| `aciklama` | Açıklamayı tamamen yeniden yaz (2–6 cümle) |
| `not` | Ne yaptığının kısa özeti |

### `at` — eğitimden çıkar
`neden` şunlardan biri olmalı: `soru_bozuk`, `gorsel_gerekli`, `cevap_supheli`, `eksik_bilgi`,
`sik_kayip`, `baglam_gerekli`, `tekrar`, `diger`. `not` ile kısa gerekçe yaz.

### Altın kurallar
1. **Uydurma yok.** Kaynakta olmayan şık metni ya da bilgi ekleme. Doğru şıkkın metni kayıpsa
   `at` (`sik_kayip`). **Görseldeki bulguyu soru gövdesine yazma** — bu, soruyu sahte biçimde
   çözülebilir hale getirir; görsel şartsa `at` (`gorsel_gerekli`).
2. **Açıklamalar düzgün Türkçe olmalı** — ş, ğ, ı, ö, ü, ç, İ karakterleriyle. ASCII Türkçe
   (`degildir`, `icin`) yazma; model bunu öğrenir.
3. **Cevap anahtarına saygı.** Kitabın cevabı tıbben açıkça yanlışsa ya da iki şık doğruysa
   kaydı `at` (`cevap_supheli`). Kendi görüşünle anahtarı değiştirme; tek istisna bariz harf
   kayması (açıklama açıkça başka şıkkı anlatıyor ve tıbben de o doğru).
4. **Okumadan `ok` verme.** Soruyu kendin de çöz; cevabın tıbben doğru olduğunu ve açıklamanın
   onu desteklediğini denetle.

### Dokunma
`dataset_v2/`, `dataset_build/*.py`, başka oturumların karar dosyaları. Tüm düzeltmeler yalnızca
kendi `kararlar_pNN.jsonl` dosyanda birikir; veri dosyası hiçbir zaman elle düzenlenmez.

---

## 5. En sık karşılaşacağın 6 durum

1. **Yapışık/kaymış şıklar (en yaygın).** Bir şıkkın harfi kaybolmuş, metni bir öncekine
   yapışmış. Araç kalan şıkları yeniden harflemiş olabilir (`yeniden_harflendi`, `eksik:C`,
   `SIK_SAYISI=4` uyarılarını görürsün). Beş şıkkı doğru biçimde yeniden yaz ve cevabı yeni
   harfe göre ver.
2. **Boş ya da okunmaz açıklama.** `[aciklama 0 kr]` görürsün ya da açıklama OCR çöpüdür.
   2–6 cümlelik, doğru, Türkçe karakterli yeni bir açıklama yaz.
3. **Açıklamaya taşan metin.** Sonuna konu anlatımı sayfaları, "SPOT BİLGİLER" listeleri ya da
   bir sonraki sorunun metni karışmış → `aciklama_paragraf` ile ilgili kısmı tut.
   Çöp **başta**ysa aralık kullan: `"1-"` ilk paragrafı atar.
4. **Şıklar başka soruya ait.** Gövde bir soruya, şıklar bambaşka soruya aitse ve doğru şıklar
   `KESILEN(...)` bloğunda görünüyorsa oradan geri koy; görünmüyorsa `at` (`soru_bozuk`).
5. **Görselli sorular.** `SORUDA_GORSEL` bayrağı varsa satırda bir dosya yolu yazar
   (`dataset_v3/inceleme/gorseller/…`); görseli Read aracıyla aç ve bak. Soru görsel olmadan
   çözülemiyorsa `at` (`gorsel_gerekli`).
6. **Bağlama bağlı sorular.** "Bir önceki soruda tanımlanan hasta…" gibi sorular tek başına
   çözülemez → `at` (`baglam_gerekli`).

---

## 6. Oturum bitince — kararlarını gönder

Karar dosyan **tek başına** yeterli; başka hiçbir şeyi commit'leme.

Sırasıyla:

1. Kontrol et: `python3 dataset_build/v3_uret.py` ardından `python3 dataset_build/v3_dogrula.py`
2. Kendi dalını aç: `git checkout -b kararlar/parca-03`
3. Yalnızca kendi karar dosyanı ekle: `git add dataset_v3/inceleme/kararlar_p03.jsonl`
4. Commit et: `git commit -m "parca 03: <n> karar"`
5. Dalını uzağa gönder (push): `git push -u origin kararlar/parca-03`

**Her oturum kendi dalına gönderir.** Dosya adları farklı olduğu için birleştirmede çakışma
çıkmaz; kararlar append-only, `v3_uret.py` tüm `kararlar*.jsonl` dosyalarını birlikte okur.

Son olarak kısa bir rapor yaz: kaç karar (ok / düzelt / at), dikkat çeken kalıplar, emin
olamadığın kayıtların id'leri.

---

## 7. Tempo

Ölçtüğümüz hız: kayıt başına **~1.150 token**, 400 kayıt ≈ 43 dakika. Listenin başı en sorunlu
kayıtlar, ilerledikçe ucuzlar.

Tek oturumda parçanın tamamını bitirmeye çalışma. **300–500 kayıtlık turlar** hâlinde ilerle,
her turun sonunda `durum` ile nerede olduğunu gör ve kararlarını gönder.

---

## 7b. Öncelikli listeler (riskli kayıtlar)

Parçalar veri setinin tamamını böler; içlerinde hem bozuk hem temiz kayıt vardır. Kredi sınırlı
olduğunda **önce bozuk olanlara** bakmak daha değerli. Bunun için ayrı listeler var:

| Liste | Kayıt | İçerik |
|---|---|---|
| `paylar/riskli_1..4.txt` | 4 × ~361 | Otomatik hattın bayrakladığı ya da elediği, yani sorunlu olması beklenen kayıtlar |

Kullanımı parçalarla aynı; yalnızca `PAY` değişkenini değiştir ve karar dosyana listeyle aynı adı ver:

```bash
export KARAR_DOSYA=kararlar_riskli_1.jsonl
export PAY=paylar/riskli_1.txt
```

Bu listeler `parca_03.txt` ile **çakışmayacak** şekilde üretildi; parça 03'te çalışan oturumla
aynı anda koşabilirler. Diğer parçalarla çakışırlar — riskli liste çalışırken `parca_04..08`
başlatma, önce riskli listeler bitsin.

Bitince dal adı: `kararlar/riskli-1` gibi.

---

## 8. Depoda ne var?

| Konum | İçerik |
|---|---|
| `paylar/parca_01..08.txt` | 8 parça × 2.149 kayıt id'si — oturumlar buradan iş alır |
| `dataset_v2/sft/tus_mcq_egitim.jsonl` | Girdi: 24.945 kayıtlık ham eğitim seti (**değiştirme**) |
| `dataset_v2/eval/` | Test setleri (838 kayıt) — eğitimden ayrı tutuluyor |
| `dataset_v3/inceleme/kararlar*.jsonl` | Şimdiye kadarki 7.753 karar |
| `dataset_v3/inceleme/REHBER.md` | Ayrıntılı karar kuralları |
| `dataset_v3/inceleme/gorseller/` | Görselli soruların resimleri (121 dosya) |
| `dataset_v3/inceleme/soruda_gorsel.json` | Hangi soruda görsel olduğu |
| `dataset_v3/inceleme/deasc.pkl`, `sozluk.pkl` | Türkçe karakter onarımı ve OCR çöpü ölçümü sözlükleri |
| `dataset_build/*.py` | Temizlik hattı, kontrol aracı, doğrulayıcı |
| `dataset_v3/sft/`, `dataset_v3/elenen/` | İlk komuttan sonra oluşur (depoda tutulmaz) |

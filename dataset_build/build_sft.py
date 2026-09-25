#!/usr/bin/env python3
"""
MinerU ciktilarindan Qwen3.5-4B SFT dataseti uretir.

Ilkeler
  - HICBIR tibbi bilgi uretilmez/tamamlanmaz. Sadece mekanik onarim.
  - Kaynak dosyalara dokunulmaz; her sey ayri dataset/ klasorune yazilir.
  - Her kayit kaynagina kadar izlenebilir (pdf, sayfa araligi, blok indeksleri).
  - Suphe varsa kayit atilmaz, flagged'a yazilir (sebebiyle).
"""
import argparse, hashlib, json, re, sys, unicodedata
from pathlib import Path
from collections import Counter

KOK        = Path(__file__).resolve().parent.parent
CIKTI_DIR  = KOK / "cikti"
DATASET    = KOK / "dataset"
PIPELINE   = "v1"

# Ingilizce sinav kitaplari gibi korpusa girmemesi gerekenler
HARIC = ("YDS", "İngilizce", "Ingilizce")

# ---------------------------------------------------------------- desenler
CEVAP = re.compile(
    r"(?:do[ğg]ru\s*cevap|yan[ıi]t|cevap)\s*[-–—:：]?\s*\(?\s*([A-Ea-e])\s*\)?(?!\w)",
    re.I)
SORU_BAS = re.compile(r"^\s*(\d{1,3})\s*[\.\)]\s*(?=\S)")
SIK_ISARET = re.compile(r"(?:^|\s)\(?([A-Ea-e])\s*[\)\.]", re.M)
# "1 – D" / "12 - B" bicimi: soru numarasi + harf, tek basina blok.
# Soru numarasi eslesmesi zorunlu -> yanlis eslesme riski dusuk.
CEVAP_NOLU = re.compile(r"^\s*(\d{1,3})\s*[–—\-]\s*([A-Ea-e])\s*[\.\)]?\s*$")
# OCR bazen soru numarasindan sonraki noktayi dusuruyor ("23 Asagidaki ...").
# Cevap taramasini bir sonraki soruya tasirmamak icin gevsek bir sinir deseni.
SORU_SINIR = re.compile(r"^\s*(\d{1,3})\s*[\.\)]?\s+[A-ZÇĞİÖŞÜ]")
SORU_IPUCU = re.compile(r"aşağıdaki|asagidaki|hangisi|hangisinde|değildir|degildir", re.I)

# --- aciklama temizligi desenleri (olculdu: log/yeni_bayraklar.json) ---
# Kitapcik/reklam gurultusu: icerikle ilgisi yok, blok duzeyinde atilir.
BOILERPLATE = re.compile(
    r"K[İI]TAP[ÇC]I[ĞG]I|DENEME\s*SINAVI|Önce\s*TUS|ABONE\s*OL|Bedava\s*Haz[ıi]rl[ıi]k|"
    r"www\.|http|Yar[ıi]şmalar,\s*Deneme|SORU\s*VE\s*A[ÇC]IKLAMALARI|"
    r"T[ıi]pta\s*Uzmanl[ıi]k\s*S[ıi]nav[ıi]na", re.I)
# Aciklamanin BASINA yapismis komsu sik ("E) Rotavirüs") ya da cevap satiri.
BAS_SIK   = re.compile(r"^\s*\(?[A-Ea-e]\s*[\)\.]\s+[^\n]{0,80}\n")
BAS_CEVAP = re.compile(r"^\s*\(?(?:doğru\s*)?cevap\s*[:\-–—]?\s*\(?[A-Ea-e]\)?[^\n]{0,80}\n?", re.I)
# Soruda sekil/resim/grafik atfi -> text-only modelde cozulemez, kayit flagged'a gider.
SEKLE_BAGLI = re.compile(
    r"şekilde|şekildeki|resimde|resimdeki|grafikte|grafikteki|görüntüde|fotoğrafta|"
    r"ok\s*işareti\s*ile|okla\s*gösterilen|yukarıdaki\s*şekil|aşağıdaki\s*şekil|"
    r"preparatta\s*görülen|"
    # EKG/trase ve goruntu atiflari - yuksek kesinlikli kaliplar (olculdu: 19 kayit,
    # yanlis pozitif yok). Genis "asagida verilen" kalibi KULLANILMAZ; o normal bir
    # soru ifadesidir ve gecerli kayitlari eler.
    r"(?:elektrokardiyogram|EKG|elektrokardiyografi|dalga)\s*\(?[^)\n]{0,24}\)?\s*trase|"
    r"aşağıdaki\s*elektrokardiyografi|aşağıdaki\s*(?:resim|fotoğraf|şema|çizim)|"
    r"(?:radyografi|grafi|tomografi|preparat)(?:si|sı)\s*aşağıda(?:ki|da)?\s*"
    r"(?:gibi|verilmiş|gösteril)", re.I)
# MinerU LaTeX artiklari: "$\% 7 0$" -> "%70"
LATEX_YUZDE = re.compile(r"\$\s*\\?%\s*([\d\s.,]+)\s*\$")
LATEX_SAYI  = re.compile(r"\$\s*([\d\s.,]+)\s*\$")
# Icerik tasimayan gerekce: yalnizca sinav yorumu ("kolay bir soru") ya da
# yarida kesilmis baslik ("...nedenleri:"). Modele eksik akil yurutme ogretir.
META_YORUM = re.compile(
    r"^(?:[^.\n]{0,120}\b(?:kolay|zor|klasik|spot|temel bilgi|sınav|soru(?:su|dur|lardan)|"
    r"kurtarıcı|vazgeçilmez|çeldirici|hatırlat|dikkat edin|bilmek yeterli)\b"
    r"[^.\n]{0,120}[.!]?\s*)+$", re.I)
ASILI_SON = re.compile(r"[:;,\-–—]\s*$")
# Onceki soruya atif yapan sorular tek baslarina cozulemez; modele eksik
# baglamdan cevap uretmeyi ogretirler.
BAGIMLI_SORU = re.compile(
    r"yukarıdaki\s*\(?\s*\d{1,3}|bir\s*önceki\s*soru|önceki\s*soruda|yukarıdaki\s*soruda|"
    r"yukarıdaki\s*olgu|\d{1,3}\s*\.?\s*soruda\s*(?:tanımlanan|anlatılan|verilen|belirtilen)|"
    r"yukarıda\s*(?:tanımlanan|anlatılan|verilen)\s*hasta", re.I)

TARIH = re.compile(r"\((Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|"
                   r"Eylül|Ekim|Kasım|Aralık)\s*(\d{4})\)")

CJK = {"，": ",", "；": ";", "：": ":", "（": "(", "）": ")",
       "、": ",", "。": ".", "？": "?", "！": "!", "－": "-"}


# ---------------------------------------------------------------- onarim
# Bu kelimeler ayri durur; "ağrısı ve" -> "ağrısıve" gibi bozmalari engeller.
AYRI_DURAN = {
    "ve", "ya", "da", "de", "ki", "bu", "şu", "o", "ile", "için", "gibi", "ise",
    "mi", "mı", "mu", "mü", "en", "her", "çok", "az", "bir", "iki", "üç", "dört",
    "beş", "ne", "ama", "veya", "hem", "ya", "ki", "te", "ta", "den", "dan",
    "ilk", "son", "tüm", "gün", "yaş", "kez", "kat", "ait", "olan", "olarak",
    "daha", "sonra", "önce", "göre", "kadar", "değil", "yok", "var",
}

VOCAB = {}          # korpustan uretilen kelime -> frekans (bosluk onarimi icin)
ONARIM_ORNEK = []   # denetlenebilirlik: yapilan birlestirmelerden ornekler


def sozluk_kur(kokler):
    """Korpusun kendi kelime dagarcigi. Sadece bolunmemis kelimeleri sayar."""
    import json as _j
    from collections import Counter as _C
    c = _C()
    for f in kokler:
        try:
            cl = _j.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for b in cl:
            t = b.get("text") or ""
            for w in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]{2,}", t):
                c[w.lower()] += 1
    VOCAB.update({w: n for w, n in c.items() if n >= 3})
    return len(VOCAB)


def bosluk_onar(t):
    """'doğ ru'->'doğru'. SADECE birlesince sozlukte gercek kelime olusuyorsa.
       Boylece 'ağrı var'->'ağrıvar' gibi bozmalar olmaz."""
    if not VOCAB:
        return t, 0
    n = 0

    def _b(m):
        nonlocal n
        sol, sag = m.group(1), m.group(2)
        birlesik = (sol + sag).lower()
        sl, sg = sol.lower(), sag.lower()
        if sg in AYRI_DURAN or sl in AYRI_DURAN:
            return m.group(0)                      # islev kelimesi: asla birlestirme
        if VOCAB.get(sl, 0) >= 5 and VOCAB.get(sg, 0) >= 5:
            return m.group(0)                      # ikisi de gercek kelime: dokunma
        # birlesik sozlukte VE saglam bir kazanc varsa birlestir
        if VOCAB.get(birlesik, 0) >= 3 and VOCAB.get(birlesik, 0) > VOCAB.get(sg, 0):
            n += 1
            if len(ONARIM_ORNEK) < 40:
                ONARIM_ORNEK.append(f"{sol} {sag} -> {sol+sag}")
            return sol + sag
        return m.group(0)

    # sol parca Turkce diakritikle bitiyor, sag parca kucuk harfle basliyor
    onceki = None
    for _ in range(3):        # "aş ağ ıdakilerden" gibi cok parcali bolunmeler
        if t == onceki:
            break
        onceki = t
        t = re.sub(r"\b([A-Za-zÇĞİÖŞÜçğıöşü]*[çğıöşüÇĞİÖŞÜ])\s+([a-zçğıöşü]{1,8})\b", _b, t)
    return t, n


def hece_orani(t):
    """Hecelenmis metin tespiti: cok kisa token orani.
       Sik harfleri (A/B/C/D/E) ve tibbi kisaltmalar (IL, IgE, DNA) HARIC -
       bunlar tibbi metinde normaldir, heceleme belirtisi degildir."""
    t = re.sub(r"(?:^|\s)\(?[A-Ea-e]\s*[\)\.]", " ", t)      # sik isaretleri
    t = re.sub(r"\b[A-Za-z]{1,4}[-–]?\d+\b", " ", t)          # IL-4, ApoA-I, B12
    toks = [w for w in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", t)
            if len(w) > 1 and not _kisaltma(w)]
    if len(toks) < 15:
        return 0.0
    return sum(1 for w in toks if len(w) <= 3) / len(toks)


def hece_birlestir(t, max_parca=6, min_frek=3):
    """Hece hece bolunmus metni SOZLUGE dayanarak geri birlestir.
       Sozlukte karsiligi olmayan hicbir birlesim yapilmaz -> uydurma yok."""
    if not VOCAB:
        return t, 0
    parcalar = re.split(r"(\s+)", t)
    cikti, i, n = [], 0, 0
    KELIME = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü]+")
    while i < len(parcalar):
        p = parcalar[i]
        if not p.strip() or not KELIME.fullmatch(p):
            cikti.append(p); i += 1; continue
        en_iyi, birikim, j = None, [], i
        while j < len(parcalar) and len(birikim) < max_parca:
            q = parcalar[j]
            if q.strip():
                if not KELIME.fullmatch(q):
                    break
                birikim.append(q)
                aday = "".join(birikim)
                if len(birikim) > 1 and VOCAB.get(aday.lower(), 0) >= min_frek:
                    en_iyi = (j, aday)
            j += 1
        if en_iyi:
            cikti.append(en_iyi[1]); i = en_iyi[0] + 1; n += 1
        else:
            cikti.append(p); i += 1
    return "".join(cikti), n


def html_coz(t):
    """<table><tr><td> ... -> okunabilir satir metni.
       Tablo icerigi korunur, etiketler atilir (egitim verisine HTML girmesin)."""
    if "<" not in t:
        return t
    t = re.sub(r"<\s*/?\s*(?:thead|tbody|table)\s*>", "\n", t, flags=re.I)
    t = re.sub(r"<\s*/\s*tr\s*>", "\n", t, flags=re.I)
    t = re.sub(r"<\s*/\s*t[dh]\s*>", " | ", t, flags=re.I)
    t = re.sub(r"<[^>]{0,80}>", " ", t)                 # kalan etiketler
    t = re.sub(r"\s*\|\s*(?=\n|$)", "", t)             # satir sonu bos hucre
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t


def onar(t: str):
    """Sadece MEKANIK duzeltmeler. Icerik eklemez."""
    if not t:
        return "", Counter()
    s = Counter()
    t = unicodedata.normalize("NFC", t)

    if "<" in t:
        oncesi = len(t)
        t = html_coz(t)
        if len(t) != oncesi:
            s["html_temizlendi"] += 1

    for a, b in CJK.items():
        if a in t:
            s["cjk_noktalama"] += t.count(a)
            t = t.replace(a, b)

    # ligatur bolunmesi: "hidrofi lik" -> "hidrofilik", "fi zyolojik" -> "fizyolojik"
    t2, n = re.subn(r"(?<=[A-Za-zÇĞİÖŞÜçğıöşü])f([il])\s+(?=[a-zçğıöşü])", r"f\1", t)
    if n:
        s["ligatur"] += n
    t = t2
    t2, n = re.subn(r"\bf([il])\s+(?=[a-zçğıöşü]{2,})", r"f\1", t)
    if n:
        s["ligatur"] += n
    t = t2

    # satir sonu tirelemesi
    t2, n = re.subn(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)
    if n:
        s["tireleme"] += n
    t = t2

    t2, n = bosluk_onar(t)
    if n:
        s["bosluk_birlestirme"] += n
    t = t2

    if hece_orani(t) > 0.40:                 # sadece hecelenmis metinde calis
        t2, n = hece_birlestir(t)
        if n:
            s["hece_birlestirme"] += n
        t = t2

    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip(), s


def aciklama_temizle(t: str):
    """Gerekce metninden AIT OLMAYAN parcalari ayiklar. Icerik EKLEMEZ."""
    if not t:
        return t, Counter()
    say = Counter()

    m = BAS_SIK.match(t)                      # basa yapismis komsu sik satiri
    if m:
        t = t[m.end():]
        say["bas_sik_atildi"] += 1

    m = BAS_CEVAP.match(t)                    # basta duran "Dogru cevap: X" satiri
    if m:
        t = t[m.end():]
        say["bas_cevap_atildi"] += 1

    satirlar = t.split("\n")                  # kitapcik/reklam satirlari
    kalan = [x for x in satirlar if not BOILERPLATE.search(x)]
    if len(kalan) != len(satirlar):
        say["boilerplate_atildi"] += len(satirlar) - len(kalan)
        t = "\n".join(kalan)

    t2 = LATEX_YUZDE.sub(lambda m: "%" + m.group(1).replace(" ", ""), t)
    t2 = LATEX_SAYI.sub(lambda m: m.group(1).replace(" ", ""), t2)
    if t2 != t:
        say["latex_sadelestirildi"] += 1
    t = t2

    return re.sub(r"\n{3,}", "\n\n", t).strip(), say


def blok_metni(b):
    if b.get("type") == "table":
        return (b.get("table_body") or "").strip()
    return (b.get("text") or "").strip()


def icerik_mi(b):
    """discarded = sayfa ustu/alti tekrarlari; aciklamaya girmemeli."""
    return b.get("type") in ("text", "list", "table")


def sik_sayisi(t):
    return len({m.group(1).upper() for m in SIK_ISARET.finditer(t)})


# ---------------------------------------------------------------- kalite
def _kisaltma(w):
    """DNA, HDL, IL, spp, IgE, TSH ... tibbi metinde normaldir, cop degildir."""
    if len(w) <= 5 and w.isupper():
        return True                      # DNA, HDL, TSH, PCR
    if len(w) <= 4 and w[0].isupper() and any(c.isupper() for c in w[1:]):
        return True                      # IgE, IgG, mRNA
    if w.lower() in {"spp", "sp", "ssp", "var", "cf", "pH", "ml", "mg", "kg"}:
        return True
    return False


def cop_orani(t):
    toks = [w for w in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]{2,}", t) if not _kisaltma(w)]
    if not toks:
        return 0.0
    sesli = set("aeıioöuüAEIİOÖUÜ")
    cop = sum(1 for w in toks
              if not (set(w) & sesli)
              or re.search(r"[bcçdfgğhjklmnprsştvyzBCÇDFGĞHJKLMNPRSŞTVYZ]{5,}", w))
    return cop / len(toks)


def tr_orani(t):
    toks = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]{2,}", t)
    if not toks:
        return 0.0
    return sum(1 for w in toks if set(w) & set("ıİğĞşŞçÇöÖüÜ")) / len(toks)


# ---------------------------------------------------------------- ayristirma
def sorulari_ayikla(cl, kaynak_bilgi):
    """content_list bloklari -> soru birimleri"""
    # Cevap isareti 'discarded' (sayfa ustu/alti) bloklara dusebiliyor:
    # ARAMA tum tiplerde yapilir, ama ACIKLAMA metnine sadece gercek icerik alinir.
    def _metin(b):
        if b.get("type") == "table":
            return (b.get("table_body") or "").strip()
        return (b.get("text") or "").strip()

    bloklar = [(i, b) for i, b in enumerate(cl)
               if b.get("type") in ("text", "list", "table", "discarded") and _metin(b)]
    sorular, i = [], 0
    while i < len(bloklar):
        idx, b = bloklar[i]
        t = blok_metni(b)
        m = SORU_BAS.match(t)
        if not m:
            i += 1
            continue

        soru_no = m.group(1)
        bas_idx = idx
        govde = [t]
        j = i + 1
        siklar = None
        # soru govdesi + siklar
        while j < len(bloklar) and j - i < 8:
            _, bb = bloklar[j]
            tt = blok_metni(bb)
            if sik_sayisi(tt) >= 3:
                siklar = tt
                j += 1
                break
            if SORU_BAS.match(tt) and icerik_mi(bb):
                break
            if icerik_mi(bb):
                govde.append(tt)
            j += 1
        if siklar is None:
            i += 1
            continue

        # Siklardan sonraki bolgeyi topla. Cevap bu bolgede NEREDE olursa olsun bulunur:
        #   - "Doğru cevap: B" / "Yanıt – D"   (aciklamadan SONRA)
        #   - "1 – D"                           (aciklamadan ONCE, soru no eslesmeli)
        aciklama, cevap, son_idx = [], None, bas_idx
        cevap_adaylari = []
        while j < len(bloklar) and j - i < 60:
            jdx, bb = bloklar[j]
            tt = blok_metni(bb)

            # Cevap aciklama blogunun BASINA yapisik olabilir: "84 -C MEDULLER..."
            gm = re.match(r"\s*(\d{1,3})\s*[-–—]?\s*([A-Ea-e])\b", tt)
            if gm and gm.group(1) == soru_no and cevap is None:
                cevap = gm.group(2).upper()
                tt = tt[gm.end():].lstrip(" .-–—")      # onekini aciklamadan ayikla
                if icerik_mi(bb) and tt.strip():
                    aciklama.append(tt)
                    son_idx = max(son_idx, jdx)
                j += 1
                continue

            nm = CEVAP_NOLU.match(tt)
            if nm and nm.group(1) == soru_no:
                cevap = nm.group(2).upper()
                son_idx = max(son_idx, jdx)
                j += 1
                continue                      # aciklama devam edebilir

            cm = CEVAP.search(tt)
            if cm and len(tt) < 60:           # kisa, tek basina cevap blogu
                cevap_adaylari.append(cm.group(1).upper())
                cevap = cevap or cm.group(1).upper()   # ILKINI tut, uzerine yazma
                son_idx = max(son_idx, jdx)
                j += 1
                continue                      # aciklama cevaptan SONRA da gelebilir
            if cm:
                cevap_adaylari.append(cm.group(1).upper())
                cevap = cevap or cm.group(1).upper()

            if SORU_BAS.match(tt) and len(tt) > 25 and icerik_mi(bb):
                break
            # Noktasi dusmus soru basligi: cevabi bulduysak ya da metin soru
            # kokune benziyorsa burada dur, sonraki sorunun cevabini kapma.
            sm = SORU_SINIR.match(tt)
            if sm and icerik_mi(bb) and sm.group(1) != soru_no and (
                    cevap is not None or SORU_IPUCU.search(tt[:160])):
                break
            if icerik_mi(bb):
                if not BOILERPLATE.search(tt):        # kitapcik gurultusunu hic alma
                    aciklama.append(tt)
                son_idx = max(son_idx, jdx)
            j += 1

        sorular.append(dict(
            no=soru_no, govde="\n".join(govde), siklar=siklar,
            aciklama="\n".join(aciklama).strip(), cevap=cevap,
            cevap_adaylari=sorted(set(cevap_adaylari)),
            blok=[bas_idx, son_idx],
            sayfa=[cl[bas_idx].get("page_idx"), cl[son_idx].get("page_idx")]))
        i = j
    return sorular


def soru_anahtari(t):
    """Dokumanlar arasi ayni soruyu yakalamak icin normalize edilmis anahtar."""
    t = t.lower()
    t = re.sub(r"^\s*\d{1,3}\s*[\.\)]\s*", "", t)     # soru numarasi
    t = re.sub(r"\([^)]*\d{4}\)", "", t)                # (Nisan 2010)
    return re.sub(r"[^a-zçğıöşü0-9]+", "", t)


# ---------------------------------------------------------------- kayit
def kayit_yap(s, kaynak, grup, sayac):
    ham = f"{s['govde']}\n{s['siklar']}"
    soru, d1 = onar(ham)
    aciklama, d2 = onar(s["aciklama"])
    aciklama, d3 = aciklama_temizle(aciklama)     # ait olmayan parcalari ayikla
    sayac.update(d1); sayac.update(d2); sayac.update(d3)

    sinav = None
    tm = TARIH.search(soru)
    if tm:
        sinav = f"{tm.group(1)} {tm.group(2)}"

    kimlik = hashlib.sha256(f"{kaynak}|{s['blok']}|{soru[:80]}".encode()).hexdigest()[:16]
    # blok indeksleri parser degisince kayabiliyor; soru metnine dayali
    # SABIT ikincil kimlik, onarim dosyalariyla eslesmeyi korur.
    anahtar_id = hashlib.sha256(soru_anahtari(soru).encode()).hexdigest()[:16]
    meta = dict(source_pdf=kaynak, group=grup, question_no=s["no"],
                pages=s["sayfa"], blocks=s["blok"], exam=sinav,
                anahtar_id=anahtar_id,
                cevap_adaylari=s.get("cevap_adaylari") or [],
                pipeline=PIPELINE,
                quality=dict(cop=round(cop_orani(soru + aciklama), 3),
                             tr=round(tr_orani(soru + aciklama), 3),
                             aciklama_uz=len(aciklama)))

    # --- kalite kapilari ---
    hata = []
    if not s["cevap"]:
        hata.append("cevap_yok")
    # Siklardan sonraki pencerede BIRDEN FAZLA farkli cevap harfi bulunduysa
    # (iki sutunlu sayfa duzeni bozulmasi) anahtar guvenilmez -> egitime girmesin.
    if len(s.get("cevap_adaylari") or []) > 1:
        hata.append("coklu_anahtar(" + "".join(s["cevap_adaylari"]) + ")")
    # Soru bir sekle/resme/EKG'ye atif yapiyorsa text-only modelde cozulemez.
    if SEKLE_BAGLI.search(soru):
        hata.append("sekle_bagli")
    if BAGIMLI_SORU.search(soru):
        hata.append("onceki_soruya_bagimli")
    # Gerekce bozuk tablo dokumunden ibaretse akil yurutme olarak kullanilamaz.
    if aciklama and len(re.findall(r"\|.*\|.*\|", aciklama)) >= 2:
        hata.append("tablo_kalintisi")
    if sik_sayisi(s["siklar"]) < 3:
        hata.append("sik_eksik")
    if len(soru) < 40:
        hata.append("soru_kisa")
    if meta["quality"]["cop"] > 0.12:
        hata.append("ocr_bozuk")
    if len(aciklama) < 40:
        hata.append("aciklama_kisa")
    elif META_YORUM.match(aciklama.strip()):
        hata.append("iceriksiz_gerekce")          # yalnizca sinav yorumu
    elif ASILI_SON.search(aciklama.strip()) and len(aciklama) < 200:
        hata.append("yarim_gerekce")              # cumle ortasinda kesilmis
    ho = hece_orani(soru + " " + aciklama)
    if ho > 0.40:
        hata.append(f"hece_bolunmesi({ho:.2f})")
    meta["quality"]["hece"] = round(ho, 3)

    if hata:
        return dict(id=kimlik, soru=soru, siklar=s["siklar"], aciklama=aciklama,
                    cevap=s["cevap"], meta=meta, sorunlar=hata), False

    icerik = f"<think>\n{aciklama}\n</think>\n\nDoğru cevap: {s['cevap']}"
    return dict(id=kimlik,
                messages=[{"role": "user", "content": soru},
                          {"role": "assistant", "content": icerik}],
                meta=meta), True


# ---------------------------------------------------------------- ana
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cikti", default=str(CIKTI_DIR))
    ap.add_argument("--dataset", default=str(DATASET))
    a = ap.parse_args()

    cdir, ddir = Path(a.cikti), Path(a.dataset)
    (ddir / "sft").mkdir(parents=True, exist_ok=True)
    (ddir / "flagged").mkdir(parents=True, exist_ok=True)

    temiz_kayitlar = []          # once topla, sonra tekille/celiski ayikla
    flag_f = open(ddir / "flagged" / "tus_mcq_flagged.jsonl", "w", encoding="utf-8")

    kokler = sorted(cdir.rglob("*content_list.json"))
    print(f"sozluk kuruluyor ({len(kokler)} dokuman)...", flush=True)
    print(f"  {sozluk_kur(kokler)} kelime\n")

    toplam_ok = toplam_flag = 0
    toplam_kopya = [0]
    onarim = Counter()
    rapor = []

    for f in sorted(cdir.rglob("*content_list.json")):
        dok = f.parent.parent.name
        if any(h in dok for h in HARIC):
            rapor.append((dok, 0, 0, "atlandi (kapsamdisi)"))
            continue
        grup = f.relative_to(cdir).parts[0]
        kaynak = str(f.parent.parent.relative_to(cdir))
        try:
            cl = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            rapor.append((dok, 0, 0, f"okunamadi: {e}")); continue

        sorular = sorulari_ayikla(cl, kaynak)

        # Deneme sinavlarinda ayni soru iki kez gecer:
        #   once soru kitapciginda (cevapsiz), sonra cevap bolumunde (tam).
        # Ayni numara icin EN IYI adayi tut, digerlerini kopya olarak at.
        en_iyi = {}
        for q in sorular:
            anahtar = (q["no"], (q["govde"] or "")[:40])
            puan = (1 if q["cevap"] else 0, len(q["aciklama"] or ""))
            mevcut = en_iyi.get(q["no"])
            if mevcut is None or puan > mevcut[0]:
                en_iyi[q["no"]] = (puan, q)
        kopya = len(sorular) - len(en_iyi)
        sorular = [v[1] for v in en_iyi.values()]
        toplam_kopya[0] += kopya

        ok = fl = 0
        for s in sorular:
            kayit, gecti = kayit_yap(s, kaynak, grup, onarim)
            if gecti:
                temiz_kayitlar.append(kayit); ok += 1
            else:
                flag_f.write(json.dumps(kayit, ensure_ascii=False) + "\n"); fl += 1
        toplam_ok += ok; toplam_flag += fl
        tip = "soru bankasi" if (ok + fl) >= 10 else "ders kitabi"
        rapor.append((dok, ok, fl, tip))

    # --- Dokumanlar arasi tekilleme ve celiski tespiti ---
    from collections import defaultdict as _dd
    gruplar = _dd(list)
    for k in temiz_kayitlar:
        gruplar[soru_anahtari(k["messages"][0]["content"])].append(k)

    yazilan, tekrar, celiski = 0, 0, 0
    with open(ddir / "sft" / "tus_mcq.jsonl", "w", encoding="utf-8") as sft_f:
        for anahtar, kume in gruplar.items():
            harfler = {k["messages"][1]["content"].strip()[-1] for k in kume}
            if len(harfler) > 1:
                # Ayni soru farkli cevapla geliyor -> biri hatali, egitime girmemeli
                celiski += 1
                for k in kume:
                    k["sorunlar"] = [f"celiskili_cevap({''.join(sorted(harfler))})"]
                    k["kaynaklar"] = [x["meta"]["source_pdf"] for x in kume]
                    flag_f.write(json.dumps(k, ensure_ascii=False) + "\n")
                continue
            # Ayni soru ayni cevap -> en uzun aciklamaliyi tut
            en_iyi = max(kume, key=lambda k: len(k["messages"][1]["content"]))
            if len(kume) > 1:
                tekrar += len(kume) - 1
                en_iyi["meta"]["duplicate_count"] = len(kume)
                en_iyi["meta"]["duplicate_sources"] = [k["meta"]["source_pdf"] for k in kume]
            sft_f.write(json.dumps(en_iyi, ensure_ascii=False) + "\n")
            yazilan += 1
    flag_f.close()
    toplam_ok = yazilan

    print(f"{'dokuman':<50}{'SFT':>7}{'flag':>7}  tip")
    print("-" * 82)
    for d, o, fl, t in rapor:
        if o or fl or "atlandi" in t:
            print(f"{d[:49]:<50}{o:>7}{fl:>7}  {t}")
    print("-" * 82)
    print(f"{'TOPLAM':<50}{toplam_ok:>7}{toplam_flag:>7}")
    print(f"\ndokuman ici kopya      : {toplam_kopya[0]} elendi")
    print(f"dokumanlar arasi tekrar: {tekrar} elendi (en uzun aciklamali tutuldu)")
    print(f"CELISKILI cevap        : {celiski} soru flagged'a alindi")
    print(f"mekanik onarim: {dict(onarim)}")
    if ONARIM_ORNEK:
        print("  birlestirme ornekleri:", "; ".join(ONARIM_ORNEK[:12]))
    print(f"\nSFT     : {ddir/'sft'/'tus_mcq.jsonl'}")
    print(f"flagged : {ddir/'flagged'/'tus_mcq_flagged.jsonl'}")


if __name__ == "__main__":
    main()

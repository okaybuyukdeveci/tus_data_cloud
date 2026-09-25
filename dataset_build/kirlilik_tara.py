#!/usr/bin/env python3
"""Egitim setindeki GEREKCE (aciklama) metinlerinde kirlilik tarar.

Kirlilik = iki sutunlu sayfa duzeni bozulunca komsu sorunun metninin
aciklamaya karismasi. Hicbir sey degistirmez, yalnizca olcer ve listeler.
"""
import json, re, sys, pathlib, unicodedata
from collections import Counter

KOK = pathlib.Path(__file__).resolve().parent.parent
YOL = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else KOK/"dataset_v2/sft/tus_mcq_egitim.jsonl"

# --- kirlilik isaretleri ---
YENI_SORU   = re.compile(r"(?:^|\n)\s*\d{1,3}\s*[.)]\s*[A-ZÇĞİÖŞÜ]")      # aciklama icinde yeni soru basligi
SIK_BLOGU   = re.compile(r"(?:^|\s)\(?([A-Ea-e])\s*[\)\.]\s+\S")           # sik isaretleri
CEVAP_SAT   = re.compile(r"(?:do[ğg]ru\s*)?cevap\s*[:\-–—]?\s*[A-Ea-e]\b", re.I)
SORU_ETIKET = re.compile(r"\bSORU\s*\d{1,3}\b", re.I)
KITAPCIK    = re.compile(r"K[İI]TAP[ÇC]I[ĞG]I|DENEME SINAVI|Önce TUS|ABONE OL|www\.|Bedava", re.I)

DURAK = set("""ve veya ile bir bu şu o da de ki mi mı mu mü için gibi olarak olan olur oldu
daha en çok az ise ancak fakat ama yani hem her hangi hangisi aşağıdakilerden aşağıdaki
değildir yanlış doğru nedir kaçtır göre sonra önce arasında içinde üzerine karşı
hasta hastada hastanın tanı tedavi görülür yapılır bulunur olabilir edilir""".split())

def sadele(t):
    """Kaba Turkce govdeleme: ilk 6 karakter. 'mantarlarda' ve 'mantar' eslesir."""
    t = unicodedata.normalize("NFKC", t).lower()
    return [w[:6] for w in re.findall(r"[a-zçğıöşü]{4,}", t) if w not in DURAK]

def govde(soru):
    """Soru kokunu al (siklardan onceki kisim)."""
    return re.split(r"(?:^|\s)\(?[A-Ea-e]\s*[\)\.]\s", soru)[0]

def analiz(soru, aciklama):
    bayrak = []
    if YENI_SORU.search(aciklama):                      bayrak.append("yeni_soru_basligi")
    harfler = {m.group(1).upper() for m in SIK_BLOGU.finditer(aciklama)}
    if len(harfler) >= 4:                               bayrak.append("sik_blogu")
    if len(CEVAP_SAT.findall(aciklama)) >= 1:           bayrak.append("cevap_satiri")
    if SORU_ETIKET.search(aciklama):                    bayrak.append("soru_etiketi")
    if KITAPCIK.search(aciklama):                       bayrak.append("kitapcik_metni")
    # konu ortusmesi: soru kokundeki icerik kelimelerinin aciklamada bulunma orani
    sk = set(sadele(govde(soru)))
    ak = set(sadele(aciklama))
    ortusme = len(sk & ak) / len(sk) if sk else 1.0
    if sk and ortusme < 0.10:                           bayrak.append(f"dusuk_ortusme({ortusme:.2f})")
    return bayrak, ortusme

def main():
    sayac, ortusmeler, ornek = Counter(), [], []
    n = kirli = 0
    with (KOK/"log/kirli_kayitlar.jsonl").open("w", encoding="utf-8") as cik:
        for l in YOL.open(encoding="utf-8"):
            r = json.loads(l); n += 1
            soru = r["messages"][0]["content"]
            asis = r["messages"][1]["content"]
            m = re.search(r"<think>\n?(.*?)\n?</think>", asis, re.S)
            acik = m.group(1) if m else ""
            if not acik.strip():
                sayac["aciklama_bos"] += 1; continue
            bayrak, ort = analiz(soru, acik)
            ortusmeler.append(ort)
            if bayrak:
                kirli += 1
                for b in bayrak: sayac[b.split("(")[0]] += 1
                sayac[f"bayrak_sayisi_{len(bayrak)}"] += 1
                cik.write(json.dumps({"id": r["id"], "bayraklar": bayrak,
                                      "ortusme": round(ort,3)}, ensure_ascii=False)+"\n")
                if len(ornek) < 4 and len(bayrak) >= 2:
                    ornek.append((r["id"], bayrak, soru[:70], acik[:160]))
            else:
                sayac["temiz"] += 1
    ortusmeler.sort()
    print(f"toplam kayit          : {n}")
    print(f"gerekce ICEREN        : {len(ortusmeler)}")
    print(f"  TEMIZ               : {sayac['temiz']}  (%{100*sayac['temiz']/max(1,len(ortusmeler)):.1f})")
    print(f"  en az 1 bayrak      : {kirli}  (%{100*kirli/max(1,len(ortusmeler)):.1f})")
    print(f"gerekce YOK/BOS       : {sayac['aciklama_bos']}")
    print("\nbayrak dagilimi:")
    for k in ["yeni_soru_basligi","sik_blogu","cevap_satiri","soru_etiketi","kitapcik_metni","dusuk_ortusme"]:
        if sayac[k]: print(f"  {k:20} {sayac[k]:6}  (%{100*sayac[k]/max(1,len(ortusmeler)):.1f})")
    print("\nbayrak sayisina gore:")
    for i in range(1,7):
        if sayac[f"bayrak_sayisi_{i}"]: print(f"  {i} bayrak: {sayac[f'bayrak_sayisi_{i}']}")
    if ortusmeler:
        y=lambda q: ortusmeler[int(len(ortusmeler)*q)-1]
        print(f"\nsoru-gerekce konu ortusmesi: medyan {y(0.5):.2f} | p10 {y(0.1):.2f} | p25 {y(0.25):.2f}")
    print("\n--- ornekler (>=2 bayrak) ---")
    for i,b,s,a in ornek:
        print(f"\n[{i}] {b}\n  S: {s}\n  G: {a}")

if __name__ == "__main__":
    main()

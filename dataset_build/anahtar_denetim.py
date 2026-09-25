#!/usr/bin/env python3
"""Cevap anahtari denetimi.

Iki sutunlu sayfa duzeni MinerU cikisinda bozuldugunda, bir sorunun siklarindan
sonra IKI farkli "Cevap X" satiri ust uste dusebiliyor: birincisi sol sutundaki
onceki soruya, ikincisi asil soruya ait. build_sft ilkini aldigi icin bu
kayitlarda anahtar YANLIS olabiliyor.

Bu betik hicbir seyi degistirmez; yalnizca supheli kayitlari listeler.
"""
import json, re, sys, pathlib
from collections import Counter

KOK = pathlib.Path(__file__).resolve().parent.parent
CIKTI = KOK / "cikti"
CEV = re.compile(r"^\s*#?\s*(?:Doğru\s+)?[CcĞğ]?[Ee]vap\s*[:.]?\s*([A-Ea-e])\s*[.)]?\s*$", re.M)
SORU_BAS = re.compile(r"^\s*\d{1,3}\s*[.)]\s+\S", re.M)

_md_onbellek = {}
def kaynak_metni(src):
    if src not in _md_onbellek:
        p = next(iter(CIKTI.glob(f"{src}/auto/*.md")), None)
        _md_onbellek[src] = p.read_text(encoding="utf-8") if p else None
    return _md_onbellek[src]

def ilk_satir(soru):
    return re.sub(r"\s+", " ", soru.split("\n")[0]).strip()

def denetle(kayit, soru_metni):
    src = kayit.get("meta", {}).get("source_pdf")
    if not src: return None
    txt = kaynak_metni(src)
    if txt is None: return ("KAYNAK_YOK", None, None)
    bas = ilk_satir(soru_metni)
    pos = txt.find(bas[:60])
    if pos < 0:
        pos = txt.find(" ".join(bas.split()[1:9]))
    if pos < 0: return ("BULUNAMADI", None, None)
    pencere = txt[pos:pos + 1800]
    # bir sonraki soru basligina kadar kirp (ilk satiri atlayarak ara)
    m2 = SORU_BAS.search(pencere, 40)
    if m2: pencere = pencere[:m2.start()]
    harfler = [m.group(1).upper() for m in CEV.finditer(pencere)]
    if not harfler: return ("ANAHTAR_YOK", None, None)
    tekil = list(dict.fromkeys(harfler))
    if len(tekil) > 1: return ("COKLU_ANAHTAR", harfler, None)
    return ("TEK", harfler, tekil[0])

def cevap_cikar(kayit):
    if "cevap" in kayit: return kayit["cevap"]
    for m in kayit.get("messages", []):
        if m["role"] == "assistant":
            mm = re.search(r"Doğru cevap:\s*([A-E])", m["content"])
            if mm: return mm.group(1)
    return None

def soru_cikar(kayit):
    if "soru" in kayit: return kayit["soru"]
    for m in kayit.get("messages", []):
        if m["role"] == "user": return m["content"]
    return ""

def main(yol, limit=None):
    sayac = Counter(); supheli = []
    for i, l in enumerate(open(yol, encoding="utf-8")):
        if limit and i >= limit: break
        k = json.loads(l)
        durum, harfler, tek = denetle(k, soru_cikar(k))
        if durum is None: sayac["META_YOK"] += 1; continue
        sayac[durum] += 1
        kayitli = cevap_cikar(k)
        if durum == "COKLU_ANAHTAR":
            supheli.append((k["id"], kayitli, harfler, ilk_satir(soru_cikar(k))[:70]))
        elif durum == "TEK" and kayitli and tek != kayitli:
            sayac["TEK_FARKLI"] += 1
            supheli.append((k["id"], kayitli, [tek], ilk_satir(soru_cikar(k))[:70]))
    print("== ozet ==")
    for k, v in sayac.most_common(): print(f"  {k:16} {v}")
    print(f"== supheli: {len(supheli)} ==")
    for s in supheli[:40]: print(" ", s[0], "kayit=", s[1], "kaynak=", s[2], "|", s[3])
    json.dump([{"id":a,"kayitli":b,"kaynak":c,"soru":d} for a,b,c,d in supheli],
              open(KOK/"log"/f"anahtar_supheli_{pathlib.Path(yol).stem}.json","w",encoding="utf-8"),
              ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)

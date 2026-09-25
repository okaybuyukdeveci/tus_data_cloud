#!/usr/bin/env python3
"""Onarim icin siradaki partiyi getirir. Onarilmis olanlari atlar."""
import json, pathlib, re, sys, hashlib

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "dataset_build"))
from build_sft import soru_anahtari

# v2 = duzeltilmis cevap-anahtari parser'i (bkz. build_sft.py, SORU_SINIR)
DS     = KOK / "dataset_v2"
FLAG   = DS / "flagged/tus_mcq_flagged.jsonl"
ONAR   = DS / "onarilmis/tus_mcq_onarilmis.jsonl"
ITIRAZ = DS / "flagged/itiraz.jsonl"
ATIL   = DS / "flagged/kullanilamaz.jsonl"
EVAL   = [DS / "eval/tus_mcq_eval.jsonl", DS / "eval/tus_mcq_eval_aciklamali.jsonl"]

# Blok indeksleri parser degisiminde kaydigi icin kimlik yerine soru metnine
# dayali SABIT anahtar kullanilir.
aid = lambda t: hashlib.sha256(soru_anahtari(t).encode()).hexdigest()[:16]

def _metin(r):
    return r["messages"][0]["content"] if "messages" in r else r.get("soru", "")

SORU_IPUCU = re.compile(r"hangisi|hangileri|nedir|kaçtır|değildir|yanlış|doğru olan|"
                        r"beklenmez|görülmez|söylenebilir|düşünülür|uygundur|seçiniz|işaretleyiniz", re.I)
ANAHTAR = re.compile(r"\d{1,2}\s*[-–]\s*[A-E](\s*,\s*\d{1,2}\s*[-–]\s*[A-E]){2,}")


def siklar(t):
    return {x.upper() for x in re.findall(r"(?:^|\s)\(?([A-Ea-e])\s*[\)\.]\s", t)}


def saglam(r):
    soru = " ".join((r.get("soru") or "").split())
    acik = " ".join((r.get("aciklama") or "").split())
    govde = re.split(r"(?:^|\s)\(?[A-Ea-e]\s*[\)\.]\s", soru)[0]
    if not SORU_IPUCU.search(govde): return False
    if not re.match(r"^\s*\d{1,3}\s*[\.\)]", soru): return False
    if ANAHTAR.search(acik) or ANAHTAR.search(soru): return False
    if len(siklar(acik)) >= 4: return False
    if len(siklar(soru)) < 4: return False
    return True


def main():
    tur = sys.argv[1] if len(sys.argv) > 1 else "cevap_yok"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    bitmis = set()
    # onarilan + itiraz edilen + atilan + DEGERLENDIRMEYE ayrilan
    for dosya in (ONAR, ITIRAZ, ATIL, *EVAL):
        if not dosya.exists(): continue
        for l in dosya.open(encoding="utf-8"):
            r = json.loads(l)
            bitmis.add(aid(_metin(r)))
            o = r.get("meta", {}).get("onarim", {}).get("orijinal_soru")
            if o: bitmis.add(aid(o))
    havuz = []
    for l in FLAG.open(encoding="utf-8"):
        r = json.loads(l)
        if "soru" not in r: continue
        if aid(r["soru"]) in bitmis or not saglam(r): continue
        s = sorted(x.split("(")[0] for x in r["sorunlar"])
        if tur == "cevap_yok" and s == ["cevap_yok"]: havuz.append(r)
        elif tur == "aciklama_kisa" and s == ["aciklama_kisa"]: havuz.append(r)
        elif tur == "celiskili" and "celiskili_cevap" in s: havuz.append(r)
        elif tur == "coklu_anahtar" and "coklu_anahtar" in s: havuz.append(r)
    print(f"# havuzda {len(havuz)} kayit ({tur}) | bitmis {len(bitmis)}\n")
    for r in havuz[:n]:
        print(f"### {r['id']}")
        print("S:", " ".join(r["soru"].split())[:400])
        a = " ".join((r.get("aciklama") or "").split())
        if a: print("A:", a[:300])
        if r.get("cevap"): print("CEVAP:", r["cevap"])
        ad = r["meta"].get("cevap_adaylari") or []
        if len(ad) > 1: print("ADAYLAR:", "/".join(ad), "<-- anahtar SUPHELI")
        print()


if __name__ == "__main__":
    main()

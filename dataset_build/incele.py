"""Elle inceleme araci (v3).

  python dataset_build/incele.py goster <liste_dosyasi|kuyruk_adi|tum> [n] [--kisa]
      incelenmemis ilk n kaydi gosterir: temizlenmis soru, siklar, cevap, bayraklar,
      aciklama (paragraf numarali). Gorsel bayragi varsa gorsel dosya yollari da basilir.
  python dataset_build/incele.py ok <id> [<id> ...]
  python dataset_build/incele.py karar '<json>' ['<json>' ...]   (tek nesne ya da liste)
  python dataset_build/incele.py durum [parca_dosyasi]

KARAR_DOSYA ortam degiskeni: kararlarin yazilacagi dosya adi
(varsayilan: dataset_v3/inceleme/kararlar.jsonl). Okurken TUM kararlar*.jsonl dikkate alinir.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from v3_uret import (GIRDI, V3, aciklama_temizle, cop_orani, cop_temizle,  # noqa: E402
                     gomulu_kes, soru_temizle, turkce_yap, yapisik_ayir, BAGIMLI)

IN = V3 / "inceleme"
YAZ = IN / os.environ.get("KARAR_DOSYA", "kararlar.jsonl")
ALANLAR = {"id", "karar", "neden", "not", "govde", "siklar", "cevap", "aciklama",
           "aciklama_kes", "aciklama_paragraf", "soru"}
NEDENLER = {"soru_bozuk", "gorsel_gerekli", "cevap_supheli", "eksik_bilgi", "sik_kayip",
            "baglam_gerekli", "tekrar", "diger"}


def kararlar():
    d = {}
    for kf in sorted(IN.glob("kararlar*.jsonl")):
        for l in open(kf, encoding="utf-8"):
            if l.strip():
                k = json.loads(l); d[k["id"]] = k
    return d


def dogrula(k):
    fazla = set(k) - ALANLAR - {"zaman"}
    if fazla: raise SystemExit(f"bilinmeyen alan {fazla} ({k.get('id')})")
    if k["karar"] not in ("ok", "at", "duzelt"): raise SystemExit(f"karar ok/at/duzelt olmali: {k}")
    if k["karar"] == "at" and k.get("neden") not in NEDENLER:
        raise SystemExit(f"neden su degerlerden biri olmali {sorted(NEDENLER)}: {k.get('id')}")
    if "siklar" in k and "cevap" not in k: raise SystemExit(f"siklar verildi ama cevap yok: {k['id']}")
    if "cevap" in k and k["cevap"] not in "ABCDE": raise SystemExit(f"cevap A-E olmali: {k['id']}")
    if "siklar" in k:
        sk = k["siklar"]; harf = list(sk) if isinstance(sk, dict) else [x[0] for x in sk]
        if k["cevap"] not in harf: raise SystemExit(f"cevap siklarda yok: {k['id']}")
    if "aciklama_paragraf" in k:
        v = k["aciklama_paragraf"]
        if isinstance(v, str):
            if not re.fullmatch(r"\d+-\d*", v):
                raise SystemExit(f"aciklama_paragraf sayi ya da 'a-b'/'a-' araligi olmali: {k['id']}")
        elif not isinstance(v, int):
            raise SystemExit(f"aciklama_paragraf sayi ya da 'a-b'/'a-' araligi olmali: {k['id']}")
    if "aciklama_kes" in k:
        acik = ACIK.get(k["id"])
        if acik is not None and k["aciklama_kes"] not in acik:
            raise SystemExit(f"aciklama_kes metni aciklamada bulunamadi: {k['id']}")


ACIK = {}


def yaz(ks):
    with open(YAZ, "a", encoding="utf-8") as f:
        for k in ks:
            dogrula(k)
            k["zaman"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            f.write(json.dumps(k, ensure_ascii=False) + "\n")


def kayitlar():
    return {json.loads(l)["id"]: json.loads(l) for l in open(GIRDI, encoding="utf-8")}


def hazirla(r):
    u0 = r["messages"][0]["content"]; a0 = r["messages"][1]["content"]
    m = re.search(r"<think>\n?(.*?)\n?</think>\s*Doğru cevap:\s*([A-E])\s*$", a0, re.S)
    soru, esleme, onarim, sorun, sinav, govde, siklar = soru_temizle(u0)
    elle = bool((r.get("meta") or {}).get("onarim"))
    # SIRA ONEMLI: once Turkcelestir, sonra yapisik ayir (v3_uret.main ile birebir ayni).
    # Ters sirada sozluk ASCII kelimeyi bulamiyor ve sahte bolme yapiyor: yaklasik -> "ya klasik"
    acik = aciklama_temizle(m.group(1), ayir=False); kes = ""
    acik = turkce_yap(acik, vurgu_kucult=True) if elle else yapisik_ayir(turkce_yap(acik, temkinli=True))
    if not elle:
        acik, kes = gomulu_kes(acik); acik, _ = cop_temizle(acik)
    return dict(govde=turkce_yap(govde, temkinli=True), siklar=siklar, h0=m.group(2), esleme=esleme,
                onarim=onarim, sorun=sorun, acik=acik, kesilen=kes, elle=elle)


def idler(ad):
    p = Path(ad)
    if p.exists(): return [l.strip() for l in open(p) if l.strip()]
    if ad == "tum": return list(kayitlar())
    return json.load(open(IN / "kuyruk.json", encoding="utf-8")).get(ad, [])


def goster(ad, n, kisa=False):
    R = kayitlar(); K = kararlar(); ids = idler(ad)
    gor = {g["id"]: g for g in json.load(open(IN / "soruda_gorsel.json", encoding="utf-8"))}
    kalan = [i for i in ids if i not in K]
    print(f"# {ad}: {len(ids)} kayit | {len(ids) - len(kalan)} incelendi | {len(kalan)} kaldi\n")
    for i in kalan[:n]:
        r = R[i]; h = hazirla(r)
        yeni = h["esleme"].get(h["h0"])
        bay = []
        if yeni is None: bay.append("CEVAP_SIKKI_KAYIP")
        if BAGIMLI.search(h["govde"]): bay.append("ONCEKI_SORUYA_BAGLI")
        if len(h["siklar"]) < 5: bay.append(f"SIK_SAYISI={len(h['siklar'])}")
        if i in gor: bay.append("SORUDA_GORSEL")
        if h["kesilen"]: bay.append(f"GOMULU_SORU_KESILDI({len(h['kesilen'])}kr)")
        if cop_orani(h["acik"])[0] > .15: bay.append("ACIKLAMA_BOZUK")
        if cop_orani(h["govde"])[0] > .12: bay.append("SORU_BOZUK")
        if h["elle"]: bay.append("ELLE_ONARILMIS")
        print(f"=== {i} | {r['meta'].get('source_pdf','').strip()} s.{r['meta'].get('pages')}")
        if h["onarim"] or h["sorun"] or bay:
            print(f"    onarim={h['onarim']} sorun={h['sorun']} {' '.join(bay)}")
        print("GOVDE:", h["govde"].replace("\n", " / "))
        for L, t in h["siklar"]:
            print(f"  {L}) {t}")
        print(f"CEVAP: {h['h0']}" + (f" -> {yeni}" if yeni and yeni != h["h0"] else "")
              + f"   [aciklama {len(h['acik'])} kr]")
        ACIK[i] = h["acik"]
        ps = [p for p in h["acik"].split("\n") if p.strip()]
        top = 0
        sinir = 700 if (kisa and not bay) else 2500      # bayraksiz kayitlarda kisa gosterim
        for k, p in enumerate(ps):
            if top > sinir:
                print(f"  ... (+{len(ps) - k} paragraf, {sum(map(len, ps[k:]))} kr daha — aciklama_paragraf ile kes: 3 = ilk 3, '2-' = [2] ve sonrasi, '1-4' = [1]..[4])")
                break
            kes = 300 if sinir == 700 else 500
            print(f"  [{k}] {p[:kes]}" + (" ..." if len(p) > kes else ""))
            top += min(len(p), kes)
        if h["kesilen"]:
            print("  KESILEN(ilk 200):", " ".join(h["kesilen"][:200].split()))
        if i in gor:
            src = r["meta"]["source_pdf"]
            d = next((p for p in (Path(__file__).resolve().parent.parent / "cikti").glob(
                str(Path(src).parent) + "/*") if p.name.strip() == Path(src).name.strip()), None)
            for k, g in enumerate(gor[i]["gorsel"]):
                yerel = sorted((IN / "gorseller").glob(f"{i}_{k}.*"))
                print(f"  GORSEL({g[1]}): {yerel[0] if yerel else f'{d}/auto/{g[2]}'}")
        print()


def main():
    a = sys.argv[1:]
    if a[0] == "goster":
        sayi = next((int(x) for x in a[2:] if x.isdigit()), 20)
        goster(a[1], sayi, "--kisa" in a)
    elif a[0] == "ok":
        yaz([{"id": i, "karar": "ok"} for i in a[1:]]); print(f"ok: {len(a) - 1}")
    elif a[0] == "karar":
        ks = []
        for s in a[1:]:
            k = json.loads(s); ks += k if isinstance(k, list) else [k]
        R = kayitlar()
        for k in ks:
            if "aciklama_kes" in k and k["id"] in R: ACIK[k["id"]] = hazirla(R[k["id"]])["acik"]
        yaz(ks); print(f"yazildi: {len(ks)}")
    elif a[0] == "durum":
        from collections import Counter
        K = kararlar()
        if len(a) > 1:
            ids = idler(a[1]); print(f"{a[1]}: {sum(i in K for i in ids)}/{len(ids)}")
        print(len(K), Counter(k["karar"] for k in K.values()))


if __name__ == "__main__":
    main()

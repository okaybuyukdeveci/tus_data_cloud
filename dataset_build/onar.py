#!/usr/bin/env python3
"""Elle onarilan kayitlari dataset_v2/onarilmis'e yazar.

Girdi: stdin'den JSON listesi
  [{"id": "...", "cevap": "B", "gerekce": "...",
    "soru": "(istege bagli) duzeltilmis soru metni",
    "cekince": "(istege bagli)"}]
"""
import json, sys, hashlib, pathlib, datetime, time
KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "dataset_build"))
from build_sft import soru_anahtari
aid = lambda t: hashlib.sha256(soru_anahtari(t).encode()).hexdigest()[:16]
D = KOK / "dataset_v2"

def main():
    istek = json.load(sys.stdin)

    # gece.sh dataseti her 30 dakikada yeniden uretiyor; dosya yazilirken
    # okursak son satir yarim kalabilir ya da kayit henuz yazilmamis olabilir.
    # Bu yuzden bozuk satirlari atla ve eksik id varsa yazma bitene kadar bekle.
    def oku():
        k = {}
        for l in (D / "flagged/tus_mcq_flagged.jsonl").open(encoding="utf-8"):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue          # yarim yazilmis son satir
            if "soru" in r: k[r["id"]] = r
        return k

    for deneme in range(4):
        kayit = oku()
        eksik = [it["id"] for it in istek if it["id"] not in kayit]
        if not eksik: break
        print(f"  [bekle] {len(eksik)} kayit henuz yok (yeniden uretim suruyor?), "
              f"20 sn sonra yeniden denenecek: {eksik[:3]}", file=sys.stderr)
        time.sleep(20)
    else:
        raise SystemExit(f"HATA: bu id'ler flagged dosyasinda bulunamadi: {eksik}")
    hedef = D / "onarilmis/tus_mcq_onarilmis.jsonl"
    n = 0
    with hedef.open("a", encoding="utf-8") as f:
        for it in istek:
            r = kayit[it["id"]]
            yeni = it.get("soru")
            soru = yeni or r["soru"]
            tur = "aciklama_yazildi" + ("+ocr_duzeltildi" if yeni else "")
            if it["cevap"] != r.get("cevap"): tur += "+anahtar_duzeltildi"
            f.write(json.dumps({"id": it["id"],
                "messages": [{"role": "user", "content": soru},
                             {"role": "assistant",
                              "content": f"<think>\n{it['gerekce']}\n</think>\n\n"
                                         f"Doğru cevap: {it['cevap']}"}],
                "meta": {**r["meta"], "anahtar_id": aid(r["soru"]),
                    "onarim": {"tur": tur, "kaynak": "ai_uretildi", "guven": "yuksek",
                        "cevap_dogrulandi": True, "kitap_anahtari_ham": r.get("cevap"),
                        "cevap_adaylari": r["meta"].get("cevap_adaylari"),
                        "cekince": it.get("cekince"),
                        "soru_degistirildi": bool(yeni),
                        "orijinal_soru": r["soru"] if yeni else None,
                        "orijinal_sorun": r["sorunlar"],
                        "tarih": datetime.date.today().isoformat()}}},
                ensure_ascii=False) + "\n")
            n += 1
    print(f"yazildi {n} | onarilmis toplam "
          f"{sum(1 for _ in hedef.open(encoding='utf-8'))}")

if __name__ == "__main__":
    main()

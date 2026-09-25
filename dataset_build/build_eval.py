#!/usr/bin/env python3
"""Degerlendirme (eval) ayrimini uretir.

Kural: eval kayitlari EGITIME GIRMEZ.
  - kaynak havuz: flagged icinde TEK sorunu 'aciklama_kisa' olan, cevabi GUVENILIR
    (coklu_anahtar isareti yok) kayitlar -> cevap var, aciklama yok
  - SFT'de ayni soru varsa (soru_anahtari ile) ELENIR  -> sizinti yok
  - elle onarilmis / itiraz / kullanilamaz olanlar ELENIR -> cakisma yok
  - secim deterministiktir (anahtar_id siralamasi), her kosuda ayni kalir
"""
import json, hashlib, sys, pathlib, argparse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_sft import soru_anahtari

KOK = pathlib.Path(__file__).resolve().parent.parent
aid = lambda t: hashlib.sha256(soru_anahtari(t).encode()).hexdigest()[:16]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(KOK / "dataset_v2"))
    ap.add_argument("--n", type=int, default=500, help="aciklamasiz eval hedefi")
    ap.add_argument("--sft-holdout", type=int, default=400,
                    help="SFT'den ayrilacak (aciklamali) degerlendirme kaydi sayisi")
    a = ap.parse_args()
    D = pathlib.Path(a.dataset)

    sft = {aid(json.loads(l)["messages"][0]["content"])
           for l in (D / "sft/tus_mcq.jsonl").open(encoding="utf-8")}

    dokunulmus = set()
    for ad in ["onarilmis/tus_mcq_onarilmis.jsonl", "flagged/itiraz.jsonl",
               "flagged/kullanilamaz.jsonl"]:
        p = D / ad
        if not p.exists(): continue
        for l in p.open(encoding="utf-8"):
            r = json.loads(l)
            t = r["messages"][0]["content"] if "messages" in r else r["soru"]
            dokunulmus.add(aid(t))
            o = r.get("meta", {}).get("onarim", {}).get("orijinal_soru")
            if o: dokunulmus.add(aid(o))

    aday, elenen = [], []
    gorulen = set()
    for l in (D / "flagged/tus_mcq_flagged.jsonl").open(encoding="utf-8"):
        r = json.loads(l)
        if "soru" not in r:          # celiskili_cevap kayitlari messages bicimli
            continue
        s = sorted(x.split("(")[0] for x in r["sorunlar"])
        k = aid(r["soru"])
        if s != ["aciklama_kisa"] or not r.get("cevap"):
            continue
        if len(r["meta"].get("cevap_adaylari") or []) > 1:
            elenen.append((k, "coklu_anahtar")); continue
        if k in sft:        elenen.append((k, "sft_sizintisi")); continue
        if k in dokunulmus: elenen.append((k, "elle_onarildi")); continue
        if k in gorulen:    continue
        gorulen.add(k)
        r["meta"]["anahtar_id"] = k
        aday.append(r)

    aday.sort(key=lambda r: r["meta"]["anahtar_id"])
    secilen = aday[:a.n]

    (D / "eval").mkdir(exist_ok=True)
    with (D / "eval/tus_mcq_eval.jsonl").open("w", encoding="utf-8") as f:
        for r in secilen:
            f.write(json.dumps({"id": r["id"], "soru": r["soru"],
                "dogru_cevap": r["cevap"],
                "meta": {**r["meta"], "kullanim": "degerlendirme",
                         "not": "aciklamasiz - egitim setinde ve onarim havuzunda YOK"}},
                ensure_ascii=False) + "\n")
    with (D / "flagged/eval_elenen.jsonl").open("w", encoding="utf-8") as f:
        for k, n in elenen:
            f.write(json.dumps({"anahtar_id": k, "sebep": n}, ensure_ascii=False) + "\n")

    print(f"eval aday havuzu : {len(aday)}")
    print(f"eval secilen     : {len(secilen)}  -> {D}/eval/tus_mcq_eval.jsonl")
    from collections import Counter
    print(f"elenen           : {len(elenen)} {dict(Counter(n for _, n in elenen))}")

    # --- SFT'den aciklamali holdout: egitimden FIZIKSEL olarak cikarilir ---
    sft_yol = D / "sft/tus_mcq.jsonl"
    kayitlar = [json.loads(l) for l in sft_yol.open(encoding="utf-8")]
    eval_k = {r["meta"]["anahtar_id"] for r in secilen}
    # deterministik: anahtar_id'nin kendi hash'ine gore sirala, bastan al.
    # Yeniden uretimde ayni kayitlar secilir; grup dengesi icin gruba gore tur at.
    from collections import defaultdict
    gruplu = defaultdict(list)
    for r in kayitlar:
        k = aid(r["messages"][0]["content"])
        r["meta"]["anahtar_id"] = k
        if k in eval_k:      # aciklamasiz eval ile cakisma -> egitimde kalmasin
            continue
        gruplu[r["meta"].get("group") or "?"].append((k, r))
    for g in gruplu: gruplu[g].sort(key=lambda x: x[0])
    toplam = sum(len(v) for v in gruplu.values())
    holdout, pay = [], {}
    for g, v in gruplu.items():
        pay[g] = max(1, round(a.sft_holdout * len(v) / toplam)) if toplam else 0
        holdout += [r for _, r in v[:pay[g]]]
    holdout = holdout[:a.sft_holdout]
    hk = {r["meta"]["anahtar_id"] for r in holdout}

    with (D / "eval/tus_mcq_eval_aciklamali.jsonl").open("w", encoding="utf-8") as f:
        for r in holdout:
            f.write(json.dumps({**r, "meta": {**r["meta"], "kullanim": "degerlendirme",
                    "not": "aciklamali holdout - SFT'den cikarildi"}}, ensure_ascii=False) + "\n")

    # DIKKAT: sft/tus_mcq.jsonl build_sft'nin ham ciktisidir, DEGISTIRILMEZ.
    # Aksi halde her kosuda holdout yeniden kesilip dosya kuculurdu (idempotent degil).
    kalan = [r for r in kayitlar if aid(r["messages"][0]["content"]) not in hk
             and aid(r["messages"][0]["content"]) not in eval_k]

    print(f"SFT holdout      : {len(holdout)} -> {D}/eval/tus_mcq_eval_aciklamali.jsonl")
    print(f"SFT ham={len(kayitlar)} -> egitime uygun={len(kalan)} (eval+holdout cikarildi)")

    # --- nihai egitim dosyasi: otomatik SFT + elle onarilmis (yinelenenler atilir) ---
    otomatik = {aid(r["messages"][0]["content"]) for r in kalan}
    dislanan = set()
    for ad in ["flagged/itiraz.jsonl", "flagged/kullanilamaz.jsonl"]:
        q = D / ad
        if q.exists():
            for l in q.open(encoding="utf-8"):
                dislanan.add(aid(json.loads(l)["soru"]))
    onar_yol = D / "onarilmis/tus_mcq_onarilmis.jsonl"
    onar, yinelenen = [], 0
    if onar_yol.exists():
        gor = set()
        for l in onar_yol.open(encoding="utf-8"):
            r = json.loads(l); k = aid(r["messages"][0]["content"])
            if k in otomatik or k in gor:   # kitabin kendi aciklamali surumu tercih edilir
                yinelenen += 1; continue
            gor.add(k); onar.append(r)
    egitim = [r for r in kalan if aid(r["messages"][0]["content"]) not in dislanan] + onar
    with (D / "sft/tus_mcq_egitim.jsonl").open("w", encoding="utf-8") as f:
        for r in egitim:
            f.write(json.dumps({"id": r["id"], "messages": r["messages"],
                                "meta": r["meta"]}, ensure_ascii=False) + "\n")
    print(f"NIHAI EGITIM     : {len(egitim)} = {len(kalan)-len(dislanan & otomatik)} otomatik "
          f"+ {len(onar)} elle onarilmis  (yinelenen {yinelenen} atildi)")
    print(f"                   -> {D}/sft/tus_mcq_egitim.jsonl")

if __name__ == "__main__":
    main()

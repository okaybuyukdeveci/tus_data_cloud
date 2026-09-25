"""SFT v3: v2 egitim setinden temiz, dogrulanmis son surumu uretir.

Asamalar
  1) otomatik temizlik (v3_temizlik): HTML/LaTeX, sik ayristirma ve onarim,
     soru numarasi ve sinav etiketi temizligi, aciklamada sayfa basligi temizligi
  2) bayraklar: elle incelenmesi gerekenler (inceleme kuyrugu)
  3) elle kararlar (dataset_v3/inceleme/kararlar.jsonl) uygulanir
  4) cikti: dataset_v3/sft/tus_mcq_egitim.jsonl + elenen/ + rapor

  python dataset_build/v3_uret.py            # uret + rapor
Kararlar dosyasi satir bicimi:
  {"id":..., "karar":"ok"}                                  incelendi, sorun yok
  {"id":..., "karar":"at", "neden":"..."}                   egitimden cikar
  {"id":..., "karar":"duzelt", "soru":..., "cevap":"C",     alanlardan verilenler
   "aciklama":..., "not":"..."}                             ezilir
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from v3_temizlik import metin_temizle, sik_onar, soru_yaz, turkce_yap, cop_temizle, cop_orani, yapisik_ayir  # noqa: E402

KOK = Path(__file__).resolve().parent.parent
GIRDI = KOK / "dataset_v2/sft/tus_mcq_egitim.jsonl"
V3 = KOK / "dataset_v3"
KARAR = V3 / "inceleme/kararlar.jsonl"
GORSEL = V3 / "inceleme/soruda_gorsel.json"

AYLAR = r"(?:Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık|Nis|Eyl)"
SINAV = re.compile(r"\s*\((?=[^()]{0,60}\))[^()]*?(?:" + AYLAR + r"|TTB|TUS|Orijinal)[^()]*?(?:\d{2,4}|Orijinal)[^()]*\)", re.I)
SORU_NO = re.compile(r"^\s*\d{1,3}\s*[\.\)]\s*|^\s*\d{1,3}\s+(?=[A-ZÇĞİÖŞÜ])|^\s*\.\s*")
BAGIMLI = re.compile(
    r"bir\s*önceki\s*\(?\s*\d{0,3}\s*(?:numaral[ıi])?\s*\)?\s*soru|önceki\s*soru|"
    r"\(?\s*\d{1,3}\s*numaral[ıi]\s*\)?\s*sorudaki|yukarıdaki\s*soruda|"
    r"\d{1,3}\s*[\.\-–]?\s*(?:ve|-|–|,)\s*\d{1,3}\s*\.?\s*soruları|"
    r"(?:ilk|ikinci|birinci)\s*soruda\s*(?:tanımlanan|verilen|anlatılan)", re.I)
# aciklamaya karismis sayfa basligi / altligi: "ANATOMI 449", "446 TÜM TUS SORULARI"
SAYFA = re.compile(r"^\s*(?:ANATOM[İI]|G E N E L|TÜM TUS SORULARI)\s*\d{1,4}\s*$")
CEVAP_ATIF = re.compile(r"(?:doğru\s*(?:cevap|yanıt|seçenek|şık)|cevap)\s*[:\-–—]?\s*\(?([A-E])\)?(?![a-zçğıöşü])", re.I)


SIKBLOK = re.compile(r"(?:^|[\s\n])\(?A\s?\)\s*\S[^\n]{0,200}?[\s\n]\(?B\s?\)\s*\S[^\n]{0,200}?[\s\n]\(?[Cc]\s?\)", re.S)
CEVSAT = re.compile(r"(?:^|(?<=[\s\n]))\d{1,3}\s*[-–—]\s*[A-E](?=[\s\n]|$)")


def gomulu_kes(t):
    """Aciklamaya karismis sonraki soruyu (govde+siklar+'31 - D') ve sonrasini kes.
    Donus: (kalan, kesilen) ; kesilen bos ise degisiklik yok."""
    adaylar = []
    m = SIKBLOK.search(t)
    if m: adaylar.append(m.start())
    c = CEVSAT.search(t)
    if c: adaylar.append(c.start())
    if not adaylar: return t, ""
    kes = min(adaylar)
    # geriye dogru: gomulu sorunun govdesi (soru isareti / 'hangisi' iceren son 2 satir)
    onceki = t[:kes]
    satirlar = onceki.split("\n")
    bas = len(onceki)
    for k in range(len(satirlar) - 1, max(len(satirlar) - 9, -1), -1):
        sat = satirlar[k]
        if re.match(r"\s*\(?[A-Ea-e0-9]\s?\)|\s*[A-E][A-ZÇĞİÖŞÜ]", sat) or (len(sat) < 70 and k > len(satirlar) - 7
                                                                          and not re.search(r"[.?:]\s*$", sat)):
            bas = len("\n".join(satirlar[:k]))      # sik satiri ya da kisa satir: gomulu soruya ait
            continue
        if re.search(r"\?|hangisi|aşağıdaki|asagidaki", sat, re.I):
            bas = len("\n".join(satirlar[:k]))
            # ayni satirdaki onceki cumle bizim aciklamamiz olabilir: soru numarasi/buyuk harfle baslayan
            # gomulu govdeyi satir icinde ara ("...yapılır. 27Malign melanom ...")
            ic = re.search(r"(?:(?<=[.!:;])\s*|^)\s*\d{0,3}\s*[A-ZÇĞİÖŞÜ][^.?]{5,300}\?", sat)
            if ic and ic.start() > 0:
                bas = len("\n".join(satirlar[:k])) + (1 if k else 0) + ic.start()
            break
    # soru numarasi yapisik ("27Malign") -> numaradan kes
    kalan = t[:bas].rstrip()
    kalan = re.sub(r"[\s\n]*\d{1,3}\s*$", "", kalan)
    return kalan.rstrip(), t[len(kalan):].strip()


def aciklama_temizle(t, ayir=True):
    """ayir=False: yapisik kelime ayirmayi atla (elle yazilmis aciklamalar OCR'dan gecmedi)."""
    t = metin_temizle(t)
    if ayir: t = yapisik_ayir(t)
    satir = [s for s in t.split("\n") if not SAYFA.match(s)]
    t = "\n".join(satir)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def soru_temizle(u):
    """-> (yeni_soru, harf_eslemesi{eski:yeni}, onarimlar, sorunlar, sinav_etiketi)"""
    u = yapisik_ayir(turkce_yap(metin_temizle(u), temkinli=True))
    sinav = [m.group(0).strip() for m in SINAV.finditer(u)]
    u = SINAV.sub("", u)
    u = SORU_NO.sub("", u, count=1)
    govde, siklar, onarim, sorun = sik_onar(u)
    esleme = {h: h for h, _ in siklar}
    eksik = [s for s in sorun if s.startswith("eksik:")]
    if siklar and eksik:
        # metni kaybolmus sik(lar): kalanlari sirayla yeniden harfle
        yeni = []
        for k, (h, t) in enumerate(siklar):
            esleme[h] = "ABCDE"[k]
            yeni.append(("ABCDE"[k], t))
        if [h for h, _ in siklar] != [h for h, _ in yeni]:
            onarim.append("yeniden_harflendi:" + "".join(h for h, _ in siklar))
        siklar = yeni
    return soru_yaz(govde, siklar) if siklar else u, esleme, onarim, sorun, sinav, govde, siklar


def main():
    kayitlar = [json.loads(l) for l in open(GIRDI, encoding="utf-8")]
    gorsel = {g["id"]: g for g in json.load(open(GORSEL, encoding="utf-8"))} if GORSEL.exists() else {}
    kararlar = {}
    for kf in sorted(KARAR.parent.glob("kararlar*.jsonl")):
        for l in open(kf, encoding="utf-8"):
            if l.strip():
                k = json.loads(l)
                if k["id"] not in kararlar or k.get("zaman", "") >= kararlar[k["id"]].get("zaman", ""):
                    kararlar[k["id"]] = k   # en son karar gecerli
    cikti, elenen, kuyruk = [], collections.defaultdict(list), collections.defaultdict(list)
    say = collections.Counter()
    for r in kayitlar:
        u0 = r["messages"][0]["content"]; a0 = r["messages"][1]["content"]
        m = re.search(r"<think>\n?(.*?)\n?</think>\s*Doğru cevap:\s*([A-E])\s*$", a0, re.S)
        acik0, harf0 = m.group(1), m.group(2)
        soru, esleme, onarim, sorun, sinav, govde, siklar = soru_temizle(u0)
        elle = bool((r.get("meta") or {}).get("onarim"))
        acik = aciklama_temizle(acik0, ayir=False)
        # Turkcelestirme ONCE: sozluk Turkce karakterli, ASCII metinde yapisik ayirici sahte bolme yapiyor
        acik = turkce_yap(acik, vurgu_kucult=True) if elle else yapisik_ayir(turkce_yap(acik, temkinli=True))
        soru = turkce_yap(soru, temkinli=True)
        bayrak = []
        kesilen = ""
        if not (r.get("meta") or {}).get("onarim"):
            acik, kesilen = gomulu_kes(acik)
            if kesilen: bayrak.append("gomulu_soru_kesildi")
            acik, atilan = cop_temizle(acik)
            if atilan: bayrak.append("cop_cumle_atildi")
        if harf0 not in esleme: bayrak.append("cevap_sikki_kayip")
        harf = esleme.get(harf0, harf0)
        if BAGIMLI.search(govde): bayrak.append("onceki_soruya_bagli")
        if r["id"] in gorsel: bayrak.append("soruda_gorsel")
        if any(o.split(":")[1] in ("parantezsiz", "sahipsiz_parantez", "satir_basi", "ocr_rakam", "tekrar_harf(D)", "yapisik_harf", "satir")
               for o in onarim if ":" in o) or any("coklu" in s for s in sorun):
            bayrak.append("sik_onarimi")
        if any(o.startswith("yeniden_harflendi") for o in onarim): bayrak.append("sik_kayip_yeniden_harf")
        if len(siklar) < 4: bayrak.append("sik_sayisi_az")
        if len(acik) > 2500: bayrak.append("aciklama_uzun")
        if len(acik) < 60: bayrak.append("aciklama_kisa")
        if cop_orani(acik)[0] > 0.15: bayrak.append("aciklama_bozuk")
        if cop_orani(govde)[0] > 0.12: bayrak.append("soru_bozuk")
        atif = {x.group(1).upper() for x in CEVAP_ATIF.finditer(acik)}
        if atif and harf0 not in atif: bayrak.append("aciklama_harf_celiskisi")
        if re.search(r"Doğru cevap", acik): bayrak.append("aciklamada_cevap_satiri")

        k = kararlar.get(r["id"])
        if k and k["karar"] == "ok" and any(b in bayrak for b in ("cevap_sikki_kayip", "onceki_soruya_bagli", "sik_sayisi_az")):
            k = None      # 'ok' otomatik eleme gerekcesini ezemez; duzelt ya da at gerekir
        durum = "otomatik"
        if k:
            durum = "incelendi"
            if k["karar"] == "at":
                elenen[k.get("neden", "elle_elendi")].append({**r, "v3_neden": k.get("not", "")}); say["elle_at"] += 1
                continue
            if k["karar"] == "duzelt":
                if "siklar" in k and "cevap" not in k:
                    raise SystemExit(f"siklar verilmis ama cevap yok: {r['id']}")
                if "siklar" in k:   # {"A": "...", ...} ya da [["A","..."], ...]
                    sk = k["siklar"]; sk = sorted(sk.items()) if isinstance(sk, dict) else sk
                    soru = soru_yaz(k.get("govde", govde), [tuple(x) for x in sk])
                    esleme = {}
                elif "govde" in k:
                    soru = soru_yaz(k["govde"], siklar)
                soru = k.get("soru", soru)
                if "aciklama_paragraf" in k:
                    # int N -> ilk N paragraf | "a-b" / "a-" -> gosterimdeki [a]..[b] araligi (0-tabanli, dahil)
                    ps = [p for p in acik.split("\n") if p.strip()]
                    v = k["aciklama_paragraf"]
                    if isinstance(v, str) and "-" in v:
                        a, _, b = v.partition("-")
                        ps = ps[int(a) if a.strip() else None:(int(b) + 1) if b.strip() else None]
                    else:
                        ps = ps[:int(v)]
                    acik = "\n".join(ps)
                if "aciklama_kes" in k:        # verilen metnin basladigi yerden kes
                    j = acik.find(k["aciklama_kes"])
                    if j < 0:
                        j = " ".join(acik.split()).find(" ".join(k["aciklama_kes"].split()))
                        if j >= 0: acik = " ".join(acik.split())[:j].rstrip()
                        else: say["kes_bulunamadi"] += 1; kuyruk["kes_bulunamadi"].append(r["id"])
                    else:
                        acik = acik[:j].rstrip()
                acik = k.get("aciklama", acik); harf = k.get("cevap", harf)
                say["elle_duzelt"] += 1
        else:
            # otomatik elenenler (elle karar yoksa)
            oto = [b for b in bayrak if b in ("cevap_sikki_kayip", "onceki_soruya_bagli", "sik_sayisi_az")]
            if oto:
                elenen[oto[0]].append(r); say["oto_at:" + oto[0]] += 1
                continue
            for b in bayrak: kuyruk[b].append(r["id"])
        meta = dict(r.get("meta") or {})
        meta["v3"] = {"onarim": onarim, "bayrak": bayrak, "durum": durum, "sinav_etiketi": sinav,
                      "harf_esleme": {k_: v for k_, v in esleme.items() if k_ != v} or None,
                      "kesilen_uzunluk": len(kesilen) or None,
                      "not": (k or {}).get("not")}
        cikti.append({"id": r["id"], "messages": [
            {"role": "user", "content": soru},
            {"role": "assistant", "content": f"<think>\n{acik}\n</think>\n\nDoğru cevap: {harf}"}],
            "meta": meta})
    # temizlik sonrasi ayni hale gelen sorular: incelenmis + uzun aciklamali olan kalir
    import hashlib
    gr = collections.defaultdict(list)
    for r in cikti:
        gr[hashlib.md5(" ".join(r["messages"][0]["content"].split()).lower().encode()).hexdigest()].append(r)
    tut = []
    for rs in gr.values():
        rs.sort(key=lambda r: (r["meta"]["v3"]["durum"] == "incelendi", len(r["messages"][1]["content"])), reverse=True)
        tut.append(rs[0])
        for r in rs[1:]:
            elenen["tekrar"].append(r); say["tekrar_atildi"] += 1
    sira = {r["id"]: k for k, r in enumerate(cikti)}
    cikti = sorted(tut, key=lambda r: sira[r["id"]])
    (V3 / "sft").mkdir(parents=True, exist_ok=True); (V3 / "elenen").mkdir(exist_ok=True)
    with open(V3 / "sft/tus_mcq_egitim.jsonl", "w", encoding="utf-8") as f:
        for r in cikti: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    for n, rs in elenen.items():
        with open(V3 / f"elenen/{n}.jsonl", "w", encoding="utf-8") as f:
            for r in rs: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump({k: v for k, v in kuyruk.items()}, open(V3 / "inceleme/kuyruk.json", "w", encoding="utf-8"),
              ensure_ascii=False)
    print(f"girdi {len(kayitlar)} | egitim {len(cikti)} | elenen {sum(map(len, elenen.values()))}")
    print("elenen:", {k: len(v) for k, v in elenen.items()})
    print("say:", dict(say))
    print("inceleme kuyrugu:", {k: len(v) for k, v in sorted(kuyruk.items(), key=lambda x: -len(x[1]))})
    print("elle karar:", len(kararlar))


if __name__ == "__main__":
    main()

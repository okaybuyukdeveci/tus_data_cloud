"""Drive'a yuklenecek paketi kurar: ders bazli hiyerarsi + SFT dataset + kod/log.

Kaynak PDF'ler pakete GIRMEZ (Drive'da Textbook/TUS altinda zaten var).
Her belge icin MinerU ciktisi: .md, _content_list.json, _middle.json, _model.json, images/.
_origin/_layout/_span PDF'leri alinmaz.

Dosyalar APFS klonu (cp -c) ile kopyalanir: ek disk yeri kaplamaz, kaynak/ ve cikti/ degismez.

  python dataset_build/drive_paket.py            # kuru calisma: esleme + agac
  python dataset_build/drive_paket.py --uygula   # paketi kur
"""
import csv, collections, hashlib, json, re, shutil, subprocess, sys, unicodedata
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KAYNAK, CIKTI, DS = KOK / "kaynak", KOK / "cikti", KOK / "dataset_v2"
HEDEF = Path.home() / "Desktop" / "TUS_Veriseti"
DRIVE_KOK = "Textbook/TUS"

TEMEL = ["Anatomi", "Fizyoloji-Histoloji-Embriyoloji", "Biyokimya", "Mikrobiyoloji", "Patoloji", "Farmakoloji"]
KLINIK = ["Dahiliye", "Pediatri", "Genel Cerrahi", "Kadın Doğum", "Küçük Stajlar"]
DERS_ANAHTAR = [  # (desen, ders) - ilk eslesen kazanir
    (r"anatomi", "Anatomi"), (r"biyokimya", "Biyokimya"), (r"dahil", "Dahiliye"),
    (r"farmakoloji", "Farmakoloji"), (r"fizyoloji|histoloji|embriyoloji", "Fizyoloji-Histoloji-Embriyoloji"),
    (r"cerrahi", "Genel Cerrahi"), (r"kad[ıi]n", "Kadın Doğum"), (r"sta[jl]|ortopedi", "Küçük Stajlar"),
    (r"mikrobiyoloji", "Mikrobiyoloji"), (r"patoloji", "Patoloji"),
    (r"pediatri|yenido[gğ]an", "Pediatri"),
]
YAYIN = {"tusdata": "Tusdata", "tusem": "Tusem", "tustime": "Tustime", "tusworld": "Tusworld"}


def nfc(s): return unicodedata.normalize("NFC", s)
def temiz(s): return re.sub(r"\s+", " ", nfc(s)).strip(" .-_")


def ders_bul(metin):
    t = nfc(metin).lower().replace("i̇", "i")  # 'İ'.lower() -> 'i' + birlesik nokta
    for desen, ders in DERS_ANAHTAR:
        if re.search(desen, t): return ders
    return None


def bilim(ders): return "Temel_Bilimler" if ders in TEMEL else "Klinik_Bilimler"


def yayinevi(s):
    k = nfc(s).lower().replace("i̇", "i")
    for a, v in YAYIN.items():
        if a.lower() in k: return v
    return None


def donem(klasor):
    yil = re.search(r"(20\d\d)", klasor).group(1)
    return f"{yil}-1_Nisan" if re.search(r"n[iİı]san", nfc(klasor), re.I) else f"{yil}-2_Eylul"


def sinifla(pdf):
    """kaynak PDF -> (goreli hedef klasor, yeni belge adi, kategori, ders, yayinevi)"""
    rel = pdf.relative_to(KAYNAK)
    p = [nfc(x) for x in rel.parts]
    stem = temiz(pdf.stem)
    if p[0] == "Denemeler":
        d = donem(p[1])
        yay = yayinevi(p[2]) if len(p) > 3 else yayinevi(stem)
        ic = "_".join(temiz(x) for x in p[3:-1]) if len(p) > 4 else ""
        ad = f"{yay}_{d.split('_')[0][:4]}-{d.split('_')[1]}_" + (f"{ic}_" if ic else "") + stem
        return Path("1_Denemeler") / d / yay, temiz(ad), "Deneme", "Karma (Temel+Klinik)", yay
    if p[0] == "Açıklamalı TUS Çıkmışları":
        return Path("2_Cikmis_Sorular/Aciklamali_TUS_Cikmislari"), f"TUS {stem}", "Çıkmış Soru", "Karma (Temel+Klinik)", "-"
    if p[0] == "Tüm TUS Soruları (30. Baskı)":
        ders = ders_bul(stem)
        return (Path("2_Cikmis_Sorular/Tum_TUS_Sorulari_30.Baski") / bilim(ders)), f"Tüm TUS Soruları - {stem}", "Çıkmış Soru", ders, "Tüm TUS Soruları"
    if "YDS" in stem:
        return Path("4_Diger"), f"Tusem - {stem}", "Diğer", "YDS İngilizce", "Tusem"
    if p[0] == "Soru Kitapları" and len(p) > 2:  # Derece Kampi
        return Path("3_Ders_Kitaplari_ve_Soru_Bankalari/Karma_Temel+Klinik"), f"Derece Kampı - {stem}", "Soru Bankası", "Karma (Temel+Klinik)", "Derece Kampı"
    if p[0] == "Tusdata":
        ders, yay = p[1], "Tusdata"
    else:
        ders = ders_bul(stem)
        yay = {"Soru Kitapları": "Soru Kitabı"}.get(p[0], p[0])
    if ders is None:
        raise ValueError(f"ders bulunamadi: {rel}")
    stem = re.sub(rf"^{yay}\s*-\s*", "", stem)  # 'Tusdata - Tusdata - X' olmasin
    return (Path("3_Ders_Kitaplari_ve_Soru_Bankalari") / bilim(ders) / ders), f"{yay} - {stem}", "Ders Kitabı / Soru Bankası", ders, yay


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def cikti_klasoru(pdf):
    parts = list(pdf.relative_to(KAYNAK).parent.parts)
    if parts and parts[0] == "Tusdata": parts = parts[1:]
    return CIKTI.joinpath(*parts) / pdf.stem / "auto"


def main():
    uygula = "--uygula" in sys.argv
    pdfs = sorted(KAYNAK.rglob("*.pdf"))
    # yinelenen PDF'ler: ayni icerikten ilk (tercihen '(1)' olmayan, Tusdata olan) tutulur
    gruplar = collections.defaultdict(list)
    for p in pdfs: gruplar[md5(p)].append(p)
    kopya = {}
    for ps in gruplar.values():
        if len(ps) > 1:
            ps = sorted(ps, key=lambda x: ("(1)" in x.name, x.relative_to(KAYNAK).parts[0] != "Tusdata", str(x)))
            for k in ps[1:]: kopya[k] = ps[0]

    # SFT'ye giren soru sayisi (meta.source_pdf = cikti goreli yolu)
    soru = collections.Counter()
    for l in open(DS / "sft/tus_mcq_egitim.jsonl", encoding="utf-8"):
        soru[nfc((json.loads(l).get("meta") or {}).get("source_pdf", "")).strip()] += 1

    satirlar, gorulen = [], {}
    for p in pdfs:
        klasor, ad, kat, ders, yay = sinifla(p)
        src = cikti_klasoru(p)
        srel = nfc(str(src.parent.relative_to(CIKTI))).strip()
        drive = f"{DRIVE_KOK}/{nfc(str(p.relative_to(KAYNAK)))}"
        if p in kopya:
            satirlar.append(dict(drive_pdf=drive, paket_yolu="", kategori=kat, ders=ders, yayinevi=yay,
                                 egitim_soru=0, not_=f"birebir kopya: {DRIVE_KOK}/{nfc(str(kopya[p].relative_to(KAYNAK)))}"))
            continue
        hedef = klasor / ad
        if str(hedef) in gorulen:
            raise SystemExit(f"AD CAKISMASI: {hedef}\n  {gorulen[str(hedef)]}\n  {p}")
        gorulen[str(hedef)] = p
        if not src.is_dir():
            raise SystemExit(f"cikti yok: {src}")
        satirlar.append(dict(drive_pdf=drive, paket_yolu=f"1_MinerU_Cikti/{hedef}", kategori=kat, ders=ders,
                             yayinevi=yay, egitim_soru=soru.get(srel, 0), not_="", _src=src, _ad=ad))

    # --- ozet / agac
    agac = collections.Counter(str(Path(r["paket_yolu"]).parent) for r in satirlar if r["paket_yolu"])
    for k in sorted(agac): print(f"{agac[k]:4d}  {k}")
    print(f"\nbelge: {sum(1 for r in satirlar if r['paket_yolu'])} paketlenecek, {len(kopya)} kopya atlandi")
    print(f"egitim sorusu eslenen: {sum(r['egitim_soru'] for r in satirlar)} / {sum(soru.values())}")
    if not uygula:
        print("\n(kuru calisma - --uygula ile kurulur)")
        return

    if HEDEF.exists(): raise SystemExit(f"hedef zaten var: {HEDEF}")
    tut = ("_content_list.json", "_middle.json", "_model.json", ".md")
    for r in satirlar:
        if not r["paket_yolu"]: continue
        dst = HEDEF / r["paket_yolu"]; dst.mkdir(parents=True)
        src, stem = r["_src"], r["_src"].parent.name
        for suf in tut:
            f = src / f"{stem}{suf}"
            if not f.exists(): raise SystemExit(f"eksik: {f}")
            subprocess.run(["cp", "-c", str(f), str(dst / f"{r['_ad']}{suf}")], check=True)
        if (src / "images").is_dir():
            subprocess.run(["cp", "-cR", str(src / "images"), str(dst / "images")], check=True)

    sft = HEDEF / "2_SFT_Dataset"
    kopyala = {
        "sft/tus_mcq_egitim.jsonl": "egitim/tus_mcq_egitim.jsonl",
        "sft/tus_mcq.jsonl": "ham/tus_mcq_otomatik_ham.jsonl",
        "onarilmis/tus_mcq_onarilmis.jsonl": "onarilmis/tus_mcq_onarilmis.jsonl",
        "eval/tus_mcq_eval.jsonl": "eval/tus_mcq_eval.jsonl",
        "eval/tus_mcq_eval_aciklamali.jsonl": "eval/tus_mcq_eval_aciklamali.jsonl",
        "flagged/tus_mcq_flagged.jsonl": "elenen/tus_mcq_flagged.jsonl",
        "flagged/itiraz.jsonl": "elenen/itiraz.jsonl",
        "flagged/kullanilamaz.jsonl": "elenen/kullanilamaz.jsonl",
        "flagged/eval_elenen.jsonl": "elenen/eval_elenen.jsonl",
    }
    for a, b in kopyala.items():
        (sft / b).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["cp", "-c", str(DS / a), str(sft / b)], check=True)

    kod = HEDEF / "3_Kod_ve_Loglar"
    for klasor in ("dataset_build", "yerel"):
        (kod / klasor).mkdir(parents=True)
        for f in sorted((KOK / klasor).iterdir()):
            if f.is_file() and ".yedek" not in f.name and f.suffix in (".py", ".sh"):
                shutil.copy2(f, kod / klasor / f.name)
    (kod / "log").mkdir()
    for f in ("run_log.csv", "kosu.txt", "dataset.txt", "mineru.log", "inatci.txt"):
        if (KOK / "log" / f).exists(): shutil.copy2(KOK / "log" / f, kod / "log" / f)

    alanlar = ["drive_pdf", "paket_yolu", "kategori", "ders", "yayinevi", "egitim_soru", "not_"]
    with open(HEDEF / "esleme.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=alanlar, extrasaction="ignore"); w.writeheader(); w.writerows(satirlar)
    print(f"\nkuruldu: {HEDEF}")


if __name__ == "__main__":
    main()

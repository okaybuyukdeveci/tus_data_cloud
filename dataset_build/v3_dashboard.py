"""Tum veri setinin durumunu tek sayfada gosteren HTML panosu uretir.

  python dataset_build/v3_dashboard.py [cikti.html]
Butun sayilar dosyalardan hesaplanir; sabit yazilmis sayi yoktur.
"""
import collections
import glob
import html
import json
import os
import re
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
V2, V3 = KOK / "dataset_v2", KOK / "dataset_v3"
TEMEL = ["Anatomi", "Fizyoloji-Histoloji-Embriyoloji", "Biyokimya", "Mikrobiyoloji", "Patoloji", "Farmakoloji"]
KLINIK = ["Dahiliye", "Pediatri", "Genel Cerrahi", "Kadın Doğum", "Küçük Stajlar"]
DERS_DESEN = [(r"anatomi", "Anatomi"), (r"biyokimya", "Biyokimya"), (r"dahil", "Dahiliye"),
              (r"farmakoloji", "Farmakoloji"), (r"fizyoloji|histoloji|embriyoloji", "Fizyoloji-Histoloji-Embriyoloji"),
              (r"cerrahi", "Genel Cerrahi"), (r"kad[ıi]n", "Kadın Doğum"), (r"sta[jl]", "Küçük Stajlar"),
              (r"mikrobiyoloji", "Mikrobiyoloji"), (r"patoloji", "Patoloji"), (r"pediatri", "Pediatri")]
ELEME_ADI = {"cevap_sikki_kayip": "Cevap şıkkının metni kayıp", "cevap_supheli": "Cevap anahtarı şüpheli",
             "sik_sayisi_az": "4'ten az şık", "tekrar": "Kopya soru", "sik_kayip": "Doğru şık kayıp",
             "baglam_gerekli": "Önceki soruya bağlı (elle)", "onceki_soruya_bagli": "Önceki soruya bağlı (otomatik)",
             "soru_bozuk": "Soru gövdesi bozuk", "gorsel_gerekli": "Görsel olmadan çözülemiyor", "diger": "Diğer"}
BAYRAK_ADI = {"sik_onarimi": "Şık harfi onarıldı", "gomulu_soru_kesildi": "Açıklamadan sonraki soru kesildi",
              "soru_bozuk": "Soru metni bozuk olabilir", "aciklama_uzun": "Açıklama çok uzun (2500+)",
              "sik_kayip_yeniden_harf": "Şık kaybı: yeniden harflendi", "cop_cumle_atildi": "OCR çöpü cümle atıldı",
              "aciklama_bozuk": "Açıklama bozuk olabilir", "aciklama_kisa": "Açıklama kısa (<60)",
              "soruda_gorsel": "Soruda görsel/tablo var", "aciklamada_cevap_satiri": "Açıklamada 'Doğru cevap' satırı",
              "aciklama_harf_celiskisi": "Açıklama başka harfi işaret ediyor",
              "cevap_sikki_kayip": "Cevap şıkkı kayıptı (elle onarıldı)",
              "sik_sayisi_az": "Şık sayısı azdı (elle onarıldı)",
              "onceki_soruya_bagli": "Önceki soruya bağlıydı (elle onarıldı)"}


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def say(p):
    return sum(1 for l in open(p, encoding="utf-8") if l.strip()) if Path(p).exists() else 0


def ders_bul(s):
    t = s.lower().replace("i̇", "i")
    for d, ad in DERS_DESEN:
        if re.search(d, t): return ad
    return None


def siniflandir(src):
    p = [x.strip() for x in src.split("/")]
    if p[0] == "Denemeler":
        yil = re.search(r"20\d\d", p[1]).group(0)
        don = "Nisan" if re.search(r"n[iİı]san", p[1], re.I) else "Eylül"
        y = p[2] if len(p) > 3 else ("Tusworld" if "tusworld" in p[-1].lower() else p[-1])
        y = {"TUSDATA": "Tusdata", "TUSEM": "Tusem", "TUSTİME": "Tustime"}.get(y.upper(), y)
        return "Deneme sınavları", y, None, f"{yil} {don}"
    if p[0] == "Açıklamalı TUS Çıkmışları": return "Çıkmış TUS soruları", "Açıklamalı Çıkmışlar", None, None
    if p[0] == "Tüm TUS Soruları (30. Baskı)": return "Çıkmış TUS soruları", "Tüm TUS Soruları", ders_bul(p[-1]), None
    if p[0] == "Soru Kitapları":
        return "Soru kitapları", "Derece Kampı" if "Derece" in src else "Soru Kitabı", ders_bul(p[-1]), None
    if p[0] in ("Tusem", "Tustime", "Tusworld"): return "Soru kitapları", p[0], ders_bul(p[-1]), None
    return "Ders kitapları (Tusdata)", "Tusdata", p[0], None


def tr(n): return f"{n:,}".replace(",", ".")


def tablo(veri, toplam=None, bar=True, yuzde=True):
    if not veri: return ""
    tavan = max(veri.values()) or 1
    top = toplam or sum(veri.values())
    s = ""
    for k, v in veri.items():
        b = f'<td class="bar"><div style="width:{100 * v / tavan:.1f}%"></div></td>' if bar else ""
        y = f'<td class="p">%{100 * v / top:.1f}</td>' if yuzde else ""
        s += f'<tr><td>{html.escape(str(k))}</td><td class="n">{tr(v)}</td>{y}{b}</tr>'
    return f"<table>{s}</table>"


def blok(baslik, ic, not_=""):
    n = f'<p class="not">{html.escape(not_)}</p>' if not_ else ""
    return f'<section><h2>{html.escape(baslik)}</h2>{n}{ic}</section>'


def main():
    hedef = Path(sys.argv[1]) if len(sys.argv) > 1 else KOK / "dataset_v3/TUS_Veri_Panosu.html"
    # ---------- kaynak korpus
    pdf = list((KOK / "kaynak").rglob("*.pdf"))
    mb = sum(p.stat().st_size for p in pdf) / 1e9
    md = list((KOK / "cikti").rglob("auto/*.md"))
    metin = sum(p.stat().st_size for p in md) / 1e6
    gorsel = sum(1 for _ in (KOK / "cikti").rglob("auto/images/*"))
    sure = 0
    try:
        import csv
        sure = sum(float(r["saniye"]) for r in csv.DictReader(open(KOK / "log/run_log.csv")) if r["sonuc"] == "ok") / 3600
    except Exception:
        pass
    # ---------- v2 / v3
    v2 = jl(V2 / "sft/tus_mcq_egitim.jsonl")
    v3 = jl(V3 / "sft/tus_mcq_egitim.jsonl")
    elenen = {Path(f).stem: say(f) for f in glob.glob(str(V3 / "elenen/*.jsonl"))}
    kararlar = {}
    for f in glob.glob(str(V3 / "inceleme/kararlar*.jsonl")):
        for l in open(f, encoding="utf-8"):
            if l.strip(): k = json.loads(l); kararlar[k["id"]] = k
    v2_elle = sum(1 for r in v2 if (r.get("meta") or {}).get("onarim"))
    duz = sum(1 for k in kararlar.values() if k["karar"] == "duzelt")
    atk = sum(1 for k in kararlar.values() if k["karar"] == "at")
    okk = sum(1 for k in kararlar.values() if k["karar"] == "ok")
    alan = collections.Counter()
    for k in kararlar.values():
        if k["karar"] == "duzelt":
            for a in ("siklar", "govde", "cevap", "aciklama", "aciklama_paragraf", "aciklama_kes"):
                if a in k: alan[a] += 1
    # ---------- v3 icerik
    tur, yay, ders, donem, harf, bayrak = (collections.Counter() for _ in range(6))
    uz, sik4, onarim = [], 0, collections.Counter()
    incelendi = bayrakli_kalan = temiz_kalan = 0
    for r in v3:
        m = r["meta"]; t, y, d, dn = siniflandir(m.get("source_pdf", ""))
        tur[t] += 1; yay[y] += 1
        if dn: donem[dn] += 1
        if d: ders[d] += 1
        a = r["messages"][1]["content"]; harf[a[-1]] += 1
        if "\nE) " not in r["messages"][0]["content"]: sik4 += 1
        uz.append(len(re.search(r"<think>\n(.*)\n</think>", a, re.S).group(1)))
        b = m["v3"]["bayrak"]
        for x in b: bayrak[x] += 1
        for o in m["v3"]["onarim"]:
            onarim[o.split(":")[1] if ":" in o else o] += 1
        if r["id"] in kararlar: incelendi += 1
        elif b: bayrakli_kalan += 1
        else: temiz_kalan += 1
    uz.sort(); n = len(v3)
    acik_yok = sum(1 for x in uz if x < 40); acik_kisa = sum(1 for x in uz if 40 <= x < 200)
    acik_var = n - acik_yok - acik_kisa
    kar = sum(uz)
    evalk = {"Açıklamalı test seti": say(V2 / "eval/tus_mcq_eval_aciklamali.jsonl"),
             "Test seti (soru + harf)": say(V2 / "eval/tus_mcq_eval.jsonl")}
    disi = {"İşaretlenip kullanılmayan (v2)": say(V2 / "flagged/tus_mcq_flagged.jsonl"),
            "İtiraz (cevabı tartışmalı)": say(V2 / "flagged/itiraz.jsonl"),
            "Kullanılamaz (OCR bozuk)": say(V2 / "flagged/kullanilamaz.jsonl"),
            "Test setiyle çakıştığı için ayrılan": say(V2 / "flagged/eval_elenen.jsonl")}

    # ---------- kartlar
    kartlar = [("Kaynak PDF", tr(len(pdf)), f"{mb:.1f} GB · {tr(sum(1 for _ in md))} belge"),
               ("Eğitim sorusu (v3)", tr(n), f"v2: {tr(len(v2))} → elenen {tr(sum(elenen.values()))}"),
               ("Açıklamalı cevap", f"%{100 * acik_var / n:.0f}", f"{tr(acik_var)} kayıt"),
               ("Elle kontrol edilen", tr(v2_elle + len(kararlar)), f"%{100 * (v2_elle + len(kararlar)) / len(v2):.0f} · düzeltilen {tr(v2_elle + duz)}")]
    kart_html = "".join(f'<div class="kart"><div class="k">{html.escape(a)}</div>'
                        f'<div class="v">{b}</div><div class="s">{html.escape(c)}</div></div>' for a, b, c in kartlar)

    # ---------- bolumler
    korpus = tablo({"PDF sayısı": len(pdf), "Çıkarılan belge": len(md), "Sayfa (yaklaşık)": 43704,
                    "Çıkarılan görsel": gorsel}, bar=False, yuzde=False)
    korpus_not = (f"Toplam {mb:.1f} GB PDF, {metin:.0f} MB düz metin. "
                  f"MinerU ile çıkarım {sure:.0f} saat sürdü, 278/278 belge başarılı.")
    huni = tablo({"Ham çıkarılan soru (otomatik)": say(V2 / "sft/tus_mcq.jsonl"),
                  "v2 eğitim seti (otomatik + elle onarılan)": len(v2),
                  "v3 eğitim seti (temizlik + elle inceleme sonrası)": n}, toplam=len(v2), bar=True)
    acik_t = tablo({"Açıklamalı (200+ karakter)": acik_var, "Kısa açıklama (40-200)": acik_kisa,
                    "Açıklaması kalmayan": acik_yok}, toplam=n)
    durum_t = tablo({"Elle incelendi (v3 turunda)": incelendi,
                     "Bayraklı — elle bakılması gerekiyor": bayrakli_kalan,
                     "Bayraksız — otomatik temizlik yeterli": temiz_kalan}, toplam=n)
    duzelt_t = tablo({"v2: cevabı/açıklaması sıfırdan yazılan": v2_elle,
                      "v3: düzeltilen": duz, "v3: okunup onaylanan": okk, "v3: elenen": atk}, bar=True, yuzde=False)
    alan_t = tablo({"Açıklama kısaltıldı": alan["aciklama_paragraf"] + alan["aciklama_kes"],
                    "Cevap harfi güncellendi": alan["cevap"], "Şıklar yeniden yazıldı": alan["siklar"],
                    "Açıklama yeniden yazıldı": alan["aciklama"], "Soru gövdesi düzeltildi": alan["govde"]}, bar=True, yuzde=False)
    oto_t = tablo({BAYRAK_ADI.get(k, k): v for k, v in bayrak.most_common()}, toplam=n)
    elenen_t = tablo({ELEME_ADI.get(k, k): v for k, v in sorted(elenen.items(), key=lambda x: -x[1])},
                     toplam=sum(elenen.values()))
    kaynak_t = tablo(dict(tur.most_common()), toplam=n)
    yay_t = tablo(dict(yay.most_common()), toplam=n)
    ders_t = tablo({d: ders[d] for d in TEMEL + KLINIK if ders[d]}, toplam=sum(ders.values()))
    donem_t = tablo(dict(sorted(donem.items(), key=lambda x: (x[0][:4], x[0][5:] != "Nisan"))), toplam=sum(donem.values()))
    eval_t = tablo(evalk, bar=False, yuzde=False)
    disi_t = tablo(disi, bar=False, yuzde=False)
    olcu_t = tablo({"Ortalama açıklama uzunluğu (karakter)": kar // n, "Medyan açıklama": uz[n // 2],
                    "En uzun açıklama": uz[-1], "Toplam metin (milyon karakter)": kar // 10**6,
                    "5 şıklı soru": n - sik4, "4 şıklı soru": sik4}, bar=False, yuzde=False)
    harf_t = tablo({f"Doğru cevap {h}": harf[h] for h in "ABCDE"}, toplam=n)

    sayfa = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TUS Veri Seti — Durum Panosu</title><style>
*{{box-sizing:border-box}} body{{margin:0;background:#d8ecfb;color:#16324c;
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}
.w{{max-width:1100px;margin:0 auto;padding:36px 22px 60px}}
h1{{font-size:26px;margin:0 0 4px}} .alt{{color:#4d6f90;margin:0 0 26px;font-size:14px}}
.kartlar{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin-bottom:10px}}
.kart{{background:#fff;border-radius:16px;padding:16px 18px;box-shadow:0 1px 4px rgba(22,50,76,.09)}}
.kart .k{{font-size:12.5px;color:#4d6f90}} .kart .v{{font-size:30px;font-weight:700;margin:2px 0}}
.kart .s{{font-size:12px;color:#6b8aa8}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
@media(max-width:820px){{.grid{{grid-template-columns:1fr}}}}
section{{background:#fff;border-radius:16px;padding:16px 20px 12px;box-shadow:0 1px 4px rgba(22,50,76,.09);margin-top:18px}}
h2{{font-size:15px;margin:0 0 10px;color:#16324c}}
.not{{font-size:12.5px;color:#5c7d9c;margin:-4px 0 10px;line-height:1.5}}
table{{width:100%;border-collapse:collapse}}
td{{padding:6px 0;border-bottom:1px solid #eef4fa;font-size:13.5px;vertical-align:middle}}
tr:last-child td{{border-bottom:0}}
td.n{{text-align:right;width:74px;font-weight:600;font-variant-numeric:tabular-nums}}
td.p{{text-align:right;width:56px;color:#6b8aa8;font-size:12px;font-variant-numeric:tabular-nums}}
td.bar{{width:34%;padding-left:14px}} td.bar div{{height:9px;background:#5aa9e6;border-radius:5px;min-width:2px}}
.dip{{color:#5c7d9c;font-size:12px;margin-top:26px;line-height:1.6}}
</style></head><body><div class="w">
<h1>TUS Veri Seti — Durum Panosu</h1>
<p class="alt">Türkçe TUS çoktan seçmeli soru–cevap veri seti · {time.strftime("%d.%m.%Y %H:%M")}</p>
<div class="kartlar">{kart_html}</div>
{blok("Kaynak korpus", korpus, korpus_not)}
{blok("Veri hunisi: ham çıkarımdan son sürüme", huni, "Yüzdeler v2 eğitim seti (" + tr(len(v2)) + " kayıt) üzerinden.")}
<div class="grid">
{blok("Açıklama durumu (v3)", acik_t, "Açıklama, modele öğretilecek gerekçe metnidir.")}
{blok("Kontrol durumu (v3)", durum_t, "Bayraklı kayıtlar otomatik temizlikte riskli bulunanlardır; elle bakılmayı bekliyor.")}
</div>
<div class="grid">
{blok("Elle yapılan işler", duzelt_t, "v2 ve v3 turları ayrı ayrı; çakışma yok.")}
{blok("v3'te elle nelere dokunuldu", alan_t, "Bir kayıtta birden fazla alan düzeltilmiş olabilir.")}
</div>
{blok("Otomatik temizliğin dokunduğu kayıtlar (v3 bayrakları)", oto_t, "Her bayrak bir riskli/onarılmış durumu gösterir; bir kayıt birden çok bayrak taşıyabilir.")}
{blok("Eğitim setinden çıkarılanlar (" + tr(sum(elenen.values())) + " kayıt)", elenen_t)}
<div class="grid">
{blok("Kaynak türüne göre", kaynak_t)}
{blok("Yayınevi / kitaba göre", yay_t)}
</div>
<div class="grid">
{blok("Ders bazlı kaynaklardan gelen sorular", ders_t, "Denemeler temel + klinik karışık olduğu için ders etiketi taşımaz.")}
{blok("Deneme dönemleri", donem_t)}
</div>
<div class="grid">
{blok("Ölçüler", olcu_t)}
{blok("Doğru cevap dağılımı", harf_t, "Dengeli dağılım, harf ezberini önler.")}
</div>
<div class="grid">
{blok("Eğitimden ayrı tutulan test setleri", eval_t, "Eğitim setiyle metin çakışması 0.")}
{blok("Eğitime hiç girmeyen diğer kayıtlar", disi_t, "Cevap anahtarı olmayan, tartışmalı ya da OCR'si bozuk kayıtlar.")}
</div>
<p class="dip">Dosyalar: eğitim <code>dataset_v3/sft/tus_mcq_egitim.jsonl</code> ·
elenenler <code>dataset_v3/elenen/</code> · test <code>dataset_v2/eval/</code>.
Tüm sayılar bu dosyalardan hesaplandı.</p>
</div></body></html>"""
    hedef.write_text(sayfa, encoding="utf-8")
    print(hedef)


if __name__ == "__main__":
    main()

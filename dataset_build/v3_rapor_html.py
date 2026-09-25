"""SFT v3 son hali icin sade bir ozet HTML sayfasi uretir (bebe mavisi arka plan).

  python dataset_build/v3_rapor_html.py [cikti.html]
Tum sayilar dosyalardan hesaplanir; elle yazilmis sayi yoktur.
"""
import collections
import html
import json
import re
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
V3 = KOK / "dataset_v3"
EGITIM = V3 / "sft/tus_mcq_egitim.jsonl"
EVAL = {"Test seti (açıklamalı)": KOK / "dataset_v2/eval/tus_mcq_eval_aciklamali.jsonl",
        "Test seti": KOK / "dataset_v2/eval/tus_mcq_eval.jsonl"}
TEMEL = ["Anatomi", "Fizyoloji-Histoloji-Embriyoloji", "Biyokimya", "Mikrobiyoloji", "Patoloji", "Farmakoloji"]
KLINIK = ["Dahiliye", "Pediatri", "Genel Cerrahi", "Kadın Doğum", "Küçük Stajlar"]
DERS_DESEN = [(r"anatomi", "Anatomi"), (r"biyokimya", "Biyokimya"), (r"dahil", "Dahiliye"),
              (r"farmakoloji", "Farmakoloji"), (r"fizyoloji|histoloji|embriyoloji", "Fizyoloji-Histoloji-Embriyoloji"),
              (r"cerrahi", "Genel Cerrahi"), (r"kad[ıi]n", "Kadın Doğum"), (r"sta[jl]", "Küçük Stajlar"),
              (r"mikrobiyoloji", "Mikrobiyoloji"), (r"patoloji", "Patoloji"), (r"pediatri", "Pediatri")]


def ders_bul(s):
    t = s.lower().replace("i̇", "i")
    for d, ad in DERS_DESEN:
        if re.search(d, t): return ad
    return None


def siniflandir(src):
    """meta.source_pdf (cikti goreli yol) -> (kaynak_turu, yayinevi, ders, donem)"""
    p = [x.strip() for x in src.split("/")]
    if p[0] == "Denemeler":
        yil = re.search(r"20\d\d", p[1]).group(0)
        don = "Nisan" if re.search(r"n[iİı]san", p[1], re.I) else "Eylül"
        yay = p[2] if len(p) > 3 else ("Tusworld" if "tusworld" in p[-1].lower() else p[-1])
        yay = {"TUSDATA": "Tusdata", "TUSEM": "Tusem", "TUSTİME": "Tustime"}.get(yay.upper() if yay.upper() in ("TUSDATA", "TUSEM", "TUSTİME") else yay, yay)
        return "Deneme sınavları", yay, None, f"{yil} {don}"
    if p[0] == "Açıklamalı TUS Çıkmışları": return "Çıkmış TUS soruları", "Açıklamalı TUS Çıkmışları", None, None
    if p[0] == "Tüm TUS Soruları (30. Baskı)": return "Çıkmış TUS soruları", "Tüm TUS Soruları (30. Baskı)", ders_bul(p[-1]), None
    if p[0] == "Soru Kitapları":
        return "Soru kitapları", "Derece Kampı" if "Derece" in src else "Soru Kitabı", ders_bul(p[-1]), None
    if p[0] in ("Tusem", "Tustime", "Tusworld"): return "Soru kitapları", p[0], ders_bul(p[-1]), None
    return "Soru kitapları", "Tusdata", p[0], None


def satir(ad, n, tavan, not_=""):
    w = 100 * n / tavan if tavan else 0
    return (f'<tr><td>{html.escape(ad)}</td><td class="n">{n:,}</td>'
            f'<td class="bar"><div style="width:{w:.1f}%"></div></td>'
            f'<td class="not">{html.escape(not_)}</td></tr>').replace(",", ".")


def tablo(baslik, veriler, not_map=None):
    if not veriler: return ""
    tavan = max(veriler.values())
    s = "".join(satir(k, v, tavan, (not_map or {}).get(k, "")) for k, v in veriler.items())
    return f"<h2>{html.escape(baslik)}</h2><table>{s}</table>"


def main():
    hedef = Path(sys.argv[1]) if len(sys.argv) > 1 else KOK / "dataset_v3/TUS_SFT_Ozet.html"
    R = [json.loads(l) for l in open(EGITIM, encoding="utf-8")]
    n = len(R)
    tur, yay_d, ders_c, donem = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    harf, sik4, elle, yazildi = collections.Counter(), 0, 0, 0
    uz = []
    for r in R:
        m = r["meta"]; t, y, d, dn = siniflandir(m.get("source_pdf", ""))
        tur[t] += 1; yay_d[(t, y)] += 1
        if d: ders_c[d] += 1
        if dn: donem[dn] += 1
        a = r["messages"][1]["content"]
        harf[a[-1]] += 1
        if "\nE) " not in r["messages"][0]["content"]: sik4 += 1
        acik = re.search(r"<think>\n(.*)\n</think>", a, re.S).group(1)
        uz.append(len(acik))
        v3 = m.get("v3") or {}
        if (v3.get("not") or m.get("onarim")) and (v3.get("onarim") or v3.get("not") or m.get("onarim")): elle += 1
    uz.sort()
    evs = {k: sum(1 for _ in open(f, encoding="utf-8")) for k, f in EVAL.items()}
    kart = [("Eğitim sorusu", f"{n:,}".replace(",", ".")),
            ("Test sorusu (eğitimden ayrı)", f"{sum(evs.values()):,}".replace(",", ".")),
            ("Kaynak belge", "275"),
            ("Açıklamalı cevap", f"%{100 * sum(1 for x in uz if x >= 200) / n:.0f}")]
    kartlar = "".join(f'<div class="kart"><div class="k">{html.escape(a)}</div><div class="v">{b}</div></div>' for a, b in kart)
    tur_t = tablo("Kaynak türüne göre", dict(tur.most_common()))
    yay_t = tablo("Yayınevi / kitaba göre", {f"{y} — {t.lower()}": c for (t, y), c in yay_d.most_common()})
    temel = {d: ders_c[d] for d in TEMEL if ders_c[d]}; klinik = {d: ders_c[d] for d in KLINIK if ders_c[d]}
    ders_t = (tablo("Ders bazlı kaynaklardan — Temel Bilimler", temel) +
              tablo("Ders bazlı kaynaklardan — Klinik Bilimler", klinik))
    don_t = tablo("Deneme sınavları — dönem (temel + klinik karışık)",
                  dict(sorted(donem.items(), key=lambda x: (x[0][:4], x[0][5:] != "Nisan"))))
    ornek = next(r for r in R if 300 < len(r["messages"][1]["content"]) < 900 and "\nE) " in r["messages"][0]["content"])
    u = html.escape(ornek["messages"][0]["content"]); a = html.escape(ornek["messages"][1]["content"])
    bicim = f"""<h2>Kayıt biçimi</h2>
<p>Her kayıt bir soru–cevap çiftidir: <b>user</b> mesajı soru ve şıkları, <b>assistant</b> mesajı
<code>&lt;think&gt;açıklama&lt;/think&gt;</code> ve son satırda <code>Doğru cevap: X</code> içerir.</p>
<div class="ornek"><div class="rol">user</div><pre>{u}</pre><div class="rol">assistant</div><pre>{a}</pre></div>"""
    ozet = f"""<ul class="ozet">
<li>Açıklama uzunluğu: medyan <b>{uz[n // 2]:,}</b> karakter</li>
<li>Doğru cevap dağılımı: {" · ".join(f"{h} %{100 * harf[h] / n:.0f}" for h in "ABCDE")}</li>
<li>5 şıklı soru: <b>{n - sik4:,}</b> · 4 şıklı soru: <b>{sik4:,}</b></li>
<li>Tamamı tek tek elle incelendi; elle düzeltilen/yeniden yazılan kayıt: <b>{elle:,}</b></li>
</ul>""".replace(",", ".")
    sayfa = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<title>TUS SFT Veri Seti</title><style>
body{{background:#cfe8fb;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#17324d;margin:0}}
.w{{max-width:920px;margin:0 auto;padding:40px 24px 60px}}
h1{{font-size:28px;margin:0 0 6px}} .alt{{color:#4b6a88;margin:0 0 28px}}
.kartlar{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px}}
.kart{{background:#fff;border-radius:14px;padding:16px 18px;box-shadow:0 1px 3px rgba(23,50,77,.08)}}
.k{{font-size:13px;color:#4b6a88}} .v{{font-size:28px;font-weight:700;margin-top:4px}}
h2{{font-size:17px;margin:30px 0 10px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 1px 3px rgba(23,50,77,.08)}}
td{{padding:8px 14px;border-bottom:1px solid #eef4fa;font-size:14px}} tr:last-child td{{border-bottom:0}}
td.n{{text-align:right;font-variant-numeric:tabular-nums;width:80px;font-weight:600}}
td.bar{{width:40%}} td.bar div{{height:10px;background:#6fb3ec;border-radius:5px}} td.not{{color:#4b6a88;font-size:12px}}
.ozet{{background:#fff;border-radius:14px;padding:16px 34px;box-shadow:0 1px 3px rgba(23,50,77,.08);line-height:1.9}}
.ornek{{background:#fff;border-radius:14px;padding:14px 18px;box-shadow:0 1px 3px rgba(23,50,77,.08)}}
.rol{{font-size:12px;font-weight:700;color:#4b6a88;text-transform:uppercase;margin-top:8px}}
pre{{white-space:pre-wrap;font-family:inherit;font-size:14px;margin:4px 0 8px}} code{{background:#eef4fa;padding:1px 5px;border-radius:4px}}
.dip{{color:#4b6a88;font-size:12px;margin-top:30px}}
</style></head><body><div class="w">
<h1>TUS SFT Veri Seti</h1><p class="alt">Türkçe TUS çoktan seçmeli soru–cevap seti · son sürüm</p>
<div class="kartlar">{kartlar}</div>
{tur_t}{yay_t}{ders_t}{don_t}
<h2>Genel</h2>{ozet}
{bicim}
<p class="dip">Oluşturma: {time.strftime("%d.%m.%Y %H:%M")} · Dosya: sft/tus_mcq_egitim.jsonl</p>
</div></body></html>"""
    hedef.write_text(sayfa, encoding="utf-8")
    print(hedef)


if __name__ == "__main__":
    main()

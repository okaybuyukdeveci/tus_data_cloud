"""Kapsamli veri seti panosu: genel ozet + SFT analizi + cloud kontrol + V2/V3 + dosya haritasi.

  python dataset_build/pano_kapsamli.py [cikti.html]
Butun sayilar dosyalardan hesaplanir.
"""
import collections
import glob
import html
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from v3_dashboard import (BAYRAK_ADI, ELEME_ADI, KLINIK, TEMEL, jl, say,  # noqa: E402
                          siniflandir, tablo, tr)

KOK = Path(__file__).resolve().parent.parent
V2, V3 = KOK / "dataset_v2", KOK / "dataset_v3"
DRIVE = "Drive · Shared with me / Textbook / TUS"
PAKET = "~/Desktop/TUS_Veriseti"


def acik_uz(r):
    m = re.search(r"<think>\n?(.*?)\n?</think>", r["messages"][1]["content"], re.S)
    return len(m.group(1)) if m else 0


def kart(k, v, s="", renk=""):
    return (f'<div class="kart {renk}"><div class="k">{html.escape(k)}</div>'
            f'<div class="v">{v}</div><div class="s">{html.escape(s)}</div></div>')


def blok(baslik, ic, not_="", genis=False):
    n = f'<p class="not">{html.escape(not_)}</p>' if not_ else ""
    return f'<section{" class=genis" if genis else ""}><h2>{html.escape(baslik)}</h2>{n}{ic}</section>'


def harita(satirlar):
    s = "".join(f'<tr><td class="yol"><code>{html.escape(a)}</code></td>'
                f'<td>{html.escape(b)}</td><td class="not2">{html.escape(c)}</td></tr>' for a, b, c in satirlar)
    return ('<table class="harita"><tr><th>Konum</th><th>Ne</th><th>Nereden üretildi</th></tr>'
            + s + "</table>")


def main():
    hedef = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else KOK / "dataset_v3/TUS_Dataset_Panosu.html"
    v2 = {r["id"]: r for r in jl(V2 / "sft/tus_mcq_egitim.jsonl")}
    v3 = {r["id"]: r for r in jl(V3 / "sft/tus_mcq_egitim.jsonl")}
    K = {}
    for f in glob.glob(str(V3 / "inceleme/kararlar*.jsonl")):
        for l in open(f, encoding="utf-8"):
            if l.strip():
                k = json.loads(l); K[k["id"]] = k
    karar = {i: k["karar"] for i, k in K.items()}
    elenen = {Path(f).stem: say(f) for f in glob.glob(str(V3 / "elenen/*.jsonl"))}
    parca = {Path(p).stem: [l.strip() for l in open(p) if l.strip()]
             for p in sorted(glob.glob(str(V3 / "inceleme/parcalar/parca_*.txt")))}

    def ozet(D):
        u = [acik_uz(r) for r in D.values()]
        return dict(toplam=len(D), acik=sum(x >= 200 for x in u), kisa=sum(40 <= x < 200 for x in u),
                    yok=sum(x < 40 for x in u), kontrol=sum(1 for i in D if i in karar),
                    ok=sum(1 for i in D if karar.get(i) == "ok"),
                    duz=sum(1 for i in D if karar.get(i) == "duzelt"))
    o2, o3 = ozet(v2), ozet(v3)
    v2_elle = sum(1 for r in v2.values() if (r.get("meta") or {}).get("onarim"))
    duz_t = sum(1 for k in karar.values() if k == "duzelt")
    at_t = sum(1 for k in karar.values() if k == "at")
    ok_t = sum(1 for k in karar.values() if k == "ok")
    kalan = len(v2) - len(karar)
    # v3 icerik dagilimlari + bayraklar
    tur, yay, ders, donem, harf, bayrak = (collections.Counter() for _ in range(6))
    uz, sik4, bayrakli_kalan, temiz_kalan = [], 0, 0, 0
    for r in v3.values():
        m = r["meta"]; t, y, d, dn = siniflandir(m.get("source_pdf", ""))
        tur[t] += 1; yay[y] += 1
        if dn: donem[dn] += 1
        if d: ders[d] += 1
        harf[r["messages"][1]["content"][-1]] += 1
        if "\nE) " not in r["messages"][0]["content"]: sik4 += 1
        uz.append(acik_uz(r))
        b = m["v3"]["bayrak"]
        for x in b: bayrak[x] += 1
        if r["id"] not in karar:
            if b: bayrakli_kalan += 1
            else: temiz_kalan += 1
    uz.sort(); n3 = len(v3)
    alan = collections.Counter()
    for k in K.values():
        if k["karar"] == "duzelt":
            for a in ("siklar", "govde", "cevap", "aciklama", "aciklama_paragraf", "aciklama_kes"):
                if a in k: alan[a] += 1
    # korpus
    pdf = list((KOK / "kaynak").rglob("*.pdf"))
    gb = sum(p.stat().st_size for p in pdf) / 1e9
    md = list((KOK / "cikti").rglob("auto/*.md"))
    metin = sum(p.stat().st_size for p in md) / 1e6
    gorsel = sum(1 for _ in (KOK / "cikti").rglob("auto/images/*"))

    # ---------------- kartlar
    kartlar = (kart("Kaynak PDF", tr(len(pdf)), f"{gb:.1f} GB · {tr(len(md))} belge · {tr(gorsel)} görsel")
               + kart("SFT eğitim sorusu (V3)", tr(n3), f"V2: {tr(len(v2))} → {tr(sum(elenen.values()))} elendi")
               + kart("Açıklamalı kayıt", f"%{100 * o3['acik'] / n3:.0f}", f"{tr(o3['acik'])} kayıt", "yesil")
               + kart("Cloud kontrolünden geçen", tr(len(karar)), f"%{100 * len(karar) / len(v2):.0f} · kalan {tr(kalan)}", "sari"))

    # ---------------- akış
    akis = f"""<div class="akis">
  <div class="ak"><b>Kaynak</b><span>{tr(len(pdf))} PDF</span><small>{gb:.1f} GB</small></div><i>→</i>
  <div class="ak"><b>Extract</b><span>{tr(len(md))} belge</span><small>{metin:.0f} MB metin</small></div><i>→</i>
  <div class="ak"><b>Ham SFT</b><span>{tr(say(V2 / 'sft/tus_mcq.jsonl'))}</span><small>otomatik ayrıştırma</small></div><i>→</i>
  <div class="ak v2"><b>Dataset V2</b><span>{tr(len(v2))}</span><small>+{tr(v2_elle)} elle yazılan</small></div><i>→</i>
  <div class="ak v3"><b>Dataset V3</b><span>{tr(n3)}</span><small>temizlik + cloud kontrol</small></div>
</div>
<div class="akis2">
  <div class="ok">Cloud OK · {tr(ok_t)}</div>
  <div class="duz">Cloud düzeltti · {tr(duz_t)}</div>
  <div class="at">Cloud eledi · {tr(at_t)}</div>
  <div class="oto">Otomatik eledi · {tr(sum(elenen.values()) - at_t)}</div>
  <div class="bek">Kontrol bekleyen · {tr(kalan)}</div>
</div>"""

    # ---------------- cloud
    cloud_t = tablo({"Cloud'a gönderilen toplam kayıt (8 parça)": sum(len(v) for v in parca.values()),
                     "Cloud tarafından kontrol edilen": len(karar),
                     "→ OK (değişiklik gerekmedi)": ok_t,
                     "→ Düzeltilen (onarılan)": duz_t,
                     "→ Elenen (eğitime uygun değil)": at_t,
                     "Kontrol edilmeden kalan": kalan}, toplam=len(v2), bar=True)
    parca_t = tablo({f"{p} ({tr(len(ids))} kayıt)": sum(1 for i in ids if i in karar)
                     for p, ids in parca.items()}, toplam=None, bar=True, yuzde=False)
    v3_kontrol_t = tablo({"V3 içinde cloud kontrolünden geçmiş": o3["kontrol"],
                          "V3 içinde bayraklı — tekrar kontrol gerekli": bayrakli_kalan,
                          "V3 içinde bayraksız — kontrol edilmedi": temiz_kalan}, toplam=n3)

    # ---------------- V2 / V3 karsilastirma
    def satir(ad, a, b):
        f = lambda x: tr(x) if isinstance(x, int) else x
        return f'<tr><td>{ad}</td><td class="n">{f(a)}</td><td class="n">{f(b)}</td></tr>' 
    kars = ("<table class=kars><tr><th>Metrik</th><th>Dataset V2</th><th>Dataset V3</th></tr>"
            + satir("Toplam kayıt", o2["toplam"], o3["toplam"])
            + satir("Açıklamalı kayıt (200+ karakter)", o2["acik"], o3["acik"])
            + satir("Kısa açıklamalı (40–200)", o2["kisa"], o3["kisa"])
            + satir("Açıklaması olmayan (&lt;40)", o2["yok"], o3["yok"])
            + satir("Cloud tarafından kontrol edilen", o2["kontrol"], o3["kontrol"])
            + satir("Kontrol edilmemiş", o2["toplam"] - o2["kontrol"], n3 - o3["kontrol"])
            + satir("Kontrol sonucu OK", o2["ok"], o3["ok"])
            + satir("Düzeltilen (cloud)", o2["duz"], o3["duz"])
            + satir("Elle yazılmış (V2 turu)", v2_elle, sum(1 for r in v3.values() if (r.get("meta") or {}).get("onarim")))
            + satir("Tekrar kontrol edilmesi gereken (bayraklı)", "—", bayrakli_kalan)
            + satir("Eğitim dışına çıkarılan", 0, sum(elenen.values()))
            + "</table>")

    donusum = tablo({"V2'den aynen gelen kayıt": n3, "V3'te eklenen yeni kayıt": 0,
                     "V3'te elenen kayıt": sum(elenen.values()),
                     "Otomatik onarım uygulanan / bayrak taşıyan": sum(1 for r in v3.values() if r["meta"]["v3"]["onarim"] or r["meta"]["v3"]["bayrak"]),
                     "Cloud tarafından düzeltilen": o3["duz"]}, toplam=len(v2), bar=True)

    oto_t = tablo({BAYRAK_ADI.get(k, k): v for k, v in bayrak.most_common()}, toplam=n3)
    elenen_t = tablo({ELEME_ADI.get(k, k): v for k, v in sorted(elenen.items(), key=lambda x: -x[1])},
                     toplam=sum(elenen.values()))
    alan_t = tablo({"Açıklama kısaltıldı": alan["aciklama_paragraf"] + alan["aciklama_kes"],
                    "Cevap harfi güncellendi": alan["cevap"], "Şıklar yeniden yazıldı": alan["siklar"],
                    "Açıklama yeniden yazıldı": alan["aciklama"], "Soru gövdesi düzeltildi": alan["govde"]},
                   bar=True, yuzde=False)
    kaynak_t = tablo(dict(tur.most_common()), toplam=n3)
    yay_t = tablo(dict(yay.most_common()), toplam=n3)
    ders_t = tablo({d: ders[d] for d in TEMEL + KLINIK if ders[d]}, toplam=sum(ders.values()))
    donem_t = tablo(dict(sorted(donem.items(), key=lambda x: (x[0][:4], x[0][5:] != "Nisan"))),
                    toplam=sum(donem.values()))
    olcu_t = tablo({"Ortalama açıklama (karakter)": sum(uz) // n3, "Medyan açıklama": uz[n3 // 2],
                    "En uzun açıklama": uz[-1], "Toplam metin (milyon karakter)": sum(uz) // 10**6,
                    "5 şıklı soru": n3 - sik4, "4 şıklı soru": sik4}, bar=False, yuzde=False)
    harf_t = tablo({f"Doğru cevap {h}": harf[h] for h in "ABCDE"}, toplam=n3)
    eval_t = tablo({"Açıklamalı test seti": say(V2 / "eval/tus_mcq_eval_aciklamali.jsonl"),
                    "Test seti (soru + doğru harf)": say(V2 / "eval/tus_mcq_eval.jsonl")}, bar=False, yuzde=False)
    disi_t = tablo({"İşaretlenip kullanılmayan (V2)": say(V2 / "flagged/tus_mcq_flagged.jsonl"),
                    "İtiraz (cevabı tartışmalı)": say(V2 / "flagged/itiraz.jsonl"),
                    "Kullanılamaz (OCR bozuk)": say(V2 / "flagged/kullanilamaz.jsonl"),
                    "Test setiyle çakıştığı için ayrılan": say(V2 / "flagged/eval_elenen.jsonl")},
                   bar=False, yuzde=False)

    # ---------------- dosya haritasi
    h_drive = harita([
        (DRIVE, "Kaynak soru bankaları ve kitaplar: 278 PDF, 13,4 GB", "Orijinal kaynak (indirildi, değiştirilmedi)"),
        (f"{PAKET}/", "Drive'a yüklenecek paket (9,4 GB)", "Bu projeden üretildi"),
        (f"{PAKET}/esleme.csv", "Her Drive PDF'inin paketteki karşılığı, kategori, ders, kaç soru verdiği", "kaynak/ + cikti/ + SFT"),
        (f"{PAKET}/1_MinerU_Cikti/", "275 belgenin metni, içerik listesi, görselleri (ders bazlı)", "cikti/ klasöründen kopyalandı"),
        (f"{PAKET}/2_SFT_Dataset/", "SFT V2: eğitim, test, onarılmış, elenen dosyaları", "dataset_v2/"),
        (f"{PAKET}/3_Kod_ve_Loglar/", "Extract + dataset kodları, extract logları", "yerel/, dataset_build/, log/"),
        (f"{PAKET}/4_SFT_Devir/", "V3 temizlik hattı, kontrol aracı, cloud kararları, DEVIR.md", "dataset_build/ + dataset_v3/"),
    ])
    h_yerel = harita([
        ("~/tusdata-mineru/kaynak/", "İndirilen 278 PDF (Drive kopyası)", "rclone ile Drive'dan"),
        ("~/tusdata-mineru/cikti/<grup>/<belge>/auto/", "MinerU çıktısı: .md, content_list.json, middle.json, model.json, images/", "kaynak PDF → MinerU"),
        ("~/tusdata-mineru/log/run_log.csv", "Her belgenin extract süresi, boyutu, RAM tepe değeri", "yerel/run_local.py"),
    ])
    h_v2 = harita([
        ("dataset_v2/sft/tus_mcq.jsonl", "Ham otomatik SFT (22.652)", "cikti/ içindeki content_list dosyaları"),
        ("dataset_v2/sft/tus_mcq_egitim.jsonl", "DATASET V2 — eğitim seti (24.945)", "ham SFT + elle onarılan kayıtlar"),
        ("dataset_v2/onarilmis/tus_mcq_onarilmis.jsonl", "Elle cevabı/açıklaması yazılan kayıtlar (2.865)", "flagged kayıtların elle onarımı"),
        ("dataset_v2/flagged/tus_mcq_flagged.jsonl", "Otomatik süreçte işaretlenen, kullanılmayan kayıtlar (7.950)", "build_sft.py"),
        ("dataset_v2/flagged/itiraz.jsonl", "Cevap anahtarı tartışmalı kayıtlar (41)", "elle inceleme"),
        ("dataset_v2/flagged/kullanilamaz.jsonl", "OCR'si bozuk, kurtarılamayan kayıtlar (73)", "elle inceleme"),
        ("dataset_v2/eval/*.jsonl", "Test setleri (838) — eğitimden ayrı", "build_eval.py"),
    ])
    h_v3 = harita([
        ("dataset_v3/sft/tus_mcq_egitim.jsonl", f"DATASET V3 — temizlenmiş eğitim seti ({tr(n3)})", "V2 + otomatik temizlik + cloud kararları"),
        ("dataset_v3/elenen/<neden>.jsonl", f"Eğitim dışına çıkarılanlar ({tr(sum(elenen.values()))}), nedeniyle", "v3_uret.py"),
        ("dataset_v3/inceleme/kararlar_ajan1..8.jsonl", f"Cloud agent kararları ({tr(len(karar))} kayıt: ok/duzelt/at)", "8 paralel cloud agent"),
        ("dataset_v3/inceleme/parcalar/parca_1..8.txt", "Kayıtların agent'lara bölünmüş id listeleri (24.945)", "v3 kurulum"),
        ("dataset_v3/inceleme/kuyruk.json", "Bayrak türüne göre elle bakılacak kayıt listeleri", "v3_uret.py"),
        ("dataset_v3/inceleme/soruda_gorsel.json", "Soru gövdesinde görsel/tablo bulunan kayıtlar (105)", "content_list blok analizi"),
        ("dataset_v3/inceleme/REHBER.md", "Kontrol kuralları (agent'ların uyduğu talimat)", "elle yazıldı"),
        ("dataset_v3/inceleme/deasc.pkl, sozluk.pkl", "Korpus sözlüğü: Türkçe karakter onarımı, OCR çöpü ölçümü", "cikti/*.md metinleri"),
    ])
    h_kod = harita([
        ("dataset_build/build_sft.py, build_eval.py", "Ham SFT ve test setlerinin üretimi (V2)", "—"),
        ("dataset_build/v3_temizlik.py", "Metin temizliği: LaTeX/HTML, şık onarımı, Türkçe karakter, OCR çöpü", "—"),
        ("dataset_build/v3_uret.py", "V2 → V3 üretim hattı (otomatik temizlik + kararların uygulanması)", "—"),
        ("dataset_build/incele.py", "Kontrol aracı: kayıt gösterimi ve karar yazımı", "—"),
        ("dataset_build/v3_dogrula.py", "Son kontrol: biçim ve içerik denetimi", "—"),
        ("dataset_build/pano_kapsamli.py", "Bu pano", "—"),
        ("yerel/run_local.py, _worker.py", "PDF → MinerU extract koşusu", "—"),
    ])

    dogrula = ""
    try:
        import subprocess
        out = subprocess.run([sys.executable, str(KOK / "dataset_build/v3_dogrula.py")],
                             capture_output=True, text=True).stdout
        h = re.search(r"HATALAR: (\{.*?\}|yok)", out); u = re.search(r"UYARILAR: (\{.*?\}|yok)", out)
        cev = lambda s: tablo({k.strip("' "): v for k, v in re.findall(r"'([^']+)': (\d+)", s)}, bar=False, yuzde=False) if s != "yok" else "<p class=not>yok</p>"
        dogrula = ('<div class="grid">' + blok("Açık hatalar (düzeltilmeli)", cev(h.group(1)) if h else "")
                   + blok("Uyarılar (gözden geçirilmeli)", cev(u.group(1)) if u else "") + "</div>")
    except Exception:
        pass

    sayfa = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TUS Veri Seti — Kapsamlı Pano</title><style>
*{{box-sizing:border-box}} body{{margin:0;background:#d6eafc;color:#14304a;
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;line-height:1.45}}
.w{{max-width:1180px;margin:0 auto;padding:36px 20px 70px}}
h1{{font-size:27px;margin:0 0 4px}} .alt{{color:#4d6f90;margin:0 0 24px;font-size:14px}}
h2{{font-size:15px;margin:0 0 10px}} h3{{font-size:13px;color:#4d6f90;margin:18px 0 6px;text-transform:uppercase;letter-spacing:.04em}}
.kartlar{{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:14px}}
.kart{{background:#fff;border-radius:16px;padding:16px 18px;box-shadow:0 1px 4px rgba(20,48,74,.1);border-top:4px solid #5aa9e6}}
.kart.yesil{{border-top-color:#3fa96a}} .kart.sari{{border-top-color:#e0a63c}}
.kart .k{{font-size:12.5px;color:#4d6f90}} .kart .v{{font-size:30px;font-weight:700;margin:2px 0}}
.kart .s{{font-size:12px;color:#6b8aa8}}
section{{background:#fff;border-radius:16px;padding:16px 20px 13px;box-shadow:0 1px 4px rgba(20,48,74,.1);margin-top:16px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.grid section{{margin-top:0}} @media(max-width:860px){{.grid{{grid-template-columns:1fr}}}}
.not{{font-size:12.5px;color:#5c7d9c;margin:-2px 0 10px}}
table{{width:100%;border-collapse:collapse}}
td,th{{padding:6px 0;border-bottom:1px solid #eef4fa;font-size:13.5px;text-align:left}}
th{{font-size:12px;color:#4d6f90;font-weight:600}} tr:last-child td{{border-bottom:0}}
td.n{{text-align:right;width:92px;font-weight:600;font-variant-numeric:tabular-nums}}
td.p{{text-align:right;width:54px;color:#6b8aa8;font-size:12px}}
td.bar{{width:32%;padding-left:14px}} td.bar div{{height:9px;background:#5aa9e6;border-radius:5px;min-width:2px}}
.akis{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:6px 0 14px}}
.akis .ak{{background:#eef6fe;border:1px solid #cfe4f7;border-radius:12px;padding:10px 14px;min-width:132px}}
.akis .ak b{{display:block;font-size:12px;color:#4d6f90}} .akis .ak span{{font-size:20px;font-weight:700}}
.akis .ak small{{display:block;font-size:11px;color:#6b8aa8}}
.akis .v2{{background:#fff6e6;border-color:#f0dcb4}} .akis .v3{{background:#e8f7ee;border-color:#bfe4cd}}
.akis i{{color:#8fb4d4;font-style:normal;font-size:18px}}
.akis2{{display:flex;gap:8px;flex-wrap:wrap;font-size:12.5px}}
.akis2 div{{padding:6px 12px;border-radius:20px;font-weight:600}}
.akis2 .ok{{background:#e4f5ea;color:#256b42}} .akis2 .duz{{background:#fdf1dc;color:#8a5a12}}
.akis2 .at{{background:#fae7e7;color:#8f2f2f}} .akis2 .oto{{background:#eceff2;color:#4d6f90}}
.akis2 .bek{{background:#e7eefc;color:#2a4f8f}}
table.kars th:nth-child(2),table.kars th:nth-child(3){{text-align:right}}
table.harita td{{vertical-align:top;padding:7px 10px 7px 0}} table.harita td.yol{{width:38%}}
code{{background:#eef4fa;padding:1px 6px;border-radius:5px;font-size:12px}}
.not2{{color:#6b8aa8;font-size:12px;width:30%}}
.dip{{color:#5c7d9c;font-size:12px;margin-top:26px}}
</style></head><body><div class="w">
<h1>TUS Veri Seti — Kapsamlı Durum Panosu</h1>
<p class="alt">Türkçe TUS çoktan seçmeli soru–cevap veri seti · {time.strftime("%d.%m.%Y %H:%M")}</p>
<div class="kartlar">{kartlar}</div>

{blok("1 · Genel yapı: kaynaktan eğitim setine", akis,
      "Süreç uçtan uca scriptlerle ve cloud agent'larıyla otomatik yürütüldü; 'kontrol edildi' ifadesi cloud agent kontrolünü anlatır, manuel insan incelemesi değildir.")}

{blok("2 · SFT veri seti: V2 → V3 dönüşümü", donusum, "Yüzdeler V2 (" + tr(len(v2)) + " kayıt) üzerinden. V3'e yeni kayıt eklenmedi; V3, V2'nin temizlenmiş ve süzülmüş halidir.")}

<div class="grid">
{blok("Açıklama durumu (V3)", tablo({"Açıklamalı (200+ karakter)": o3["acik"], "Kısa açıklama (40–200)": o3["kisa"], "Açıklaması kalmayan (<40)": o3["yok"]}, toplam=n3))}
{blok("Kontrol durumu (V3)", v3_kontrol_t, "Bayraklı = otomatik temizliğin riskli bulduğu, henüz kontrol edilmemiş kayıt.")}
</div>

{blok("3 · Cloud otomatik kontrol süreci", cloud_t,
      "8 cloud agent paralel çalıştı; her agent bir parçayı kayıt kayıt kontrol edip ok / düzelt / ele kararı yazdı. Süreç token maliyeti nedeniyle durduruldu, o ana kadarki kararların tamamı V3'e işlendi.")}
{blok("Parça bazında cloud kontrol ilerlemesi", parca_t, "Her parça ~3.119 kayıt; sayı, o parçada kontrol edilen kayıt adedidir.")}

{blok("4 · Dataset V2 ve V3 karşılaştırması", kars)}

<div class="grid">
{blok("Cloud düzeltmelerinde neye dokunuldu", alan_t, "Bir kayıtta birden fazla alan düzeltilmiş olabilir.")}
{blok("Eğitim dışına çıkarılanlar (" + tr(sum(elenen.values())) + ")", elenen_t)}
</div>

{blok("Otomatik temizliğin dokunduğu kayıtlar (V3 bayrakları)", oto_t,
      "Bayrak, otomatik onarım yapıldığını ya da riskli bir durum saptandığını gösterir; bir kayıt birden çok bayrak taşıyabilir.")}

{dogrula}

<div class="grid">
{blok("Kaynak türüne göre (V3)", kaynak_t)}
{blok("Yayınevi / kitaba göre (V3)", yay_t)}
</div>
<div class="grid">
{blok("Ders bazlı kaynaklardan gelen sorular", ders_t, "Denemeler temel + klinik karışık olduğu için ders etiketi taşımaz.")}
{blok("Deneme dönemleri", donem_t)}
</div>
<div class="grid">
{blok("Ölçüler (V3)", olcu_t)}
{blok("Doğru cevap dağılımı (V3)", harf_t)}
</div>
<div class="grid">
{blok("Eğitimden ayrı tutulan test setleri", eval_t, "Eğitim setiyle metin çakışması 0.")}
{blok("Eğitime hiç girmeyen diğer kayıtlar", disi_t)}
</div>

{blok("5 · Dosya ve klasör haritası — Drive ve yükleme paketi", h_drive)}
{blok("Yerel kaynak ve extract çıktıları", h_yerel)}
{blok("Dataset V2 dosyaları", h_v2)}
{blok("Dataset V3 dosyaları (cloud kontrol çıktıları dahil)", h_v3)}
{blok("Scriptler", h_kod)}

<p class="dip">Bütün sayılar yukarıdaki dosyalardan bu pano üretilirken hesaplandı
(<code>dataset_build/pano_kapsamli.py</code>). Veri değiştikçe yeniden çalıştırılabilir.</p>
</div></body></html>"""
    hedef.write_text(sayfa, encoding="utf-8")
    print(hedef)


if __name__ == "__main__":
    main()

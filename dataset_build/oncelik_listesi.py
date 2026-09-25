"""Kontrol edilecek kayitlari risk sirasina gore tek bir listeye dizer.

  python dataset_build/oncelik_listesi.py
  -> dataset_v3/inceleme/oncelik.txt   (karar verilmemis kayitlar, oncelikli once)

Sira:
  1) dogrulayici hatalari  (bos aciklama, bozuk sik dizisi, cok kisa aciklama, cevap uyusmazligi)
  2) bayrakli kayitlar     (asagidaki BAYRAK_SIRA sirasiyla)
  3) otomatik elenmisler   (kurtarilabilir mi diye bakilir)
  4) bayraksiz kayitlar    (dusuk riskli)
"""
import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from v3_uret import GIRDI, V3  # noqa: E402

BAYRAK_SIRA = ["aciklama_harf_celiskisi", "sik_kayip_yeniden_harf", "sik_onarimi", "soruda_gorsel",
               "aciklama_kisa", "aciklama_bozuk", "soru_bozuk", "aciklamada_cevap_satiri",
               "gomulu_soru_kesildi", "cop_cumle_atildi", "aciklama_uzun"]
CEVAP = re.compile(r"^<think>\n(.+)\n</think>\n\nDoğru cevap: ([A-E])$", re.S)
SIK = re.compile(r"^([A-E])\) (.+)$", re.M)


def hatali(r):
    u, a = r["messages"][0]["content"], r["messages"][1]["content"]
    c = CEVAP.match(a)
    if not c: return True                       # aciklama bos ya da bicim bozuk
    acik, harf = c.group(1), c.group(2)
    h = [x for x, _ in SIK.findall(u)]
    return h not in (list("ABCDE"), list("ABCD")) or harf not in h or len(acik) < 40


def main():
    karar = set()
    for f in glob.glob(str(V3 / "inceleme/kararlar*.jsonl")):
        karar |= {json.loads(l)["id"] for l in open(f, encoding="utf-8") if l.strip()}
    v3 = {r["id"]: r for r in (json.loads(l) for l in open(V3 / "sft/tus_mcq_egitim.jsonl", encoding="utf-8"))}
    sira = [json.loads(l)["id"] for l in open(GIRDI, encoding="utf-8")]      # kaynak sirasi korunur

    hata, bayrakli, elenmis, temiz = [], [], [], []
    for i in sira:
        if i in karar: continue
        r = v3.get(i)
        if r is None: elenmis.append(i); continue
        if hatali(r): hata.append(i); continue
        b = r["meta"]["v3"]["bayrak"]
        if b: bayrakli.append((min((BAYRAK_SIRA.index(x) for x in b if x in BAYRAK_SIRA), default=99), i))
        else: temiz.append(i)
    bayrakli.sort(key=lambda x: x[0])
    liste = hata + [i for _, i in bayrakli] + elenmis + temiz
    (V3 / "inceleme/oncelik.txt").write_text("\n".join(liste) + "\n", encoding="utf-8")
    print(f"karar verilmis: {len(karar)} | listeye giren: {len(liste)}")
    print(f"  1) dogrulayici hatasi : {len(hata)}")
    print(f"  2) bayrakli           : {len(bayrakli)}")
    print(f"  3) otomatik elenmis   : {len(elenmis)}")
    print(f"  4) bayraksiz          : {len(temiz)}")
    print(V3 / "inceleme/oncelik.txt")


if __name__ == "__main__":
    main()

"""SFT v3 son kontrol: bicim ve icerik denetimi. Hata varsa sifir olmayan cikis kodu.

  python dataset_build/v3_dogrula.py
"""
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from v3_temizlik import cop_orani  # noqa: E402

KOK = Path(__file__).resolve().parent.parent
E = KOK / "dataset_v3/sft/tus_mcq_egitim.jsonl"
EVAL = [KOK / "dataset_v2/eval/tus_mcq_eval.jsonl", KOK / "dataset_v2/eval/tus_mcq_eval_aciklamali.jsonl"]
CEVAP = re.compile(r"^<think>\n(.+)\n</think>\n\nDoğru cevap: ([A-E])$", re.S)
SIK = re.compile(r"^([A-E])\) (.+)$", re.M)


def anahtar(u):
    return hashlib.md5(" ".join(u.split()).lower().encode()).hexdigest()


def main():
    hata = collections.defaultdict(list); uyari = collections.defaultdict(list)
    idler = collections.Counter(); sorular = collections.Counter(); n = 0
    for l in open(E, encoding="utf-8"):
        r = json.loads(l); n += 1; i = r["id"]; idler[i] += 1
        m = r["messages"]
        if [x["role"] for x in m] != ["user", "assistant"]: hata["rol"].append(i); continue
        u, a = m[0]["content"], m[1]["content"]
        c = CEVAP.match(a)
        if not c: hata["cevap_bicimi"].append(i); continue
        acik, harf = c.group(1), c.group(2)
        siklar = SIK.findall(u)
        harfler = [h for h, _ in siklar]
        if harfler not in (list("ABCDE"), list("ABCD")): hata["sik_harfleri"].append(i)
        if harf not in harfler: hata["cevap_siklarda_yok"].append(i)
        if any(not t.strip() for _, t in siklar): hata["bos_sik"].append(i)
        govde = u[:u.find("\nA) ")] if "\nA) " in u else ""
        if len(govde.strip()) < 10: hata["govde_yok"].append(i)
        if len(set(t.strip().lower() for _, t in siklar)) < len(siklar): uyari["ayni_sik_metni"].append(i)
        if re.search(r"\$[^$]{1,80}\$|\\(?:math|frac|left|right)", u + acik): hata["latex"].append(i)
        if re.search(r"&(?:#x?[0-9a-fA-F]+|amp|lt|gt|quot|nbsp);", u + acik): hata["html"].append(i)
        if "Doğru cevap" in acik: uyari["aciklamada_dogru_cevap"].append(i)
        if len(acik) < 40: hata["aciklama_cok_kisa"].append(i)
        if len(acik) > 4000: uyari["aciklama_4000+"].append(i)
        if cop_orani(acik)[0] > .2: uyari["aciklama_bozuk>0.2"].append(i)
        if cop_orani(govde)[0] > .15: uyari["govde_bozuk>0.15"].append(i)
        tr = len(re.findall(r"[çğıöşüÇĞİÖŞÜ]", acik)); harfs = len(re.findall(r"[A-Za-zçğıöşüÇĞİÖŞÜ]", acik))
        if harfs > 200 and tr / harfs < 0.02: uyari["turkce_karakter_az"].append(i)
        sorular[anahtar(u)] += 1
    hata["tekrar_id"] = [i for i, v in idler.items() if v > 1]
    uyari["tekrar_soru"] = [k for k, v in sorular.items() if v > 1]
    ek = set(sorular)
    for f in EVAL:
        for l in open(f, encoding="utf-8"):
            r = json.loads(l)
            u = r["messages"][0]["content"] if "messages" in r else r.get("soru", "")
            if anahtar(u) in ek: hata["eval_sizintisi"].append(r["id"])
    print(f"kayit: {n}")
    print("HATALAR:", {k: len(v) for k, v in hata.items() if v} or "yok")
    print("UYARILAR:", {k: len(v) for k, v in uyari.items() if v} or "yok")
    for k, v in list(hata.items()) + list(uyari.items()):
        if v: print(f"  {k}: {v[:8]}")
    sys.exit(1 if any(hata.values()) else 0)


if __name__ == "__main__":
    main()

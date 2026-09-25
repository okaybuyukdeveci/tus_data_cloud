#!/usr/bin/env python3
"""Dataset butunluk kontrolu: sizinti, cakisma, bicim."""
import json, hashlib, sys, pathlib
KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK/"dataset_build"))
from build_sft import soru_anahtari
aid=lambda t: hashlib.sha256(soru_anahtari(t).encode()).hexdigest()[:16]
D=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else KOK/"dataset_v2")

def oku(p):
    p=D/p
    return [json.loads(l) for l in p.open(encoding="utf-8")] if p.exists() else []
def m(r): return r["messages"][0]["content"] if "messages" in r else r.get("soru","")

ham=oku("sft/tus_mcq.jsonl")
sft=oku("sft/tus_mcq_egitim.jsonl")   # NIHAI egitim dosyasi
ev=oku("eval/tus_mcq_eval.jsonl")
eva=oku("eval/tus_mcq_eval_aciklamali.jsonl"); on=oku("onarilmis/tus_mcq_onarilmis.jsonl")
it=oku("flagged/itiraz.jsonl"); at=oku("flagged/kullanilamaz.jsonl")
fl=oku("flagged/tus_mcq_flagged.jsonl")
K=lambda L:{aid(m(r)) for r in L}
S,E,EA,O,I,A = K(sft),K(ev),K(eva),K(on),K(it),K(at)
print(f"{'ham SFT (build_sft)':28} {len(ham):6}")
print(f"{'NIHAI EGITIM':28} {len(sft):6}  tekil {len(S)}")
print(f"{'eval aciklamasiz':28} {len(ev):6}")
print(f"{'eval aciklamali (holdout)':28} {len(eva):6}")
print(f"{'onarilmis (egitime eklenir)':28} {len(on):6}")
print(f"{'itiraz (egitim DISI)':28} {len(it):6}")
print(f"{'kullanilamaz (egitim DISI)':28} {len(at):6}")
print(f"{'flagged (bekleyen)':28} {len(fl):6}")
print("\n-- sizinti kontrolu (hepsi 0 olmali) --")
for ad,x in [("eval ∩ SFT",E&S),("evalAciklamali ∩ SFT",EA&S),("eval ∩ onarilmis",E&O),
             ("evalAciklamali ∩ onarilmis",EA&O),("eval ∩ evalAciklamali",E&EA),
             ("itiraz ∩ EGITIM",I&S),("kullanilamaz ∩ EGITIM",A&S),
             ("itiraz ∩ onarilmis",I&O),("kullanilamaz ∩ onarilmis",A&O)]:
    print(f"  {ad:30} {len(x)}  {'OK' if not x else '<<< SORUN'}")
kotu=[r for r in on if "<think>" not in r["messages"][1]["content"]
      or "Doğru cevap:" not in r["messages"][1]["content"]]
print(f"\nonarilmis bicim hatasi: {len(kotu)}")
print(f"\nEGITIME GIREN TOPLAM = {len(sft)}  (yinelenenler ayiklanmis)")

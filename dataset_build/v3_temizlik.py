"""SFT v3 temizlik yardimcilari: metin normalizasyonu ve sik ayristirma.

Saf fonksiyonlar; dosya okumaz/yazmaz. v3_uret.py tarafindan kullanilir.
"""
import html
import re
import unicodedata

# ------------------------------------------------------------------ LaTeX
YUNAN = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "Delta": "Δ", "epsilon": "ε",
    "varepsilon": "ε", "kappa": "κ", "lambda": "λ", "mu": "μ", "pi": "π", "sigma": "σ",
    "Sigma": "Σ", "theta": "θ", "omega": "ω", "Omega": "Ω", "tau": "τ", "phi": "φ",
    "varphi": "φ", "psi": "ψ", "Psi": "Ψ", "chi": "χ", "eta": "η", "zeta": "ζ", "rho": "ρ",
    "nu": "ν", "xi": "ξ", "iota": "ι", "Gamma": "Γ", "Theta": "Θ", "Lambda": "Λ", "Phi": "Φ",
}
SEMBOL = {
    "%": "%", "times": "×", "cdot": "·", "cdots": "…", "ldots": "…", "dots": "…",
    "geq": "≥", "ge": "≥", "geqslant": "≥", "leq": "≤", "le": "≤", "leqslant": "≤",
    "pm": "±", "mp": "∓", "neq": "≠", "ne": "≠", "approx": "≈", "sim": "~", "simeq": "≃",
    "infty": "∞", "rightarrow": "→", "to": "→", "longrightarrow": "→", "Rightarrow": "⇒",
    "leftarrow": "←", "Leftarrow": "⇐", "leftrightarrow": "↔", "rightleftharpoons": "⇌",
    "uparrow": "↑", "downarrow": "↓", "Uparrow": "↑", "Downarrow": "↓", "nearrow": "↗",
    "searrow": "↘", "circ": "°", "degree": "°", "prime": "'", "star": "*", "ast": "*",
    "div": "÷", "propto": "∝", "sqrt": "√", "partial": "∂", "sum": "Σ", "Delta": "Δ",
    "#": "#", "&": "&", "_": "_", "{": "{", "}": "}", "$": "$", "colon": ":", "mid": "|",
    "vert": "|", "lvert": "|", "rvert": "|", "langle": "⟨", "rangle": "⟩", "quad": " ",
    "qquad": " ", ",": " ", ";": " ", "!": "", " ": " ", "in": "∈", "notin": "∉",
    "cup": "∪", "cap": "∩", "subset": "⊂", "emptyset": "∅", "angle": "∠", "perp": "⊥",
    "parallel": "∥", "bullet": "•", "dagger": "†", "S": "§", "textdegree": "°",
    "hbar": "ħ", "ell": "l", "AA": "Å", "o": "ø", "O": "Ø",
}
# OCR madde isaretlerini LaTeX sembolu sanmis: anlam tasimaz -> madde imi
MADDE = {"gtrdot", "checkmark", "Lsh", "Rsh", "clubsuit", "spadesuit", "diamondsuit",
         "heartsuit", "therefore", "because", "complement", "succ", "prec", "triangleright",
         "blacktriangleright", "rhd", "lhd", "diamond", "Diamond", "square", "blacksquare",
         "Box", "boxdot", "boxtimes", "circledcirc", "circleddot", "odot", "oplus", "otimes",
         "bigstar", "maltese", "natural", "flat", "sharp", "surd", "top", "bot", "wp",
         "mho", "Finv", "Game", "eth", "digamma", "backprime", "lozenge", "blacklozenge",
         "triangle", "triangledown", "vartriangle", "bigtriangleup", "bigtriangledown",
         "curvearrowright", "curvearrowleft", "looparrowright", "twoheadrightarrow",
         "hookrightarrow", "multimap", "Vdash", "vdash", "models", "gtrless", "lessgtr",
         "ggg", "lll", "gg", "ll", "gtrsim", "lesssim", "sqsubset", "sqsupset"}
SARMALAYICI = r"(?:math(?:sf|rm|tt|bf|bb|cal|frak|it|scr|sfit|bfit)|pmb|boldsymbol|bm|textbf|" \
              r"textit|textrm|textsf|texttt|text|operatorname|mbox|hbox|underline|overline|" \
              r"bar|hat|tilde|vec|dot|ddot|widehat|widetilde|underset\{[^{}]*\}|overset\{[^{}]*\}|" \
              r"stackrel\{[^{}]*\}|mathring|check|breve|acute|grave|left|right|big|Big|bigg|Bigg|" \
              r"displaystyle|textstyle|scriptstyle|scriptscriptstyle|large|Large|small|footnotesize|" \
              r"normalsize|tiny|huge|Huge|boxed|fbox|cancel|not|mathbin|mathrel|mathop|mathord|mathpunct)"


def _grup(s, i):
    """s[i]=='{' ise eslesen '}' indeksini dondur."""
    d = 0
    for j in range(i, len(s)):
        if s[j] == "{": d += 1
        elif s[j] == "}":
            d -= 1
            if d == 0: return j
    return -1


def latex_duz(m):
    """$...$ icini duz metne cevir."""
    s = m.strip("$")
    s = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"\1/\2", s)
    s = re.sub(r"\\(?:text|mathrm|mathsf)\s*\{\s*\}", "", s)
    s = re.sub(r"\\" + SARMALAYICI + r"(?![A-Za-z])\s*", "", s)
    s = re.sub(r"\\begin\{[^}]*\}|\\end\{[^}]*\}", " ", s)
    s = re.sub(r"\\(" + "|".join(sorted(map(re.escape, MADDE), key=len, reverse=True)) + r")(?![A-Za-z])", "•", s)

    def komut(mm):
        k = mm.group(1)
        if k in YUNAN: return YUNAN[k]
        if k in SEMBOL: return SEMBOL[k]
        return ""
    s = re.sub(r"\\([A-Za-z]+|[%#&_{}$,;! ])", komut, s)
    # ust/alt indis: ^{...} _{...} ^x _x
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch in "^_":
            j = i + 1
            while j < len(s) and s[j] == " ": j += 1
            if j < len(s) and s[j] == "{":
                k = _grup(s, j)
                if k < 0: k = len(s) - 1
                ic = s[j + 1:k]; i = k + 1
            elif j < len(s):
                ic = s[j]; i = j + 1
            else:
                i = j; continue
            ic = re.sub(r"[{}]", "", ic).replace(" ", "")
            if ch == "^" and ic in ("'", "′"): out.append("'")
            elif ch == "^" and ic in ("°", "o"): out.append("°")
            else: out.append(ic)
            continue
        out.append(ch); i += 1
    s = "".join(out).replace("{", "").replace("}", "")
    s = re.sub(r"\s+", "", s)                    # OCR her simgeyi bosluklu yaziyor
    s = s.replace("HbA1•", "HbA1c")
    s = s.replace("•", " • ").replace("→", " → ").replace("⇒", " ⇒ ")
    return s


LATEX = re.compile(r"\$\$[^$]{0,300}\$\$|\$[^$\n]{0,200}\$")


def latex_temizle(t):
    t = LATEX.sub(lambda m: latex_duz(m.group(0).strip("$")), t)
    # eslesmemis $ yuzunden kalan komut artiklari: '\mathbb { M } _ { 2 }' gibi
    if "\\" in t:
        t = re.sub(r"\\[A-Za-z]+(?:\s*\{[^{}\n]{0,60}\})*(?:\s*[_^]\s*\{[^{}\n]{0,20}\})*",
                   lambda m: latex_duz(m.group(0)), t)
    if "$" in t:
        # cok satira yayilmis ya da bozuk $...$: son care - komut/parantez artiklarini temizle
        t = t.replace("$", "")
        t = re.sub(r"\\%", "%", t)
        t = re.sub(r"\\([A-Za-z]+)", lambda m: YUNAN.get(m.group(1), SEMBOL.get(m.group(1), "")), t)
        t = re.sub(r"[_^]\s*\{\s*([^{}\n]{0,15}?)\s*\}", r"\1", t)
        t = re.sub(r"\{\s*([^{}\n]{0,40}?)\s*\}", r"\1", t)
        t = t.replace("{", "").replace("}", "").replace("~", " ")
        t = re.sub(r"%\s+(?=\d)", "%", t)
        t = re.sub(r"(?<=\d) (?=\d)", "", t)
    return t


def metin_temizle(t):
    t = unicodedata.normalize("NFC", t)
    for _ in range(2):
        t = html.unescape(t)
    t = latex_temizle(t)
    t = t.replace("\u00a0", " ").replace("\u200b", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" +([,.;:!?%)])", r"\1", t)
    t = re.sub(r"\( +", "(", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# ------------------------------------------------------------------ siklar
# Sik baslangici: satir basi ya da bosluk sonrasi "A)" "a)" "(A)" "A." (A. sadece buyuk harf + bosluk)
SIK = re.compile(r"(?:(?<=^)|(?<=[\s\n]))\(?([A-Ea-e])\s?\)\s*|(?:(?<=^)|(?<=\n))([A-E])[\.]\s+")


def sik_ayir(u):
    """Soru metnini govde + siklar olarak ayir.

    Donus: (govde, [(harf, metin), ...], sorunlar)
    Sik bolgesi ilk 'A)' ile baslar. Harfler sirayla beklenir; sira disi eslesmeler
    (orn. metin icindeki 'c)' ) sik sayilmaz.
    """
    sorun = []
    ms = list(SIK.finditer(u))
    # ilk A'yi bul (buyuk/kucuk)
    bas = None
    for k, m in enumerate(ms):
        h = (m.group(1) or m.group(2)).upper()
        if h == "A":
            bas = k
            break
    if bas is None:
        return u.strip(), [], ["A_yok"]
    secili, beklenen = [], 0
    for m in ms[bas:]:
        h = (m.group(1) or m.group(2)).upper()
        idx = "ABCDE".index(h)
        if idx == beklenen or (idx > beklenen and idx <= beklenen + 2 and secili):
            if idx > beklenen:
                sorun.append("atlanan:" + "".join("ABCDE"[beklenen:idx]))
            secili.append((h, m))
            beklenen = idx + 1
            if beklenen == 5: pass
    govde = u[:secili[0][1].start()].strip()
    siklar = []
    for k, (h, m) in enumerate(secili):
        son = secili[k + 1][1].start() if k + 1 < len(secili) else len(u)
        siklar.append((h, u[m.end():son].strip()))
    if len(siklar) < 5 and not any(s.startswith("atlanan") for s in sorun):
        sorun.append(f"sik_sayisi:{len(siklar)}")
    return govde, siklar, sorun


def roma_duzelt(t):
    """OCR'nin Roma rakamlarinda I yerine l okudugu durumlar: 'Il ve III', 'I ve lI', 'lV'."""
    return re.sub(r"(?<![A-Za-zÇĞİÖŞÜçğıöşü])(?=[IlV]*l)(?=[IlV]*I)[IlV]{2,4}(?![A-Za-zÇĞİÖŞÜçğıöşü])",
                  lambda m: m.group(0).replace("l", "I"), t)


def soru_yaz(govde, siklar):
    return govde.strip() + "\n" + "\n".join(f"{h}) {roma_duzelt(t)}" for h, t in siklar)


# ---------------------------------------------------------- sik onarimi (v2)
HARF = "ABCDE"
GUCLU = {L: re.compile(r"(?:(?<=^)|(?<=[\s\n]))\(?[" + L + L.lower() + r"]\s?\)\s*") for L in HARF}
OCR_HARF = {"D": "0O", "B": "8", "E": "", "C": "", "A": ""}


def _zayif_adaylar(seg, L, ofs):
    """seg icinde L sikkinin baslangici icin zayif adaylar: (bas, metin_bas, tur)."""
    ad = []
    for m in re.finditer(r"(?:(?<=^)|(?<=[\s\n]))\(?" + L + r"(?:\s+|[\.\-:]\s*)(?=[A-ZÇĞİÖŞÜa-zçğıöşü0-9(%])", seg):
        ad.append((ofs + m.start(), ofs + m.end(), "parantezsiz"))
    for m in re.finditer(r"(?:(?<=^)|(?<=[\s\n]))" + L + r"(?=[A-ZÇĞİÖŞÜ][a-zçğıöşü])", seg):
        ad.append((ofs + m.start(), ofs + m.end(), "yapisik_harf"))
    for ch in OCR_HARF[L]:
        for m in re.finditer(r"(?:(?<=^)|(?<=[\s\n]))\(?" + re.escape(ch) + r"\s?\)\s*", seg):
            ad.append((ofs + m.start(), ofs + m.end(), "ocr_rakam"))
    for m in re.finditer(r"(?:(?<=^)|(?<=[\s\n])|(?<=[A-Za-zÇĞİÖŞÜçğıöşü0-9.,]))\)\s*(?=\S)", seg):
        once = seg[:m.start()]
        son_sik = max(once.rfind(")"), 0)
        if once.count("(", son_sik) > 0:      # 'T(11,18)' gibi kapanis parantezi
            continue
        ad.append((ofs + m.start(), ofs + m.end(), "sahipsiz_parantez"))
    return ad


def sik_onar(u):
    """Donus: (govde, [(harf, metin)], onarimlar[list[str]], sorunlar[list[str]])"""
    onarim, sorun = [], []
    # 0) iki sutunlu dizilim: 5 harf de guclu isaretle var ama sira bozuk (A C / B D E)
    qm0 = max(u.rfind("?"), 0)
    tum = []
    for L in HARF:
        ms = list(GUCLU[L].finditer(u, qm0))
        if len(ms) == 1: tum.append((ms[0].start(), ms[0].end(), L))
    if len(tum) == 5 and [x[2] for x in sorted(tum)] != list(HARF):
        tum.sort()
        govde = u[:tum[0][0]].strip()
        par = {L: u[e:(tum[k + 1][0] if k + 1 < 5 else len(u))].strip() for k, (b, e, L) in enumerate(tum)}
        return govde, [(L, par[L]) for L in HARF], ["sira:iki_sutun"], []
    # 0b) satir tabanli: son soru isaretinden sonra tam 5 dolu satir
    qs = max(u.rfind("?"), u.rfind(":"))
    if qs > 0:
        satir_bas, satirlar = [], []
        pos = u.find("\n", qs)
        if pos >= 0:
            for ln in re.finditer(r"[^\n]+", u[pos:]):
                if ln.group(0).strip(): satirlar.append((pos + ln.start(), ln.group(0)))
        if len(satirlar) == 5:
            uyum, onr = True, []
            par = []
            for k, (b, t) in enumerate(satirlar):
                L = HARF[k]
                m = re.match(r"\s*\(?([A-Ea-e0O8])\s?[\)\.]?\s*", t)
                harf_var = re.match(r"\s*\(?[A-Ea-e]\s?\)", t)
                if harf_var and harf_var.group(0).strip("( )").upper() != L:
                    uyum = False; break
                if harf_var:
                    par.append((L, t[harf_var.end():].strip()))
                else:
                    tt = re.sub(r"^\s*\)?\s*", "", t)
                    # satir basinda kalan harf: 'DÇiğneme', 'A A. facialis', 'cİki', 'B) ' kalintisi
                    tt = re.sub(r"^\(?[" + L + L.lower() + r"]\s*[\)\.]?\s*(?=[A-ZÇĞİÖŞÜ(0-9])", "", tt)
                    par.append((L, tt.strip())); onr.append(f"{L}:satir")
            if uyum and onr and all(x[1] for x in par):
                govde = u[:satirlar[0][0]].strip()
                return govde, par, onr, []
    # 1) guclu eslesmeler, sirali
    konum, bul = 0, {}
    for L in HARF:
        m = GUCLU[L].search(u, konum)
        # A icin: govdedeki 'a)' gibi yanlislari azaltmak icin, son soru isaretinden sonra ara
        if L == "A":
            qm = max(u.rfind("?\n"), u.rfind("? "), u.rfind("?"))
            if qm > 0:
                m2 = GUCLU[L].search(u, qm)
                if m2: m = m2
        if m:
            bul[L] = (m.start(), m.end(), "guclu")
            konum = m.end()
    # sira bozuklugu: bulunan konumlar artan olmali
    son = -1
    for L in HARF:
        if L in bul:
            if bul[L][0] <= son: del bul[L]
            else: son = bul[L][0]
    # ayni harf iki kez: 'D) x D) y' -> ikinci D, E eksikse E'dir
    if "E" not in bul and "D" in bul:
        m = GUCLU["D"].search(u, bul["D"][1])
        if m:
            bul["E"] = (m.start(), m.end(), "tekrar_harf"); onarim.append("E:tekrar_harf(D)")
    # 2) bosluklari doldur
    for i, L in enumerate(HARF):
        if L in bul: continue
        onceki = max([bul[x][1] for x in HARF[:i] if x in bul], default=None)
        sonraki = min([bul[x][0] for x in HARF[i + 1:] if x in bul], default=len(u))
        if L == "A" and onceki is None:
            # govde sonu: son '?' ya da ':' sonrasi satir basi
            qm = max(u.rfind("?", 0, sonraki), u.rfind(":", 0, sonraki))
            seg_bas = qm + 1 if qm >= 0 else 0
        else:
            seg_bas = onceki if onceki is not None else 0
        seg = u[seg_bas:sonraki]
        ad = [a for a in _zayif_adaylar(seg, L, seg_bas) if a[0] > seg_bas or L == "A"]
        # onceki sikkin metni bos kalmasin: adayin oncesinde en az 1 karakter olmali
        if onceki is not None:
            ad = [a for a in ad if u[onceki:a[0]].strip()]
        if ad:
            a = ad[-1] if len(ad) > 1 and L != "A" else ad[0]
            if len(ad) > 1: sorun.append(f"{L}:coklu_aday")
            bul[L] = a; onarim.append(f"{L}:{a[2]}")
        elif L == "A" and onceki is None and sonraki < len(u):
            # A harfi tamamen kayip: govdeden sonraki satir basi
            nl = u.rfind("\n", 0, sonraki)
            if nl >= 0 and u[nl + 1:sonraki].strip():
                bul[L] = (nl + 1, nl + 1, "satir_basi"); onarim.append("A:satir_basi")
    harfler = [L for L in HARF if L in bul]
    if not harfler:
        return u.strip(), [], onarim, ["sik_yok"]
    govde = u[:bul[harfler[0]][0]].strip()
    siklar = []
    for k, L in enumerate(harfler):
        s = bul[harfler[k + 1]][0] if k + 1 < len(harfler) else len(u)
        siklar.append((L, u[bul[L][1]:s].strip()))
    eksik = [L for L in HARF if L not in bul]
    # 4 sikli soru olabilir: yalniz E eksikse sorun degil, ama isaretle
    if eksik: sorun.append("eksik:" + "".join(eksik))
    if any(not t for _, t in siklar): sorun.append("bos_sik")
    return govde, siklar, onarim, sorun


# ------------------------------------------------------ Turkce karakter (deasciify)
_DEASC = None
_ASCII_KELIME = re.compile(r"(?<![A-Za-zÇĞİÖŞÜçğıöşü])[A-Za-z]{2,}(?![A-Za-zÇĞİÖŞÜçğıöşü])")


def _tr_upper(s): return s.replace("i", "İ").replace("ı", "I").upper()


def turkce_yap(t, vurgu_kucult=False, temkinli=False):
    """ASCII yazilmis Turkce kelimeleri korpus sozluguyle duzeltir (degildir -> değildir).
    vurgu_kucult: 6+ harfli, sozlukte bilinen TAMAMI BUYUK kelimeleri normal yazima cevirir
    (vurgu amacli buyuk harf; DNA/HIV gibi kisaltmalar kisa oldugu icin etkilenmez)."""
    global _DEASC
    if _DEASC is None:
        import pickle
        from pathlib import Path
        d = pickle.load(open(Path(__file__).resolve().parent.parent /
                             "dataset_v3/inceleme/deasc.pkl", "rb"))
        _DEASC = (d["best"], d["sayim"])
    best, sayim = _DEASC
    fold = str.maketrans("çğıöşüâîû", "cgiosuaiu")

    def cevir(m):
        w = m.group(0)
        low = w.lower()
        hedef = best.get(low)
        if hedef and temkinli and sayim.get(low, 0) > 0.05 * sayim.get(hedef, 1):
            return w          # ASCII hali de gercek bir kelime olabilir (on/ön, sac/saç)
        if not hedef or hedef.translate(fold) != low:
            if vurgu_kucult and w.isupper() and len(w) >= 7:   # sozlukte yok ama uzun: vurgu
                hedef = low
            else:
                return w
        if w.isupper() and len(w) > 1:
            if vurgu_kucult and (len(w) >= 6 or (len(w) >= 4 and sayim.get(hedef, 0) >= 50)):
                bas = m.start()
                once = t[:bas].rstrip()
                if not once or once[-1] in ".:;!?\n(":
                    return _tr_upper(hedef[0]) + hedef[1:]
                return hedef
            return _tr_upper(hedef)
        if w[0].isupper(): return _tr_upper(hedef[0]) + hedef[1:]
        return hedef
    return _ASCII_KELIME.sub(cevir, t)


# ------------------------------------------------------------ OCR copu temizligi
_SOZ = None
_CUMLE = re.compile(r"[^.!?\n]+[.!?]*\s*|\n")


def _soz():
    global _SOZ
    if _SOZ is None:
        import pickle
        from pathlib import Path
        d = pickle.load(open(Path(__file__).resolve().parent.parent / "dataset_v3/inceleme/deasc.pkl", "rb"))
        _SOZ = {w for w, n in d["sayim"].items() if n >= 5}
    return _SOZ


def cop_orani(t):
    V = _soz()
    w = [x.replace("İ", "i").replace("I", "ı").lower() for x in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşüâîû]{3,}", t)]
    if not w: return 0.0, 0, 0
    bil = [x in V for x in w]
    uzun = sum(1 for x, b in zip(w, bil) if not b and len(x) >= 12)
    return 1 - sum(bil) / len(w), len(w), uzun


def cop_temizle(t):
    """Anlamsiz OCR cumlelerini at. Donus: (temiz, atilan_cumle_sayisi)"""
    out, at = [], 0
    for m in _CUMLE.finditer(t):
        c = m.group(0)
        oran, n, uzun = cop_orani(c)
        if "|" in c:
            out.append(c); continue
        if (n >= 5 and oran >= 0.45) or (3 <= n <= 4 and oran >= 0.67):
            at += 1
            if c.endswith("\n"): out.append("\n")
            continue
        out.append(c)
    s = "".join(out)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip(), at


# ------------------------------------------------------- yapisik kelime ayirma
_FRK = None


def _frk():
    global _FRK
    if _FRK is None:
        import pickle
        from pathlib import Path
        _FRK = pickle.load(open(Path(__file__).resolve().parent.parent / "dataset_v3/inceleme/deasc.pkl", "rb"))["sayim"]
    return _FRK


def _low(w): return w.replace("İ", "i").replace("I", "ı").lower()


def _bol(w, derin=0):
    """Bilinmeyen kelimeyi once 2, olmazsa 3 bilinen kelimeye bol. Bolunemezse None."""
    F = _frk(); lw = _low(w)
    iki = []
    for i in range(2, len(w) - 1):
        fa, fb = F.get(lw[:i], 0), F.get(lw[i:], 0)
        if fa >= 5 and fb >= 5 and len(lw[:i]) >= 2 and len(lw[i:]) >= 2:
            iki.append((min(fa, fb), [w[:i], w[i:]]))
    if iki:
        return max(iki)[1]
    if derin:
        return None
    uc = []
    for i in range(3, len(w) - 5):
        if F.get(lw[:i], 0) >= 30:
            r = _bol(w[i:], 1)
            if r and min(F.get(_low(x), 0) for x in r) >= 30:
                uc.append((min(F.get(lw[:i], 0), *[F.get(_low(x), 0) for x in r]), [w[:i]] + r))
    return max(uc)[1] if uc else None


def yapisik_ayir(t):
    F = _frk()

    def f(m):
        w = m.group(0)
        if len(w) < 7 or w.isupper() or F.get(_low(w), 0) >= 3: return w   # TAMAMI BUYUK: kisaltma ya da vurgu, bolunmez
        p = _bol(w)
        return " ".join(p) if p else w
    return re.sub(r"[A-Za-zÇĞİÖŞÜçğıöşüâîû]{7,}", f, t)

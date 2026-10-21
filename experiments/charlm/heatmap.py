"""Add character-language-model surprise to the MDZ OCR collections (3a, 3b) of the viewer.
Each MDZ row gets surprise_bpc (bits per character over the normalised line) and char_bits
(bits for each character of the row text; null where a character is dropped by normalisation).
Run from the latinrproj root."""
import json, gzip, sys, math, unicodedata, statistics as S
from shared.io import ROOT
from . import charlm
sys.modules.setdefault("charlm", charlm)
from .charlm import BOS, EOS, UNK, SPECIAL, KEEP
m = __import__("pickle").load(open(ROOT / "models/charlm/original_kn6.pkl", "rb"))
SITE = str(ROOT / "site")

def per_char(c):
    """normalise one original character, as charlm.norm does"""
    c = "".join(SPECIAL.get(x, x) for x in c.lower())
    out = ""
    for x in unicodedata.normalize("NFKD", c):
        if unicodedata.combining(x): continue
        if x in "jvf": x = {"j": "i", "v": "u", "f": "s"}[x]
        elif x == "w": x = "uu"
        elif x.isdigit(): x = "0"
        elif x.isspace(): x = " "
        elif x in ".,:;·!?'\"()[]/*†¶§—–_=+-": x = " "
        out += x if all(ch in KEEP for ch in x) else UNK
    return out

def score(text):
    seq = []                                   # (original index, normalised char)
    for i, c in enumerate(text):
        for n in per_char(c):
            if n == " " and (not seq or seq[-1][1] == " "): continue
            seq.append((i, n))
    while seq and seq[-1][1] == " ": seq.pop()
    norm = "".join(n for _, n in seq)
    assert norm == charlm.norm(text), (norm, charlm.norm(text))
    if len(norm) < 10: return None, None
    N = m.N; s = BOS * (N - 1) + norm + EOS; bits = []
    for j in range(N - 1, len(s)):
        w = s[j] if s[j] in m.vocab else UNK
        bits.append(-math.log2(m.p(s[j - N + 1:j], w)))
    char = [None] * len(text)
    for (i, n), b in zip(seq, bits):
        if n == " ": continue
        char[i] = round((char[i] or 0) + b, 2)
    return round(sum(bits) / len(bits), 3), char

idx = json.load(open(f"{SITE}/data/index.json", encoding="utf-8"))
for ds in idx["datasets"]:
    if ds["id"] not in ("mdz-ocr-regions", "mdz-ocr-lexicon"): continue
    for p in ds["pages"]:
        path = f"{SITE}/{p['annotation']}"; rec = json.loads(gzip.open(path).read()); tb = tc = 0
        for o in rec["objects"]:
            if o["kind"] != "row" or not o.get("text"): continue
            bpc, char = score(o["text"])
            o["surprise_bpc"], o["char_bits"] = bpc, char
            if bpc is not None:
                n = sum(1 for x in char if x is not None); tb += bpc * n; tc += n
        p["surprise_bpc"] = round(tb / tc, 3) if tc else None
        with open(path, "wb") as f: f.write(gzip.compress(json.dumps(rec, ensure_ascii=False).encode(), mtime=0))
    v = [p["surprise_bpc"] for p in ds["pages"] if p["surprise_bpc"]]
    print(ds["id"], len(v), "pages, median bits/char %.2f" % S.median(v))
json.dump(idx, open(f"{SITE}/data/index.json", "w", encoding="utf-8"), ensure_ascii=False)

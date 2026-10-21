"""Character n-gram language model with interpolated Kneser-Ney smoothing (pure Python).
Text is normalised the same way for training and scoring: see norm()."""
import math, re, unicodedata, collections, pickle
BOS, EOS, UNK = "\x02", "\x03", "\x04"
SPECIAL = {"ꝑ": "p", "ꝓ": "p", "ꝗ": "q", "ꝙ": "q", "ꝯ": "9", "ꝰ": "9", "⁊": "&", "ꝝ": "r", "ꝛ": "r", "ſ": "s", "æ": "ae", "œ": "oe", "ß": "ss", "ł": "l", "đ": "d", "ħ": "h"}
KEEP = set("abcdeghiklmnopqrstuxyz0& ")
def norm(s):
    s = s.lower()
    s = "".join(SPECIAL.get(c, c) for c in s)
    s = unicodedata.normalize("NFKD", s)
    out = []
    for c in s:
        if unicodedata.combining(c): continue
        if c in "jvf": c = {"j": "i", "v": "u", "f": "s"}[c]
        elif c == "w": c = "uu"
        elif c.isdigit(): c = "0"
        elif c.isspace(): c = " "
        elif c in ".,:;·!?'\"()[]/*†¶§—–_=+-": c = " "
        if all(ch in KEEP for ch in c): out.append(c)
        else: out.append(UNK)
    return re.sub(r" +", " ", "".join(out)).strip()

class KN:
    def __init__(self, order=6, D=0.75):
        self.N, self.D = order, D
    def fit(self, lines):
        N = self.N
        raw = collections.Counter()
        for l in lines:
            s = BOS * (N - 1) + l + EOS
            for i in range(N - 1, len(s)):
                raw[s[i - N + 1:i + 1]] += 1
        self.vocab = {g[-1] for g in raw} | {UNK}
        counts = {N: raw}
        for k in range(N - 1, 0, -1):          # continuation counts from distinct (k+1)-grams
            c = collections.Counter()
            for g in counts[k + 1]: c[g[1:]] += 1
            counts[k] = c
        self.c = counts; self.tot = {}; self.typ = {}
        for k, cnt in counts.items():
            t = collections.Counter(); y = collections.Counter()
            for g, n in cnt.items(): t[g[:-1]] += n; y[g[:-1]] += 1
            self.tot[k], self.typ[k] = t, y
        self.cache = {}
        return self
    def p(self, ctx, w):
        key = (ctx, w)
        if key in self.cache: return self.cache[key]
        k = len(ctx) + 1
        if k == 1:
            t = self.tot[1].get("", 0); y = self.typ[1].get("", 0)
            pr = max(self.c[1].get(w, 0) - self.D, 0) / t + self.D * y / t / len(self.vocab)
        else:
            t = self.tot[k].get(ctx, 0)
            lower = self.p(ctx[1:], w)
            if t == 0: pr = lower
            else: pr = max(self.c[k].get(ctx + w, 0) - self.D, 0) / t + self.D * self.typ[k][ctx] / t * lower
        if len(self.cache) < 4_000_000: self.cache[key] = pr
        return pr
    def line_bits(self, l):
        """total bits and number of predicted characters (including end of line)"""
        N = self.N; s = BOS * (N - 1) + l + EOS; bits = 0.0
        for i in range(N - 1, len(s)):
            w = s[i] if s[i] in self.vocab else UNK
            bits -= math.log2(self.p(s[i - N + 1:i], w))
        return bits, len(s) - (N - 1)

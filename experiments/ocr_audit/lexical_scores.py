"""Quality of the MDZ library OCR, 102 frozen pages from 97 books (data/ocr_audit/lexical_sample.json).
No ground truth is used. Measures: share of words (4+ letters) found in a lexicon of legal Latin
(Latin Library Digest, Codex, Institutes: 56,000 forms), the same after undoing long-s read as f,
and the share of tokens that cannot be Latin (foreign script, digits inside words)."""
import re, json, glob, html, unicodedata, os, sys
from shared.io import ROOT
LEX = set(open(ROOT / "data/charlm/legal_lexicon.txt", encoding="utf-8").read().split())
def norm(w):
    w = unicodedata.normalize("NFKD", w.lower().replace("ſ", "s").replace("æ", "ae").replace("œ", "oe"))
    return "".join(c for c in w if not unicodedata.combining(c)).replace("j", "i").replace("v", "u")
def words(path):
    s = open(path, encoding="utf-8", errors="replace").read()
    lines = []
    for l in re.split(r"(?=<span[^>]*class=['\"]ocr_line)", s)[1:]:
        ws = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"class=['\"]ocrx_word['\"][^>]*>(.*?)</span>", l, flags=re.S)]
        lines.append([w for w in ws if w])
    return lines
def page_stats(path):
    lines = words(path); toks = [w for l in lines for w in l]
    n = hit = hit_f = abbr = tested = 0; junk = 0; alpha = 0
    for t in toks:
        core = t.strip(".,;:()[]!?'\"-—*†¶§/")
        if not core: continue
        n += 1
        if re.search(r"[Ͱ-ϿЀ-ӿ԰-᳿Ⰰ-꛿]", core) or (re.search(r"\d", core) and re.search(r"[A-Za-z]", core)):
            junk += 1; continue
        if not re.fullmatch(r"[A-Za-zÀ-ÿſ]+", core) or len(core) < 4: continue
        tested += 1
        if re.search(r"[ãẽĩõũñq̃]", core) or unicodedata.normalize("NFKD", core) != core: abbr += 1
        w = norm(core)
        if w in LEX: hit += 1; hit_f += 1
        elif "f" in w and (w.replace("f", "s") in LEX or any(w[:i] + "s" + w[i + 1:] in LEX for i, c in enumerate(w) if c == "f")): hit_f += 1
    return dict(lines=len(lines), tokens=n, tested=tested, hit=hit / max(1, tested), hit_f=hit_f / max(1, tested), junk=junk / max(1, n), marked=abbr / max(1, tested)), lines
if __name__ == "__main__":
    (ROOT/"outputs/lexical_scores").mkdir(parents=True, exist_ok=True)
    inv = {b["id"]: b for b in json.load(open("data/corpus/books.json", encoding="utf-8"))["books"]}
    fam = json.load(open("data/corpus/families.json")); rows = []; ex = open("outputs/lexical_scores/excerpts.txt", "w", encoding="utf-8")
    for f in json.loads((ROOT/"data/ocr_audit/lexical_sample.json").read_text(encoding="utf-8")):
        b = f.split("/")[-2]; st, lines = page_stats(f); st.update(book=b, scan=int(os.path.basename(f)[:5]), family=fam.get(b), date=inv[b]["date_sort"], work=inv[b]["work"], place=str(inv[b]["place"]))
        rows.append(st)
        body = [l for l in lines if len(l) >= 4]; m = len(body) // 2
        ex.write("### %s %s %s %s | lexicon %.2f (%.2f with f->s) junk %.3f\n" % (b, st["family"], st["date"], st["work"], st["hit"], st["hit_f"], st["junk"]))
        for l in body[m - 4:m + 4]: ex.write("  " + " ".join(l)[:150] + "\n")
    json.dump(rows, open("outputs/lexical_scores/per_book.json", "w"), indent=1)
    for r in sorted(rows, key=lambda r: r["hit_f"]):
        print("%-28s %-2s %4s %-20s lines %3d words %4d  lex %.2f  +f>s %.2f  junk %.3f  diacr %.2f" % (r["book"], r["family"], r["date"], r["work"][:20], r["lines"], r["tested"], r["hit"], r["hit_f"], r["junk"], r["marked"]))

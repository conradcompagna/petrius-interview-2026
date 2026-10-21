"""Train corpus-only KN6 models and rescore the exact 50 viewer pages."""
from pathlib import Path
import collections
import csv
import gzip
import hashlib
import json
import math
import pickle
import re
import statistics as st
import sys
import unicodedata as ud

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data/charlm"
RESULTS = ROOT / "outputs/charlm"
RESULTS.mkdir(parents=True, exist_ok=True)
MODELS = ROOT / "models/charlm"
MODELS.mkdir(parents=True, exist_ok=True)
from . import charlm
sys.modules.setdefault("charlm", charlm)

STRIP = ".,;:()[]!?\"'-—*†¶§/"
ABBR = set("ꝑꝓꝗꝙꝯꝰꝝꝛꝵꝶꝘ⁊")


def diplomatic(text):
    """Keep f, abbreviation glyphs and marks; canonicalize macron/overline to tilde."""
    text = text.lower().replace("ſ", "s").replace("æ", "ae").replace("œ", "oe")
    text = text.replace("j", "i").replace("v", "u").replace("⁊", "&")
    out = []
    for c in ud.normalize("NFD", text):
        cat = ud.category(c)
        if c in "\u0304\u0305":
            c = "\u0303"
        if cat.startswith("L") or cat.startswith("M") or cat == "Co" or c == "&":
            out.append(c)
        elif c.isdigit():
            out.append("0")
        else:
            out.append(" ")
    return ud.normalize("NFC", re.sub(r" +", " ", "".join(out)).strip())


def lex_flat(text):
    text = text.lower().replace("ſ", "s").replace("æ", "ae").replace("œ", "oe")
    return "".join(c for c in ud.normalize("NFKD", text) if not ud.combining(c)).replace("j", "i").replace("v", "u")


def mark_tolerant(text):
    """Retain an overhead-mark feature, abstracting the mark's exact Unicode shape."""
    n = ud.normalize("NFD", diplomatic(text))
    n = "".join("\u0303" if ud.category(c).startswith("M") else c for c in n)
    n = re.sub("\u0303+", "\u0303", n)
    return ud.normalize("NFC", n)


def tokens(text):
    """Keep internal digits so malformed words cannot become matches by deleting digits."""
    current = []
    for c in text:
        cat = ud.category(c)
        if cat[0] in "LMN" or cat == "Co" or c in ABBR or c == "&":
            current.append(c)
        elif current:
            word = "".join(current)
            if any(ud.category(x)[0] == "L" or x in ABBR or ud.category(x) == "Co" for x in word):
                yield word
            current = []
    if current:
        word = "".join(current)
        if any(ud.category(x)[0] == "L" or x in ABBR or ud.category(x) == "Co" for x in word):
            yield word


def latin_token(t):
    return all("LATIN" in ud.name(c, "") or ud.category(c)[0] == "M" or c in ABBR or ud.category(c) == "Co" for c in t)


def lookup(t, lex, normalizer):
    n = normalizer(t)
    return n in lex or ("f" in n and n.replace("f", "s") in lex)


def score(model, text, norm, old=False):
    n = norm(text)
    if len(n) < 10:
        return None
    if not old:
        n = "".join(c if c in model.vocab else charlm.UNK for c in n)
    bits, count = model.line_bits(n)
    return bits, count


def weighted(results):
    valid = [r for r in results if r]
    return sum(x[0] for x in valid) / sum(x[1] for x in valid) if valid else None


def train(source, name, norm):
    train_lines, held = [], []
    for r in source:
        text = r["text"]
        n = norm(text)
        if len(n) < 10:
            continue
        # The split is shared across models and independent of the OCR target pages.
        is_held = int(hashlib.sha256(charlm.norm(text).encode()).hexdigest()[:12], 16) % 20 == 0
        (held if is_held else train_lines).append(n)
    print(f"Training {name}: {len(train_lines)} lines, {sum(map(len, train_lines))} characters", flush=True)
    path = MODELS / f"{name}.pkl"
    if path.exists():
        model = pickle.loads(path.read_bytes())
    else:
        model = charlm.KN(6).fit(train_lines)
        path.write_bytes(pickle.dumps(model))
    ref = weighted([model.line_bits("".join(c if c in model.vocab else charlm.UNK for c in n)) for n in held])
    print(f"{name}: vocabulary {len(model.vocab)}, reference bits/character {ref:.4f}", flush=True)
    return model, {"train_lines": len(train_lines), "train_characters": sum(map(len, train_lines)),
                   "heldout_lines": len(held), "reference_bpc": ref, "vocabulary": len(model.vocab),
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    source_raw = [json.loads(x) for x in (DATA / "training_source.jsonl").read_text(encoding="utf-8").splitlines()]
    seen, source = set(), []
    for r in source_raw:
        key = ud.normalize("NFC", re.sub(r"\s+", " ", r["text"]).strip())
        if key not in seen:
            seen.add(key)
            source.append(r)
    old_path = MODELS / "original_kn6.pkl"
    original = pickle.loads(old_path.read_bytes())
    corpus_flat, flat_meta = train(source, "corpus_flat_kn6", charlm.norm)
    corpus_dip, dip_meta = train(source, "corpus_diplomatic_kn6", diplomatic)
    corpus_mark, mark_meta = train(source, "corpus_mark_tolerant_kn6", mark_tolerant)
    models = {"original": (original, charlm.norm, True), "corpus_flat": (corpus_flat, charlm.norm, False),
              "corpus_diplomatic": (corpus_dip, diplomatic, False),
              "corpus_mark_tolerant": (corpus_mark, mark_tolerant, False)}
    original_lex = set((DATA / "legal_lexicon.txt").read_text(encoding="utf-8").split())
    word_forms = [t for r in source for t in tokens(r["text"]) if latin_token(t)]
    flat_lex = {lex_flat(t) for t in word_forms}
    dip_lex = {diplomatic(t) for t in word_forms}
    mark_lex = {mark_tolerant(t) for t in word_forms}
    for name, lex in (("lexicon_flat", flat_lex), ("lexicon_diplomatic", dip_lex), ("lexicon_mark_tolerant", mark_lex)):
        (RESULTS / f"{name}.txt").write_text("\n".join(sorted(lex))+"\n", encoding="utf-8")
    site = ROOT / "site"
    idx = json.loads((site / "data/index.json").read_text(encoding="utf-8"))
    dataset = next(d for d in idx["datasets"] if d["id"] == "mdz-ocr-lexicon")
    pages, all_rows, all_bits = [], [], {k: [] for k in models}
    unseen = {k: collections.Counter() for k in models}
    normal_chars = collections.Counter()
    examples = []
    checks = {"saved_row_score_mismatches": 0, "saved_lex_status_mismatches": 0}
    input_hasher = hashlib.sha256()
    for page in dataset["pages"]:
        path = site / page["annotation"]
        data = path.read_bytes()
        input_hasher.update(page["key"].encode()+data)
        rec = json.loads(gzip.decompress(data))
        row_out, page_bits = [], {k: [] for k in models}
        c = collections.Counter()
        for row in rec["objects"]:
            if row["kind"] != "row" or not row.get("text"):
                continue
            text = row["text"]
            result = {"page": page["key"], "display_id": page["display_id"], "row_id": row["id"], "text": text}
            for name, (m, norm, old) in models.items():
                normalized = norm(text)
                normal_chars[name] += len(normalized)
                unseen[name].update(c for c in normalized if c not in m.vocab)
                scored = score(m, text, norm, old)
                result[name+"_bpc"] = scored[0]/scored[1] if scored else None
                page_bits[name].append(scored)
                all_bits[name].append(scored)
            if result["original_bpc"] is not None and abs(round(result["original_bpc"], 3)-row["surprise_bpc"]) > .00001:
                checks["saved_row_score_mismatches"] += 1
            old_status = row.get("lex_words", [])
            for token, status in old_status:
                core = token.strip(STRIP)
                if status is not None:
                    c["same_tested"] += 1
                    c["original_hits"] += bool(status)
                    if lookup(core, original_lex, lex_flat) != status:
                        checks["saved_lex_status_mismatches"] += 1
                    c["flat_same_hits"] += lookup(core, flat_lex, lex_flat)
                    c["diplomatic_same_hits"] += lookup(core, dip_lex, diplomatic)
                    c["mark_same_hits"] += lookup(core, mark_lex, mark_tolerant)
            expanded_tokens = list(tokens(text))
            new_status = []
            for token in expanded_tokens:
                hit_flat = lookup(token, flat_lex, lex_flat)
                hit_dip = lookup(token, dip_lex, diplomatic)
                hit_mark = lookup(token, mark_lex, mark_tolerant)
                c["all_tested"] += 1
                c["flat_all_hits"] += hit_flat
                c["diplomatic_all_hits"] += hit_dip
                c["mark_all_hits"] += hit_mark
                if not re.fullmatch(r"[A-Za-zÀ-ÿſ]+", token) or len(token) < 4:
                    c["previously_excluded_tokens"] += 1
                    c["previously_excluded_flat_hits"] += hit_flat
                    c["previously_excluded_dip_hits"] += hit_dip
                new_status.append({"token": token, "flat": hit_flat, "diplomatic": hit_dip, "mark_tolerant": hit_mark})
            result["lexicon"] = new_status
            if page["key"] == "bsb00073099/00188" and row["id"] == "row:63":
                result["original_lexicon"] = old_status
                examples.append(result)
            row_out.append(result)
            all_rows.append(result)
        p = {"display_id": page["display_id"], "key": page["key"], "book": page["book"], "scan": page["scan"],
             "rows": len(row_out), **c, **{k+"_bpc": weighted(v) for k,v in page_bits.items()},
             "original_viewer_bpc": page["surprise_bpc"]}
        for name,num,den in (("original_lex", "original_hits", "same_tested"),
                             ("flat_lex_same", "flat_same_hits", "same_tested"),
                             ("diplomatic_lex_same", "diplomatic_same_hits", "same_tested"),
                             ("mark_lex_same", "mark_same_hits", "same_tested"),
                             ("flat_lex_all", "flat_all_hits", "all_tested"),
                             ("diplomatic_lex_all", "diplomatic_all_hits", "all_tested"),
                             ("mark_lex_all", "mark_all_hits", "all_tested")):
            p[name] = c[num]/c[den] if c[den] else None
        pages.append(p)
        print(f"{page['display_id']} {page['key']}: {p['original_bpc']:.3f} -> {p['corpus_flat_bpc']:.3f} / {p['corpus_diplomatic_bpc']:.3f}", flush=True)
    if any(checks.values()):
        raise RuntimeError(f"Original replication failed: {checks}")
    fields = sorted(set().union(*(p.keys() for p in pages)))
    with (RESULTS / "per_page.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(pages)
    (RESULTS / "per_line.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in all_rows), encoding="utf-8")
    summary = {"dataset": dataset["id"], "pages": len(pages), "books": len({p['book'] for p in pages}),
               "rows": len(all_rows), "source_unique_lines": len(source), "source_raw_lines": len(source_raw),
               "input_sha256": input_hasher.hexdigest(), "replication": checks,
               "models": {"original_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(), "corpus_flat": flat_meta, "corpus_diplomatic": dip_meta, "corpus_mark_tolerant": mark_meta},
               "lexicons": {"original": len(original_lex), "corpus_flat": len(flat_lex), "corpus_diplomatic": len(dip_lex), "corpus_mark_tolerant": len(mark_lex)},
               "unseen_characters": {k: {"count": sum(v.values()), "normalized_characters": normal_chars[k],
                                         "most_common": v.most_common(12)} for k,v in unseen.items()},
               "page_results": pages, "example": examples}
    totals = {k: sum(p.get(k,0) for p in pages) for k in ("same_tested", "original_hits", "flat_same_hits", "diplomatic_same_hits", "mark_same_hits", "all_tested", "flat_all_hits", "diplomatic_all_hits", "mark_all_hits", "previously_excluded_tokens", "previously_excluded_flat_hits", "previously_excluded_dip_hits")}
    summary["totals"] = totals
    for name in models:
        summary[name] = {"pooled_bpc": weighted(all_bits[name]), "median_page_bpc": st.median(p[name+"_bpc"] for p in pages),
                         "scored_rows": sum(r is not None for r in all_bits[name])}
    summary["original_viewer_median_page_bpc"] = st.median(p['original_viewer_bpc'] for p in pages)
    summary["corpus_flat"]["pages_lower_than_original"] = sum(p['corpus_flat_bpc'] < p['original_bpc'] for p in pages)
    summary["corpus_diplomatic"]["pages_lower_than_original"] = sum(p['corpus_diplomatic_bpc'] < p['original_bpc'] for p in pages)
    summary["lex_same_pages_improved"] = sum(p['flat_lex_same'] > p['original_lex'] for p in pages)
    (RESULTS / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k not in ('page_results','example')}, indent=2), flush=True)


if __name__ == "__main__":
    main()

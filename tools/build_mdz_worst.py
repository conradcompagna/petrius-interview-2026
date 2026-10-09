"""Build the viewer collection 'MDZ OCR · 100 worst pages' from the saved OCR study outputs.
Run from the latinrproj root:  python submission/historical_latin_document_analysis/tools/build_mdz_worst.py
A: the 50 reference pages (of 97, one per MDZ book) with the highest share of OCR rows crossing printed regions.
B: the 50 survey pages (of 766, eight per book, at most two per book) with the lowest legal-Latin lexicon score."""
import json, gzip, os, re, html, sys
from collections import Counter
ROOT = os.getcwd()
SUB = os.path.join(ROOT, "submission", "historical_latin_document_analysis")
sys.path.insert(0, os.path.join(ROOT, "out", "mdz_ocr_quality"))
import measure  # LEX, norm, page_stats
DS = "mdz-ocr-worst100"
NAME = "MDZ OCR · 100 worst pages"
DESC = ("Library OCR (MDZ hOCR) drawn on the scan. Part A, 50 pages: the reference pages with the highest share of OCR rows "
        "that run across separate printed regions (red rows; reference regions outlined). Part B, 50 pages: the survey pages with "
        "the lowest share of words found in a 56,336-form legal-Latin lexicon (red rows: under 25% of their words found). "
        "Measurements were run and reported by LLM agents; selection is by those measurements only.")

def hocr_lines(path):
    s = open(path, encoding="utf-8", errors="replace").read()
    m = re.search(r"ocr_page['\"][^>]*bbox (\d+) (\d+) (\d+) (\d+)", s)
    size = (int(m.group(3)), int(m.group(4))) if m else None
    out = []
    for chunk in re.split(r"(?=<span[^>]*class=['\"]ocr_line)", s)[1:]:
        b = re.search(r"bbox (\d+) (\d+) (\d+) (\d+)", chunk)
        ws = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"class=['\"]ocrx_word['\"][^>]*>(.*?)</span>", chunk, flags=re.S)]
        ws = [w for w in ws if w]
        if b and ws:
            out.append((list(map(int, b.groups())), " ".join(ws), ws))
    return size, out

def line_lex(ws):
    t = h = 0
    for w in ws:
        core = w.strip(".,;:()[]!?'\"-—*†¶§/")
        if len(core) < 4 or not re.fullmatch(r"[A-Za-zÀ-ÿſ]+", core): continue
        t += 1; n = measure.norm(core)
        if n in measure.LEX or ("f" in n and n.replace("f", "s") in measure.LEX): h += 1
    return t, h

def obj(i, kind, label, bbox, text="", note="", mistake=False, poly=None):
    x0, y0, x1, y1 = bbox
    poly = poly or [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
    return dict(id=f"{kind}:{i}", source_id=str(i), kind=kind, label=label, polygon=poly, bbox=bbox, geometry_type="polygon", holes=[],
                components=[], line_ids=[], baseline=None, input_line_refs=[], subtype=None, parent=None, draft=False, text=text,
                certainty="", probabilities={}, note=note, review_status="measurement", mistake=mistake, reading_order=i)

def page(book, scan, size, objects, part, note, src):
    url = f"https://api.digitale-sammlungen.de/iiif/image/v2/{book}_{scan:05d}/full/full/0/default.jpg"
    counts = Counter(o["label"] for o in objects)
    rec = dict(dataset=DS, dataset_name=NAME, kind="ocr", key=f"{book}/{scan:05d}", book=book, scan=scan, pending=False,
               semantic_labels_assigned=False, provenance=None, has_ocr=True, page_notes=note, title=titles.get(book, book),
               image_path=url, image=dict(width=size[0], height=size[1]), objects=objects, counts=dict(counts), description=DESC,
               sources=[src], flags=[], page_type=None, note=note, image_url=url, source_url=url)
    return rec, part

titles = {}
try:
    for b in json.load(open(os.path.join(ROOT, "corpus", "benchmark_inventory.json"), encoding="utf-8"))["books"]:
        titles[b["id"]] = (b.get("title") or b.get("short_title") or b["id"])[:160]
except Exception:
    pass

records = []
# ---- A: region structure
diag = json.load(open(os.path.join(ROOT, "out", "findings_audit_20261006", "region_diagnostics.json"), encoding="utf-8"))
diag = [d for d in diag if d["lines"] >= 30]
diag.sort(key=lambda d: -d["cross_region_lines"] / d["lines"])
seen = set()
for d in diag[:50]:
    book, scan = d["book"], d["scan"]
    hp = os.path.join(ROOT, d["hocr"].replace("\\", "/"))
    size, lines = hocr_lines(hp)
    ref = json.load(open(os.path.join(ROOT, d["reference"].replace("\\", "/")), encoding="utf-8"))
    objs = []
    for k, r in enumerate(ref["regions"]):
        sp = r.get("source_polygon") or r["polygon"]
        xs, ys = [p[0] for p in sp], [p[1] for p in sp]
        lab = {"main_text": "main_text", "gloss": "gloss", "header": "header", "footer": "footer", "marginalia": "marginalia", "initial": "initial"}.get(r.get("role"), "text_region")
        objs.append(obj(k, "region", lab, [min(xs), min(ys), max(xs), max(ys)], note=f"reference region {r['id']} ({r.get('role')})", poly=sp + [sp[0]]))
    flagged = {tuple(map(int, f["bbox"])): f for f in d["line_flags"]}
    for k, (b, text, ws) in enumerate(lines):
        f = flagged.get(tuple(b))
        objs.append(obj(k, "row", "cross_region" if f else "ocr_row", b, text,
                        note=("OCR row runs across regions " + ", ".join(f["regions"])) if f else "", mistake=bool(f)))
    note = (f"Part A · region structure. {d['cross_region_lines']} of {d['lines']} OCR rows "
            f"({100*d['cross_region_lines']/d['lines']:.0f}%) run across separate reference regions; {d['mixed_blocks']} hOCR blocks span regions.")
    records.append(page(book, scan, size, objs, "A", note, d["hocr"].replace("\\", "/")))
    seen.add((book, scan))

# ---- B: recognition
sv = os.path.join(ROOT, "out", "mdz_ocr_quality", "survey5")
scores = []
for f in sorted(os.listdir(sv)):
    m = re.fullmatch(r"(bsb\d+)_(\d+)\.hocr", f)
    if not m: continue
    st, _ = measure.page_stats(os.path.join(sv, f))
    if st["lines"] < 30 or st["tested"] < 200: continue
    scores.append((st["hit_f"], m.group(1), int(m.group(2)), st))
scores.sort()
perbook = Counter(); nB = 0
for hit, book, scan, st in scores:
    if nB == 50: break
    if perbook[book] == 2 or (book, scan) in seen: continue
    perbook[book] += 1; nB += 1
    size, lines = hocr_lines(os.path.join(sv, f"{book}_{scan:05d}.hocr"))
    objs = []
    for k, (b, text, ws) in enumerate(lines):
        t, h = line_lex(ws)
        bad = t >= 3 and h / t < 0.25
        objs.append(obj(k, "row", "low_lexicon" if bad else "ocr_row", b, text,
                        note=f"{h} of {t} words of 4+ letters found in the lexicon" if t else "", mistake=bad))
    note = (f"Part B · recognition. {100*hit:.0f}% of {st['tested']} words of four or more letters are found in the legal-Latin lexicon "
            f"(long s read as f repaired); red rows have under 25%.")
    records.append(page(book, scan, size, objs, "B", note, f"out/mdz_ocr_quality/survey5/{book}_{scan:05d}.hocr"))

# ---- write into the static site
site = os.path.join(SUB, "site", "data")
idx_path = os.path.join(site, "index.json")
idx = json.load(open(idx_path, encoding="utf-8"))
entries = []
for i, (rec, part) in enumerate(records):
    rel = f"data/pages/{DS}/{rec['book']}/{rec['scan']:05d}.json.gz"
    os.makedirs(os.path.dirname(os.path.join(SUB, "site", rel)), exist_ok=True)
    with open(os.path.join(SUB, "site", rel), "wb") as fh:
        fh.write(gzip.compress(json.dumps(rec, ensure_ascii=False).encode("utf-8"), mtime=0))
    entries.append(dict(key=rec["key"], book=rec["book"], scan=rec["scan"], title=rec["title"], sequence=i, display_id=f"{part}{i % 50 + 1:02d}",
                        split=("A · region structure" if part == "A" else "B · recognition"), semantic_units=0, ocr_ready=True, counterparts=[],
                        annotation=rel, image_url=rec["image_url"], text_url=None, source_url=rec["source_url"]))
ds = dict(id=DS, name=NAME, kind="ocr", description=DESC, group="finished", completed_pages=len(entries), pages=entries)
idx["datasets"] = [d for d in idx["datasets"] if d["id"] != DS]
pos = max([i for i, d in enumerate(idx["datasets"]) if d.get("group") == "finished"], default=-1) + 1
idx["datasets"].insert(pos, ds)
json.dump(idx, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False)
print("pages", len(entries), "A", sum(p == "A" for _, p in records), "B", sum(p == "B" for _, p in records))
print("worst A", records[0][0]["page_notes"]); print("worst B", [r for r, p in records if p == "B"][0]["page_notes"])

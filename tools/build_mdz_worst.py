"""Build the viewer collection 'MDZ OCR · 100 worst pages' from the saved OCR study outputs.
Run from the latinrproj root:  python submission/historical_latin_document_analysis/tools/build_mdz_worst.py
A: the 50 pages (of the 120 reviewed region-annotation pages) with the highest share of OCR rows crossing annotated regions.
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
        "that run across separate printed regions, measured on the 120 reviewed region-annotation pages (red rows; annotated regions and MDZ paragraphs outlined). Part B, 50 pages: the survey pages with "
        "the lowest share of words found in a 56,336-form legal-Latin lexicon (red rows: under 25% of their words found). "
        "")

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

def hocr_pars(path):
    s = open(path, encoding="utf-8", errors="replace").read()
    return [list(map(int, m.groups())) for m in re.finditer(r"class=['\"]ocr_par['\"][^>]*bbox (\d+) (\d+) (\d+) (\d+)", s)]

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
# ---- A: region structure, on the 120 reviewed region-annotation pages (the D-FINE dataset)
study = json.load(open(os.path.join(ROOT, "out", "region_study_120_v1", "pages.json"), encoding="utf-8"))
study = [d for d in study if d["rows"] >= 30]
study.sort(key=lambda d: -d["cross_region_rows"] / d["rows"])
seen = set()
for d in study[:50]:
    book, scan = d["book"], d["scan"]
    hp = os.path.join(ROOT, d["hocr"])
    size, lines = hocr_lines(hp)
    ann = json.load(open(os.path.join(ROOT, "out", "original_region_annotations120_v1", d["partition"], book, f"{scan:05d}.json"), encoding="utf-8"))
    fx, fy = size[0] / ann["image"]["width"], size[1] / ann["image"]["height"]
    objs = []
    for k, r in enumerate(ann["regions"]):
        sp = [[x * fx, y * fy] for x, y in r["polygon"]]
        xs, ys = [q[0] for q in sp], [q[1] for q in sp]
        objs.append(obj(k, "region", "text_region", [min(xs), min(ys), max(xs), max(ys)], note=f"annotated region {r['id']}", poly=sp + [sp[0]]))
    for k, pb in enumerate(hocr_pars(hp)):
        objs.append(obj(1000 + k, "region", "mdz_paragraph", pb, note="MDZ hOCR paragraph"))
    flagged = {tuple(int(v) for v in f["bbox"]): f for f in d["row_flags"]}
    for k, (bb, text, ws) in enumerate(lines):
        f = flagged.get(tuple(bb))
        objs.append(obj(k, "row", "cross_region" if f else "ocr_row", bb, text,
                        note=("OCR row runs across regions " + ", ".join(f["regions"])) if f else "", mistake=bool(f)))
    note = (f"Part A · region structure. {d['cross_region_rows']} of {d['rows']} OCR rows "
            f"({100*d['cross_region_rows']/d['rows']:.0f}%) run across separate annotated regions; {d['mixed_blocks']} hOCR blocks span regions.")
    records.append(page(book, scan, size, objs, "A", note, d["hocr"]))
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
    objs = [obj(1000 + k, "region", "mdz_paragraph", pb, note="MDZ hOCR paragraph") for k, pb in enumerate(hocr_pars(os.path.join(sv, f"{book}_{scan:05d}.hocr")))]
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
DSETS = {"A": ("mdz-ocr-regions", "MDZ OCR · rows across regions · 50 pages"),
         "B": ("mdz-ocr-lexicon", "MDZ OCR · lexicon test · 50 pages")}
idx["datasets"] = [d for d in idx["datasets"] if d["id"] not in (DS, "mdz-ocr-regions", "mdz-ocr-lexicon")]
pos = max([i for i, d in enumerate(idx["datasets"]) if d.get("group") == "finished"], default=-1) + 1
for part in "AB":
    dsid, dsname = DSETS[part]; entries = []
    for rec, pp in records:
        if pp != part: continue
        rec = dict(rec, dataset=dsid, dataset_name=dsname)
        rel = f"data/pages/{dsid}/{rec['book']}/{rec['scan']:05d}.json.gz"
        os.makedirs(os.path.dirname(os.path.join(SUB, "site", rel)), exist_ok=True)
        with open(os.path.join(SUB, "site", rel), "wb") as fh:
            fh.write(gzip.compress(json.dumps(rec, ensure_ascii=False).encode("utf-8"), mtime=0))
        entries.append(dict(key=rec["key"], book=rec["book"], scan=rec["scan"], title=rec["title"], sequence=len(entries), display_id=f"{part}{len(entries)+1:02d}",
                            split="", semantic_units=0, ocr_ready=True, counterparts=[],
                            annotation=rel, image_url=rec["image_url"], text_url=None, source_url=rec["source_url"]))
    idx["datasets"].insert(pos, dict(id=dsid, name=dsname, kind="ocr", description="", group="finished", completed_pages=len(entries), pages=entries)); pos += 1
json.dump(idx, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False)
print("pages", len(records), "A", sum(p == "A" for _, p in records), "B", sum(p == "B" for _, p in records))
print("worst A", records[0][0]["page_notes"]); print("worst B", [r for r, p in records if p == "B"][0]["page_notes"])

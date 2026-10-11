"""Build the viewer collections cited in the note that are not produced elsewhere.
Run from the latinrproj root: python submission/historical_latin_document_analysis/tools/build_note_collections.py
- parser-transfer: the first parser on 12 sampled pages from each of eleven other editions (out/transfer_baseline).
- stock-models: a few pages from each stock region/line/OCR model, grouped by page.
Then orders and names every collection."""
import json, gzip, os, sys, shutil, hashlib
ROOT = os.getcwd(); SITE = os.path.join(ROOT, "submission", "historical_latin_document_analysis", "site")
sys.path.insert(0, ROOT)
from annotation_viewer.server import Catalog
idx_path = os.path.join(SITE, "data", "index.json"); idx = json.load(open(idx_path, encoding="utf-8"))
by = {d["id"]: d for d in idx["datasets"]}

def write(ds, key, rec):
    rel = f"data/pages/{ds}/{hashlib.sha1(key.encode()).hexdigest()[:16]}.json.gz"
    os.makedirs(os.path.dirname(os.path.join(SITE, rel)), exist_ok=True)
    with open(os.path.join(SITE, rel), "wb") as f: f.write(gzip.compress(json.dumps(rec, ensure_ascii=False).encode(), mtime=0))
    return rel

# ---- parser transfer
cat = Catalog.__new__(Catalog); cat.datasets = {}; cat.titles = {}; cat.warnings = []
cat.add_dataset("parser-transfer", "", "prediction", "")
inv = {b["id"]: b for b in json.load(open(os.path.join(ROOT, "corpus", "pilot.json"), encoding="utf-8"))["books"]}
pages = []
for book in sorted(os.listdir(os.path.join(ROOT, "out", "transfer_baseline"))):
    pdir = os.path.join(ROOT, "out", "transfer_baseline", book, "pages")
    if book == "bsb10144443" or not os.path.isdir(pdir): continue
    for f in sorted(os.listdir(pdir)):
        scan = int(f[:-5]); key = f"{book}/{scan:05d}"
        cat.add_page("parser-transfer", book, scan, annotation=f"out/transfer_baseline/{book}/pages/{f}",
                     image=f"data/{book}/images/{scan:05d}.jpg", adapter="legacy", split="")
        rec = cat.page("parser-transfer", key)
        rec = dict(rec, dataset="parser-transfer")
        if book.startswith("bsb"):
            url = f"https://api.digitale-sammlungen.de/iiif/image/v2/{book}_{scan:05d}/full/full/0/default.jpg"
        else:
            src = os.path.join(ROOT, "data", book, "images", f"{scan:05d}.jpg")
            name = hashlib.sha1(key.encode()).hexdigest()[:24] + ".jpg"
            os.makedirs(os.path.join(SITE, "data", "images"), exist_ok=True); shutil.copyfile(src, os.path.join(SITE, "data", "images", name))
            url = f"data/images/{name}"
        rec["image_url"] = url; rec["image_path"] = url
        b = inv.get(book, {}); title = b.get("short_title") or b.get("title") or book
        rel = write("parser-transfer", key, rec)
        pages.append(dict(key=key, book=book, scan=scan, title=title, sequence=len(pages), display_id="", split=title[:40],
                          semantic_units=0, ocr_ready=True, counterparts=[], annotation=rel, image_url=url, text_url=None, source_url=url))
idx["datasets"] = [d for d in idx["datasets"] if d["id"] != "parser-transfer"]
idx["datasets"].append(dict(id="parser-transfer", name="", kind="prediction", description="", group="finished", completed_pages=len(pages), pages=pages))

# ---- stock models, grouped by page
groups = [(["bsb00026118/00051", "bsb00053599/00443"], [("ocr-test100", "Kraken"), ("seg-surya", "Surya"), ("seg-ppocr", "PaddleOCR"), ("seg-ppdoclayout", "PP-DocLayoutV3"), ("seg-qwen3-vl-8b", "Qwen3-VL-8B")]),
          (["bsb00065906/00224", "bsb10488451/00390"], [("seg-pero-random10", "PERO"), ("seg-eynollah-random10", "Eynollah"), ("seg-orli-random10", "Orli")])]
if "stock-models" not in by or True:
    pages = []
    for keys, models in groups:
        for ds, model in models:
            for k in keys:
                src = next(p for p in by[ds]["pages"] if p["key"] == k)
                rec = json.loads(gzip.open(os.path.join(SITE, src["annotation"])).read())
                key = f"{k}/{model}"
                rec = dict(rec, dataset="stock-models", key=key, dataset_name=model)
                rel = write("stock-models", key, rec)
                pages.append(dict(src, key=key, display_id=model, split="", sequence=len(pages), annotation=rel, text_url=None, counterparts=[]))
    idx["datasets"] = [d for d in idx["datasets"] if d["id"] != "stock-models"]
    idx["datasets"].append(dict(id="stock-models", name="", kind="segmentation", description="", group="finished", completed_pages=len(pages), pages=pages))

order = [("finished-task1-min", "1 · Task I program · task pages"),
         ("legacy-gold-review", "2a · First parser · same book (1582 Decretals)"),
         ("parser-transfer", "2b · First parser · eleven other editions"),
         ("mdz-ocr-regions", "3a · MDZ library OCR · rows crossing regions"),
         ("mdz-ocr-lexicon", "3b · MDZ library OCR · lowest lexicon scores"),
         ("stock-models", "4 · Stock layout and OCR models · sample pages"),
         ("finished-region-data", "5a · Region annotations · training data"),
         ("finished-region-eval", "5b · D-FINE region detector · held-out pages"),
         ("finished-neural-data", "6a · Line annotations · training data"),
         ("finished-neural-eval", "6b · Neural tagger · held-out pages"),
         ("finished-interview", "6c · Full pipeline (D-FINE, PERO, tagger) · task pages")]
by = {d["id"]: d for d in idx["datasets"]}
idx["datasets"] = [dict(by[i], name=n, group="finished") for i, n in order if i in by]
json.dump(idx, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False)
keep = {i for i, _ in order}
for x in os.listdir(os.path.join(SITE, "data", "pages")):
    if x not in keep: shutil.rmtree(os.path.join(SITE, "data", "pages", x))
used = {p["image_url"] for d in idx["datasets"] for p in d["pages"]}
for f in os.listdir(os.path.join(SITE, "data", "images")):
    if f"data/images/{f}" not in used: os.remove(os.path.join(SITE, "data", "images", f))
for d in idx["datasets"]: print(d["name"], len(d["pages"]))

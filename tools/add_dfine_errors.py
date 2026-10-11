"""Mark D-FINE errors on the 20 held-out pages (collection 5b), from the saved evaluation matches at IoU 0.50.
Extra detections are flagged as mistakes; annotated regions with no match are added as 'missed region'.
Run from the latinrproj root."""
import json, gzip, os
SITE = "submission/historical_latin_document_analysis/site"
idx = json.load(open(f"{SITE}/data/index.json", encoding="utf-8"))
ds = next(d for d in idx["datasets"] if d["id"] == "finished-region-eval")
tp = fp = fn = 0
for p in ds["pages"]:
    ev = json.load(open(f"out/submission_final_20261007/dfine_eval/{p['key']}.json", encoding="utf-8"))
    m = ev["metrics_at_50"]; matched = {a: b for a, b, _ in m["matched"]}
    ann = json.load(open(f"out/original_region_annotations120_v1/evaluation/{p['key']}.json", encoding="utf-8"))
    path = f"{SITE}/{p['annotation']}"; rec = json.loads(gzip.open(path).read())
    rec["objects"] = [o for o in rec["objects"] if o["label"] != "missed_region"]
    det = [r["id"] for r in ev["regions"]]
    for o in rec["objects"]:
        if o["kind"] == "region" and o["source_id"] in det:
            i = det.index(o["source_id"]); o["mistake"] = i not in matched; o["mistake_reason"] = ""
    hit = set(matched.values())
    for j, r in enumerate(ann["regions"]):
        if j in hit: continue
        xs = [q[0] for q in r["polygon"]]; ys = [q[1] for q in r["polygon"]]
        rec["objects"].append(dict(id=f"region:missed_{r['id']}", source_id=r["id"], kind="region", label="missed_region",
            polygon=r["polygon"] + [r["polygon"][0]], bbox=[min(xs), min(ys), max(xs), max(ys)], geometry_type="polygon", holes=[],
            components=[], line_ids=[], baseline=None, input_line_refs=[], subtype=None, parent=None, draft=False, text="",
            probabilities={}, note="", counts_as_task_unit=True, reading_order=None, mistake=True, mistake_reason=""))
    tp += m["tp"]; fp += m["fp"]; fn += m["fn"]
    with open(path, "wb") as f: f.write(gzip.compress(json.dumps(rec, ensure_ascii=False).encode(), mtime=0))
print("matched", tp, "extra", fp, "missed", fn, "F1", round(2 * tp / (2 * tp + fp + fn), 4))

"""Apply both final trained taggers to D-FINE/PERO page JSON.

Usage: python inference/neural/predict.py OUT_DIR page.json [page.json ...]
The main inference/run.py pipeline prepares these inputs from local page images.
"""
import sys, os, json, numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from .runtime import HERE, ROLE, Lines, Regions
from .extract import page_arrays


def main(out, files, model="full", device="auto"):
    from . import runtime
    runtime.DEV = torch.device("cuda" if device == "auto" and torch.cuda.is_available() else "cpu" if device == "auto" else device)
    ck = torch.load(os.path.join(HERE, "..", "..", "models", "neural", "v3.pt"), map_location="cpu"); voc = ck["vocab"]
    pages = [json.load(open(f, encoding="utf-8")) for f in files]; LL, RR = None, None
    for p in pages:
        L, R, _ = page_arrays(p, labels=False)
        LL = L if LL is None else {k: LL[k] + L[k] for k in L}; RR = R if RR is None else {k: RR[k] + R[k] for k in R}
    obj = ("text", "key", "rid", "lid", "review")
    d = {k: np.array(v, str) if k in obj else np.array(v, np.uint8 if k == "X" else np.float32) for k, v in LL.items()}
    d.update({"R_" + k: np.array(v, str) if k in obj else np.array(v, np.uint8 if k == "T" else np.float32) for k, v in RR.items()})
    d["coords"] = np.concatenate([d["lbox"] / np.tile(d["page"], 2), d["rbox"] / np.tile(d["page"], 2)], 1).astype(np.float32)
    d["R_coords"] = (d["R_box"] / np.tile(d["R_page"], 2)).astype(np.float32); d["R_y"] = np.zeros(len(d["R_rid"]), np.int64)
    dup = d["R_ruledup"].astype(bool); ridx = {(k, r): i for i, (k, r) in enumerate(zip(d["R_key"], d["R_rid"]))}
    by_page, lines_of = {}, {}
    for i in np.where(~dup)[0]: by_page.setdefault(d["R_key"][i], []).append(int(i))
    for i, (k, r) in enumerate(zip(d["key"], d["rid"])): lines_of.setdefault(ridx[(k, r)], []).append(i)
    R = Regions(d, voc); R.model.load_state_dict(ck["regions"]); rp = R.predict(list(by_page.values()))
    L = Lines(d, voc); L.model.load_state_dict(ck["lines"])
    seqs = [s for s in ([i for r in rr if rp[r] >= 0.5 for i in lines_of[r]] for rr in by_page.values()) if s]
    lp = L.predict(seqs) if seqs else {}
    lab = {(d["key"][i], d["lid"][i]): (ROLE[int(q.argmax())], float(q.max())) for i, q in lp.items()}
    for p in pages:
        k = p["key"]; dropped = sorted(d["R_rid"][i] for i in np.where(dup)[0] if d["R_key"][i] == k)
        prob = {d["R_rid"][i]: rp[i] for i in by_page.get(k, [])}
        res = {"key": k, "image": p["image"], "model": "line_nn_v3/" + model, "duplicate_regions_dropped": dropped,
               "regions": [{"id": r["id"], "bbox": r["bbox"], "central_probability": prob.get(r["id"]), "central": prob.get(r["id"], 0) >= 0.5} for r in p["regions"]],
               "lines": [{"id": l["id"], "region_id": l.get("region_id") or l["region_ids"][0], "bbox": l["bbox"], "text": l.get("text"),
                          "label": lab.get((k, l["id"]), ("outside", None))[0], "confidence": lab.get((k, l["id"]), ("outside", None))[1]} for l in p["lines"]]}
        f = os.path.join(out, k + ".json"); os.makedirs(os.path.dirname(f), exist_ok=True)
        json.dump(res, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        c = {}
        for l in res["lines"]: c[l["label"]] = c.get(l["label"], 0) + 1
        print(k, c, "duplicates dropped", len(dropped), flush=True)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("model=")]; m = [x[6:] for x in sys.argv[1:] if x.startswith("model=")]
    main(a[0], a[1:], m[0] if m else "full")

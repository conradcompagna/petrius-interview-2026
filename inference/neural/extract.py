"""line_nn_v3 inputs for the 120-page set: colour line strips, colour region thumbnails, raw OCR text, raw coordinates, labels.
Run from the repository root:  python line_nn_v3/extract.py [book ...]   ->  line_nn_v3/work/<book>.npz
Steps 4-5 and 7 of the pipeline: duplicate rule (flag only, nothing is deleted here), page rescaled so that its commonest
letter height is 10 px, one 40 x 384 colour strip per line, one 128 x 128 colour window per region (centre of the box).
Channel order is OpenCV's (blue, green, red) everywhere."""
import json, glob, os, sys
import cv2, numpy as np

H, W, UNIT, TH = 40, 384, 10.0, 128
LAB = ["text", "summarium", "inscriptio", "other", "outside"]
SRC = "out/central_block_annotations_v1/predictions"
DUP = "line_nn_v2/work/duplicates.json"


def unit_height(gray):
    ink = cv2.adaptiveThreshold(gray, 1, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 51, 25)
    st = cv2.connectedComponentsWithStats(ink, connectivity=8)[2][1:]
    h = st[(st[:, 4] >= 12) & (st[:, 3] >= 8) & (st[:, 3] <= 60), 3]
    hist = np.convolve(np.bincount(h, minlength=61).astype(float), [1, 2, 1], mode="same")
    return float(np.argmax(hist))


def rescale(bgr):
    u = unit_height(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)); s = UNIT / u
    im = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return im, s, u, np.median(im.reshape(-1, 3), 0).astype(np.uint8)


def strip(im, bg, s, box):
    x0, y0, x1, y1 = [int(round(v * s)) for v in box]
    out = np.empty((H, W, 3), np.uint8); out[:] = bg
    cy = (y0 + y1) // 2
    a, b = max(y0, cy - H // 2, 0), min(y1, cy + H // 2, im.shape[0])
    c = im[a:b, max(x0, 0):min(x1, x0 + W, im.shape[1])]
    if c.size:
        out[a - (cy - H // 2):a - (cy - H // 2) + c.shape[0], :c.shape[1]] = c
    return out, min(W, max(1, x1 - x0))


def thumb(im, bg, s, box):
    """TH x TH window on the centre of the region; pixels outside the region are background."""
    x0, y0, x1, y1 = [int(round(v * s)) for v in box]
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, im.shape[1]), min(y1, im.shape[0])
    out = np.empty((TH, TH, 3), np.uint8); out[:] = bg
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    a, b, c, d = max(y0, cy - TH // 2), min(y1, cy + TH // 2), max(x0, cx - TH // 2), min(x1, cx + TH // 2)
    if b > a and d > c:
        out[a - (cy - TH // 2):b - (cy - TH // 2), c - (cx - TH // 2):d - (cx - TH // 2)] = im[a:b, c:d]
    return out


def liou(a, b):
    a, b = np.array(a, np.float32), np.array(b, np.float32)
    ix = np.clip(np.minimum(a[:, None, 2], b[None, :, 2]) - np.maximum(a[:, None, 0], b[None, :, 0]), 0, None)
    iy = np.clip(np.minimum(a[:, None, 3], b[None, :, 3]) - np.maximum(a[:, None, 1], b[None, :, 1]), 0, None)
    i = ix * iy
    return i / (((a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1]))[:, None] + ((b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1]))[None] - i + 1e-6)


def duplicate_regions(regions, lines):
    """Step 4. A region is a duplicate detection when at least half of its lines have a twin line (box IoU >= 0.4) in one region with more lines."""
    lb = {}
    for l in lines:
        lb.setdefault(l.get("region_id") or l["region_ids"][0], []).append(l["bbox"])
    area = {r["id"]: (r["bbox"][2] - r["bbox"][0]) * (r["bbox"][3] - r["bbox"][1]) for r in regions}
    rank = sorted(lb, key=lambda r: (-len(lb[r]), -area[r], r)); drop = set()
    for n, r in enumerate(rank):
        for q in rank[:n]:
            if q not in drop and (liou(lb[r], lb[q]).max(1) >= 0.4).mean() >= 0.5:
                drop.add(r); break
    return drop


def page_arrays(d, labels=True):
    """d: viewer page JSON (regions, lines, image). Returns line arrays and region arrays for one page."""
    bgr = cv2.imread(d["image"]["path"].replace("\\", "/"), 1)
    assert bgr is not None and bgr.shape[:2] == (d["image"]["height"], d["image"]["width"]), d["key"]
    im, s, u, bg = rescale(bgr); pw, ph = d["image"]["width"], d["image"]["height"]
    reg = {r["id"]: r for r in d["regions"]}; rule = duplicate_regions(d["regions"], d["lines"])
    L = {k: [] for k in ("X", "w", "y", "text", "key", "rid", "lid", "lbox", "rbox", "page", "review")}; by = {}
    for l in d["lines"]:
        rid = l.get("region_id") or l["region_ids"][0]; x, w = strip(im, bg, s, l["bbox"]); by.setdefault(rid, []).append(l)
        L["X"].append(x); L["w"].append(w); L["y"].append(LAB.index(l["label"]) if labels else 4); L["text"].append(l.get("text") or "")
        L["key"].append(d["key"]); L["rid"].append(rid); L["lid"].append(l["id"]); L["lbox"].append(l["bbox"]); L["rbox"].append(reg[rid]["bbox"])
        L["page"].append([pw, ph]); L["review"].append(l.get("review_status", ""))
    R = {k: [] for k in ("T", "key", "rid", "box", "page", "text", "y", "ruledup", "nlines")}
    for rid, ls in by.items():
        ls = sorted(ls, key=lambda l: l["bbox"][1] + l["bbox"][3])
        R["T"].append(thumb(im, bg, s, reg[rid]["bbox"])); R["key"].append(d["key"]); R["rid"].append(rid); R["box"].append(reg[rid]["bbox"]); R["page"].append([pw, ph])
        R["text"].append(" ".join((l.get("text") or "") for l in ls)[:200]); R["ruledup"].append(rid in rule); R["nlines"].append(len(ls))
        R["y"].append(int(np.mean([l["label"] != "outside" for l in ls]) >= 0.5) if labels else 0)
    return L, R, u


def book(b):
    dups = json.load(open(DUP)); LL, RR = None, None; part, golddup, unit = [], [], []
    for f in sorted(glob.glob("%s/%s/*.json" % (SRC, b))):
        d = json.load(open(f, encoding="utf-8")); L, R, u = page_arrays(d)
        LL = L if LL is None else {k: LL[k] + L[k] for k in L}; RR = R if RR is None else {k: RR[k] + R[k] for k in R}
        part += [d["partition"]] * len(R["rid"]); golddup += [r in dups.get(d["key"], {}) for r in R["rid"]]; unit += [u] * len(R["rid"])
    obj = ("text", "key", "rid", "lid", "review")
    out = {k: np.array(v, str) if k in obj else np.array(v, np.uint8 if k == "X" else np.float32) for k, v in LL.items()}
    out.update({"R_" + k: np.array(v, str) if k in obj else np.array(v, np.uint8 if k == "T" else np.float32) for k, v in RR.items()})
    out["R_part"] = np.array(part, str); out["R_golddup"] = np.array(golddup); out["R_unit"] = np.array(unit, np.float32)
    np.savez_compressed("line_nn_v3/work/%s.npz" % b, **out)
    print(b, "lines", len(LL["y"]), np.bincount(np.array(LL["y"]), minlength=5).tolist(), "regions", len(RR["rid"]), "central", int(sum(RR["y"])),
          "annotated duplicates", int(sum(golddup)), "rule duplicates", int(sum(RR["ruledup"])), flush=True)


if __name__ == "__main__":
    for b in sys.argv[1:] or sorted(os.listdir(SRC)):
        if not os.path.exists("line_nn_v3/work/%s.npz" % b):
            book(b)

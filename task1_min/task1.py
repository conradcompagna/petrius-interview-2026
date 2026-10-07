"""PetrIUS interview, Task I. Decretals of Gregory IX, Rome 1582 (MDZ object bsb10144443), scans 40 and 41.

  1. retrieve the page image and the OCR from MDZ
  2. find the block of decretal text in each column
  3. label every OCR line in the block: text, summarium, inscriptio or other

MDZ interfaces used
  image  https://api.digitale-sammlungen.de/iiif/image/v2/bsb10144443_000NN/full/full/0/default.jpg
  OCR    https://api.digitale-sammlungen.de/ocr/bsb10144443/NN            (hOCR: words with boxes, grouped in lines)

Method. Three things are measured on the image for a stretch of line: the share of red ink, whether the
letters are slanted, and the letter size relative to the commonest type on the page (the gloss).
The block of a column is where the lines in the larger type are; it is extended up and down over the
neighbouring lines of the same column. Inside the block: red = other, slanted = summarium,
large = text, the rest = inscriptio.

Run:  python task1.py        (needs opencv-python and numpy)
"""
import csv, html, json, os, re, urllib.request
import cv2, numpy as np

OBJECT, SCANS = "bsb10144443", (40, 41)
HERE = os.path.dirname(os.path.abspath(__file__))
LABELS = ["text", "summarium", "inscriptio", "other", "outside"]
COLOUR = {"text": (60, 160, 60), "summarium": (200, 120, 0), "inscriptio": (160, 0, 160), "other": (0, 0, 220)}   # BGR
LARGE = 1.15        # text type is about a quarter larger than the gloss
RED = 0.30          # share of red ink in a heading


def fetch(scan):
    """Image and hOCR from MDZ, kept in ./cache."""
    os.makedirs(os.path.join(HERE, "cache"), exist_ok=True)
    out = []
    for name, url in (("%05d.jpg" % scan, "https://api.digitale-sammlungen.de/iiif/image/v2/%s_%05d/full/full/0/default.jpg" % (OBJECT, scan)),
                      ("%05d.hocr" % scan, "https://api.digitale-sammlungen.de/ocr/%s/%d" % (OBJECT, scan))):
        path = os.path.join(HERE, "cache", name)
        if not os.path.exists(path):
            urllib.request.urlretrieve(url, path)
        out.append(path)
    return out


def ocr_lines(path):
    """The OCR as a list of lines; a line is a list of (box, word)."""
    lines = []
    for chunk in re.split(r"(?=<span[^>]*class=['\"]ocr_line)", open(path, encoding="utf-8").read())[1:]:
        words = [(tuple(map(int, b.split())), html.unescape(re.sub("<[^>]+>", "", w)).strip())
                 for b, w in re.findall(r"ocrx_word['\"][^>]*bbox (\d+ \d+ \d+ \d+)[^>]*>(.*?)</span>", chunk, flags=re.S)]
        words = [w for w in words if w[1]]
        if words:
            lines.append(words)
    return lines


def box(words):
    return (min(w[0][0] for w in words), min(w[0][1] for w in words), max(w[0][2] for w in words), max(w[0][3] for w in words))


def measure(image, ink, b):
    """red share, slanted or not, letter height in pixels, for the part of the page inside box b."""
    x0, y0, x1, y1 = b
    m = np.ascontiguousarray(ink[y0:y1, x0:x1])
    if m.sum() < 20:
        return 0.0, False, 0.0
    blue, green, red = [c.astype(int) for c in cv2.split(image[y0:y1, x0:x1])]
    red_share = ((red - green > 45) & (red - blue > 45) & (m > 0)).sum() / m.sum()
    # letter height: the commonest height among the blobs of ink that are at least a quarter of the line high
    heights = cv2.connectedComponentsWithStats(m, connectivity=8)[2][1:, 3]
    heights = heights[heights >= 0.25 * (y1 - y0)]
    size = float(max(sorted(set(heights)), key=lambda v: (abs(heights - v) <= 2).sum())) if len(heights) else 0.0
    # slant: italic strokes line up better after the line is sheared by 10 degrees than before
    def sharpness(degrees):
        t = np.tan(np.deg2rad(degrees))
        columns = cv2.warpAffine(m.astype(np.float32), np.float32([[1, t, -t * m.shape[0] / 2], [0, 1, 0]]), m.shape[::-1]).sum(axis=0)
        return float((columns ** 2).sum())
    return float(red_share), sharpness(10) > sharpness(0), size


def label_page(scan):
    image_path, hocr_path = fetch(scan)
    image = cv2.imread(image_path)
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ink = cv2.adaptiveThreshold(grey, 1, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 51, 25).astype(np.uint8)
    width = image.shape[1]
    lines = ocr_lines(hocr_path)

    # the commonest letter height on the page is the gloss; sizes are expressed in that unit
    whole = [(box(l),) + measure(image, ink, box(l)) for l in lines]
    unit = float(np.median([s for _, _, _, s in whole if s > 0]))

    # left and right edge of the block in each half of the page: where the large black lines start and end
    large = [b for b, red, _, s in whole if s >= LARGE * unit and red < RED and b[2] - b[0] > 0.1 * width]
    edges = []
    for half in (0, 1):
        g = [b for b in large if ((b[0] + b[2]) / 2 > width / 2) == bool(half)]
        edges.append((np.median([b[0] for b in g]) - 15, np.median([b[2] for b in g]) + 15))
    outer_left, outer_right = edges[0][0] - 10, edges[1][1] + 10

    result, blocks = [], []
    for column, (x0, x1) in zip("LR", edges):
        # the part of every OCR line that lies between the two edges (the OCR sometimes runs a line across both columns)
        parts = []
        for l in lines:
            words = [w for w in l if x0 <= (w[0][0] + w[0][2]) / 2 <= x1]
            if not words:
                continue
            b = box(words)
            red, slanted, size = measure(image, ink, b)
            parts.append(dict(scan=scan, column=column, bbox=b, text=" ".join(w[1] for w in words), red=red, slanted=slanted, size=size / unit,
                              # a gloss line runs past the outer edge of the blocks; a line of the block does not
                              inside=outer_left <= box(l)[0] and box(l)[2] <= outer_right))
        for p in parts:
            p["core"] = p["size"] >= LARGE and p["red"] < RED and (p["bbox"][2] - p["bbox"][0]) > 0.5 * (x1 - x0)
        core = [p for p in parts if p["core"] and p["inside"]]
        top, bottom = min(p["bbox"][1] for p in core), max(p["bbox"][3] for p in core)
        # extend the block over the lines directly above and below it (inscriptio and summarium at the head of a chapter)
        step = 1.3 * float(np.median([p["bbox"][3] - p["bbox"][1] for p in core]))
        grew = True
        while grew:
            grew = False
            for p in parts:
                if (p["inside"] or p["core"]) and p["bbox"][2] - p["bbox"][0] > 0.04 * width:
                    if top - step < p["bbox"][1] < top:
                        top, grew = p["bbox"][1], True
                    if bottom < p["bbox"][3] < bottom + step:
                        bottom, grew = p["bbox"][3], True
        for p in parts:
            middle = (p["bbox"][1] + p["bbox"][3]) / 2
            if p["bbox"][3] - p["bbox"][1] >= 0.5 * unit and top <= middle <= bottom and (p["inside"] or p["size"] >= LARGE or p["red"] > RED):
                p["label"] = "other" if p["red"] > RED else "summarium" if p["slanted"] else "text" if p["size"] >= LARGE else "inscriptio"
                result.append(p)
        blocks.append(dict(id=column, bbox=list(map(int, (x0, top, x1, bottom))), label="main_text_block"))
    # Gutter numbers belong to 'other'; retain the library's word boxes.
    for l in lines:
        for b, text in l:
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            if text.isdigit() and edges[0][1] - unit < cx < edges[1][0] + unit and any(r["bbox"][1] <= cy <= r["bbox"][3] for r in blocks):
                result.append(dict(scan=scan, column="gutter", bbox=b, text=text, red=0, slanted=False, size=0, label="other", kind="line_number"))
    # Recover a gutter number omitted by OCR using the same narrow strip as its neighbouring numbers.
    stats = cv2.connectedComponentsWithStats(ink, connectivity=8)[2][1:]
    numbers = [p for p in result if p.get("kind") == "line_number"]
    if numbers:
        left, right = np.median([p["bbox"][0] for p in numbers]), np.median([p["bbox"][2] for p in numbers])
        digits = [s for s in stats if left-unit*.25 <= s[0] and s[0]+s[2] <= right+unit*.25 and unit*.5 <= s[3] <= unit*1.5 and s[4] > 20]
        for x,y,w,h,area in digits:
            pair = [s for s in digits if abs(s[1]+s[3]/2-y-h/2) < unit*.3]
            if len(pair) == 2:
                b = tuple(map(int, (min(s[0] for s in pair), min(s[1] for s in pair), max(s[0]+s[2] for s in pair), max(s[1]+s[3] for s in pair))))
                cy = (b[1]+b[3])/2
                if any(r["bbox"][1] <= cy <= r["bbox"][3] for r in blocks) and not any(abs((p["bbox"][1]+p["bbox"][3])/2-cy) < unit*2 for p in numbers):
                    p = dict(scan=scan,column="gutter",bbox=b,text="[gutter line number]",red=0,slanted=False,size=0,label="other",kind="line_number")
                    result.append(p); numbers.append(p)
    # A woodcut initial is an ink component, not an OCR line. Its frame is much taller and wider than type.
    candidates = sorted(stats, key=lambda s: -int(s[2]) * int(s[3]))
    initials = []
    for x, y, w, h, area in candidates:
        if w > 6 * unit and h > 6 * unit and any(a <= x and y >= b and x+w <= c and y+h <= d for a,b,c,d in [r["bbox"] for r in blocks]):
            if not any(a <= x and b <= y and x+w <= c and y+h <= d for a,b,c,d in initials):
                initials.append((int(x),int(y),int(x+w),int(y+h)))
    result.extend(dict(scan=scan, column="L" if b[0] < width/2 else "R", bbox=b, text="[woodcut initial]", red=0, slanted=False, size=0, label="other", kind="initial") for b in initials)
    for r in blocks:
        a,b,c,d = r["bbox"]; cv2.rectangle(image, (a,b), (c,d), (0,0,0), 4)
    for p in result:
        a, b, c, d = p["bbox"]
        image[b:d, a:c] = (0.6 * image[b:d, a:c] + 0.4 * np.array(COLOUR[p["label"]])).astype(np.uint8)
    cv2.imwrite(os.path.join(HERE, "labels_%05d.jpg" % scan), image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    with open(os.path.join(HERE, "page_%05d.json" % scan), "w", encoding="utf-8") as f:
        json.dump(dict(key=f"{OBJECT}/{scan:05d}", book=OBJECT, scan=scan,
            image=dict(path=f"task1_min/cache/{scan:05d}.jpg", width=image.shape[1], height=image.shape[0]), regions=blocks,
            lines=[dict(p, id=f"line_{i:03d}", region_id=p["column"]) for i,p in enumerate(result)]), f, ensure_ascii=False, indent=2, default=lambda x: x.item())
    return result


def evaluate(result):
    """Confusion matrix against reference.csv: one row per reference line (a point inside the line and its label)."""
    matrix = np.zeros((5, 5), int)
    for row in csv.DictReader(open(os.path.join(HERE, "reference.csv"), encoding="utf-8")):
        x, y = float(row["x"]), float(row["y"])
        hits = [p for p in result if p["scan"] == int(row["scan"]) and p["bbox"][0] <= x <= p["bbox"][2] and p["bbox"][1] - 3 <= y <= p["bbox"][3] + 3]
        hit = min(hits, key=lambda p: abs((p["bbox"][1] + p["bbox"][3]) / 2 - y)) if hits else None
        matrix[LABELS.index(row["label"]), LABELS.index(hit["label"] if hit else "outside")] += 1
    print("reference in rows, program in columns")
    print("%-11s" % "" + "".join("%11s" % l for l in LABELS))
    for i, l in enumerate(LABELS):
        print("%-11s" % l + "".join("%11d" % v for v in matrix[i]))
    print("correct: %d of %d" % (np.trace(matrix), matrix.sum()))
    with open(os.path.join(HERE, "evaluation.json"), "w", encoding="utf-8") as f:
        json.dump(dict(labels=LABELS, confusion_matrix=matrix.tolist(), correct=int(np.trace(matrix)), total=int(matrix.sum()),
            additional_objects=[dict(scan=p["scan"], bbox=p["bbox"], kind=p["kind"], text=p["text"], label=p["label"]) for p in result if "kind" in p]), f, indent=2)


if __name__ == "__main__":
    result = [p for scan in SCANS for p in label_page(scan)]
    with open(os.path.join(HERE, "lines.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scan", "column", "x0", "y0", "x1", "y1", "label", "red", "slanted", "size", "text"])
        for p in result:
            w.writerow([p["scan"], p["column"], *p["bbox"], p["label"], round(p["red"], 2), int(p["slanted"]), round(p["size"], 2), p["text"]])
    evaluate(result)

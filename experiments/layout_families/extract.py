"""Page descriptors for layout-family assignment, from the page image and the saved parser prediction.

    python -m experiments.layout_families.extract [--books A B ...]

Writes outputs/layout_families/pages/<book>.json, a 640-px page thumbnail and a
384-px native-resolution patch from the middle of the main text (or of the page) for every page.
No labels are read; books of every partition are described the same way.
"""
import argparse, json, sys
from pathlib import Path
import cv2
import numpy as np
from .common import ROOT, PKG, WORK
from .measure import Page

OUT = WORK
ROLES = ['main_text', 'gloss', 'marginalia', 'header', 'initial', 'other']


def spacing(lines):
    """Median baseline-to-baseline distance between vertically adjacent, horizontally overlapping lines."""
    ys = sorted((float(np.median([p[1] for p in l['baseline']])), l['bbox'][0], l['bbox'][2]) for l in lines if l.get('baseline'))
    d = []
    for (y0, a0, a1), (y1, b0, b1) in zip(ys, ys[1:]):
        if min(a1, b1) - max(a0, b0) > .3 * min(a1 - a0, b1 - b0) and 3 < y1 - y0 < 200: d.append(y1 - y0)
    return float(np.median(d)) if d else 0.


def columns(lines, W):
    if len(lines) < 6: return 1 if lines else 0
    cov = np.zeros(W + 2)
    for l in lines: cov[max(0, l['bbox'][0]):min(W, l['bbox'][2]) + 1] += 1
    lo = min(l['bbox'][0] for l in lines); hi = max(l['bbox'][2] for l in lines); peak = np.percentile(cov[lo:hi + 1], 90)
    low = cov[lo:hi + 1] <= max(1., .2 * peak); n = 1; start = None
    for i, v in enumerate(np.append(low, False)):
        if v and start is None: start = i
        elif not v and start is not None:
            a, b = lo + start, lo + i
            if a - lo > .15 * (hi - lo) and hi - b > .15 * (hi - lo) and b - a >= 3: n += 1
            start = None
    return n


def describe(rec, im):
    H, W = im.shape[:2]; A = float(W * H); f = dict(aspect=W / H)
    lines = rec['lines']; f['n_lines'] = len(lines)
    by = {r: [l for l in lines if l.get('region_role') == r] for r in ROLES}
    for r in ROLES:
        f[f'lines_{r}'] = len(by[r]) / max(1, len(lines))
        f[f'area_{r}'] = sum(abs(cv2.contourArea(np.asarray(g['polygon'], np.float32))) for g in rec['regions'] if g['role'] == r) / A
        f[f'n_regions_{r}'] = sum(g['role'] == r for g in rec['regions'])
    main, gloss = by['main_text'], by['gloss']
    f['presence'] = rec.get('qa', {}).get('legal_text_presence') or 0.
    f['main_cols'] = columns(main, W); f['all_cols'] = columns([l for l in lines if l.get('region_role') in ('main_text', 'gloss', 'other')], W)
    sm, sg = spacing(main), spacing(gloss); f['main_pitch'] = sm / H; f['gloss_pitch'] = sg / H; f['pitch_ratio'] = sm / sg if sm and sg else 0.
    f['line_pitch_all'] = spacing(lines) / H
    if main:
        x0 = min(l['bbox'][0] for l in main); x1 = max(l['bbox'][2] for l in main); y0 = min(l['bbox'][1] for l in main); y1 = max(l['bbox'][3] for l in main)
        f.update(main_w=(x1 - x0) / W, main_h=(y1 - y0) / H, main_cx=(x0 + x1) / 2 / W, main_cy=(y0 + y1) / 2 / H)
        c = lambda l: ((l['bbox'][0] + l['bbox'][2]) / 2, (l['bbox'][1] + l['bbox'][3]) / 2)
        g = [c(l) for l in gloss]; n = max(1, len(g))
        f.update(gloss_left=sum(x < x0 for x, y in g) / n, gloss_right=sum(x > x1 for x, y in g) / n, gloss_above=sum(y < y0 for x, y in g) / n, gloss_below=sum(y > y1 for x, y in g) / n)
        centre = (int((x0 + x1) / 2), int((y0 + y1) / 2))
    else:
        f.update(main_w=0., main_h=0., main_cx=0., main_cy=0., gloss_left=0., gloss_right=0., gloss_above=0., gloss_below=0.)
        centre = (W // 2, H // 2)
    widths = [l['bbox'][2] - l['bbox'][0] for l in lines] or [0]
    f['line_w_med'] = float(np.median(widths)) / W; f['line_w_p90'] = float(np.percentile(widths, 90)) / W
    page = Page(im)
    ink = page.ink; f['ink'] = float(ink.mean()); f['red'] = float(page.red.sum()) / max(1, int(ink.sum()))
    hsv = cv2.cvtColor(cv2.resize(im, (64, 96)), cv2.COLOR_BGR2HSV); f['saturation'] = float(hsv[..., 1].mean()) / 255; f['value'] = float(hsv[..., 2].mean()) / 255
    return f, centre


def main(books):
    src = PKG / 'source_pages'
    (OUT / 'pages').mkdir(parents=True, exist_ok=True); (OUT / 'thumbs').mkdir(exist_ok=True); (OUT / 'patches').mkdir(exist_ok=True)
    (OUT / 'feature_keys.json').write_bytes((PKG / 'work/feature_keys.json').read_bytes())
    for b in books or sorted(p.name for p in src.iterdir() if (p / 'predictions').is_dir()):
        target = OUT / 'pages' / f'{b}.json'
        if target.exists(): continue
        rows = []
        for f in sorted((src / b / 'predictions').glob('*.json')):
            rec = json.loads(f.read_text(encoding='utf-8')); im = cv2.imread(str(ROOT / rec['image']['path'].replace('\\', '/')))
            if im is None: continue
            feat, (cx, cy) = describe(rec, im)
            H, W = im.shape[:2]; s = 640 / H
            cv2.imwrite(str(OUT / 'thumbs' / f'{b}_{f.stem}.jpg'), cv2.resize(im, (int(W * s), 640), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 80])
            x0 = int(np.clip(cx - 192, 0, max(0, W - 384))); y0 = int(np.clip(cy - 192, 0, max(0, H - 384)))
            cv2.imwrite(str(OUT / 'patches' / f'{b}_{f.stem}.jpg'), im[y0:y0 + 384, x0:x0 + 384], [cv2.IMWRITE_JPEG_QUALITY, 88])
            rows.append(dict(book=b, scan=int(f.stem), features=feat))
        assert rows, f'No source pages found for {b}'
        target.write_text(json.dumps(rows), encoding='utf-8'); print(b, len(rows), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--books', nargs='*'); main(p.parse_args().books)

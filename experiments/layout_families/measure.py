"""Page and line measurements on the image: ink, red ink, x-height, slant, caps, spacing.

Everything is expressed relative to the page's own body type, so no edition-specific
threshold enters. CPU only (OpenCV + NumPy).
"""
import cv2
import numpy as np

ANGLES = np.arange(-6, 27, 1.5)


def load(path):
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if im is None:
        raise IOError(f'cannot read {path}')
    return im


class Page:
    """Binarised page with red-ink mask. Built once, queried per box."""

    def __init__(self, im):
        self.im = im
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(g, None, fx=.25, fy=.25, interpolation=cv2.INTER_AREA)
        bg = cv2.resize(cv2.medianBlur(small, 31), (g.shape[1], g.shape[0]))
        norm = cv2.divide(g, bg, scale=255)
        self.norm = norm
        _, bw = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        # Red is measured against the local paper colour, so yellowed paper and faded rubrics both work.
        sm = cv2.resize(im, None, fx=.25, fy=.25, interpolation=cv2.INTER_AREA)
        paper = cv2.resize(cv2.medianBlur(sm, 31), (g.shape[1], g.shape[0])).astype(np.int16)
        b, gg, r = [c.astype(np.int16) for c in cv2.split(im)]
        redness = (r - gg) - (paper[..., 2] - paper[..., 1])
        red = (redness > 28) & (gg < paper[..., 1] - 25)
        red = cv2.morphologyEx(red.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)) > 0
        self.ink = (bw > 0) | red
        self.red = red
        self.H, self.W = g.shape

    def clip(self, box, pad=0):
        x0, y0, x1, y1 = [int(round(v)) for v in box]
        return max(0, x0 - pad), max(0, y0 - pad), min(self.W, x1 + pad + 1), min(self.H, y1 + pad + 1)


def slant(mask):
    if mask.size == 0 or mask.sum() < 20:
        return 0., 1.
    h, w = mask.shape
    m = mask.astype(np.float32)
    scores = []
    for a in ANGLES:
        t = np.tan(np.deg2rad(a))
        M = np.float32([[1, t, -t * h / 2.], [0, 1, 0]])
        p = cv2.warpAffine(m, M, (w, h), flags=cv2.INTER_LINEAR).sum(0)
        scores.append(float((p * p).sum()))
    scores = np.array(scores)
    i = int(scores.argmax())
    return float(ANGLES[i]), float(scores[i] / (scores[int(np.abs(ANGLES).argmin())] + 1e-6))


def band(profile, frac):
    """Longest run of rows whose ink projection exceeds frac * max."""
    if profile.max() <= 0:
        return 0, 0
    on = profile >= frac * profile.max()
    best = (0, 0); start = None
    for i, v in enumerate(np.append(on, False)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    return best


def measure(page, box, pad_y=0):
    """Raw typographic measurements of the ink inside a box (line, span or word)."""
    x0, y0, x1, y1 = page.clip(box)
    y0 = max(0, y0 - pad_y); y1 = min(page.H, y1 + pad_y)
    ink = page.ink[y0:y1, x0:x1]
    red = page.red[y0:y1, x0:x1]
    n = int(ink.sum())
    out = dict(ink=n, w=x1 - x0, h=y1 - y0, x0=x0, x1=x1, y0=y0, y1=y1)
    if n < 15 or ink.shape[1] < 4:
        out.update(red=0., xh=0., asc=0., body_ratio=0., slant=0., slant_gain=1., density=0., stroke=0.,
                   ink_x0=x0, ink_x1=x1, gap_max=0., gap_mean=0., base=y1, ncomp=0, tall=0., xh_proj=0.)
        return out
    cols = np.flatnonzero(ink.any(0))
    out['ink_x0'], out['ink_x1'] = x0 + int(cols[0]), x0 + int(cols[-1])
    prof = ink.sum(1).astype(float)
    prof = np.convolve(prof, [.25, .5, .25], mode='same')
    a, b = band(prof, .5)      # x-height band
    c, d = band(prof, .12)     # ascender-to-descender extent
    out['xh'] = float(b - a)
    # Skew and curvature smear a whole-row profile, so the bands are measured in short stretches of the
    # row and the medians are kept.
    step = max(60, 5 * ink.shape[0]); xs = []; As = []
    for s0 in range(0, ink.shape[1], step):
        part = ink[:, s0:s0 + step]
        if part.sum() < 40 or part.shape[1] < 20: continue
        pp = np.convolve(part.sum(1).astype(float), [.25, .5, .25], mode='same')
        a2, b2 = band(pp, .5); c2, d2 = band(pp, .12)
        xs.append(b2 - a2); As.append(d2 - c2)
    out['xh_proj'] = out['xh']
    if xs:
        out['xh'] = float(np.median(xs)); out['asc_local'] = float(np.median(As))
    out['asc'] = out.pop('asc_local', float(d - c))
    out['body_ratio'] = out['xh'] / max(1., out['asc'])
    out['base'] = y0 + b
    out['red'] = float(red.sum()) / n
    core = ink[max(0, a - 1):b + 1]
    s, gain = slant(ink[c:d])
    out['slant'], out['slant_gain'] = s, gain
    out['density'] = float(core.sum()) / max(1, core.size)
    # stroke width: median horizontal run of ink in the x-height band
    runs = []
    for row in core[::2]:
        dd = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        runs.extend((np.flatnonzero(dd == -1) - np.flatnonzero(dd == 1)).tolist())
    out['stroke'] = float(np.median(runs)) if runs else 0.
    # white gaps along the line (letter- and word-spacing)
    occ = ink[c:d].any(0)[cols[0]:cols[-1] + 1]
    dd = np.diff(np.concatenate([[1], occ.astype(np.int8), [1]]))
    gaps = np.flatnonzero(dd == 1) - np.flatnonzero(dd == -1)
    out['gap_max'] = float(gaps.max()) if len(gaps) else 0.
    out['gap_mean'] = float(gaps.mean()) if len(gaps) else 0.
    out['ncomp'] = int(len(gaps) + 1)
    # share of columns whose ink rises well above the x-height band (capitals, ascenders)
    above = ink[c:max(c + 1, a - 1)].any(0)
    out['tall'] = float(above[cols[0]:cols[-1] + 1].mean()) if a - c >= 2 else 0.
    return out

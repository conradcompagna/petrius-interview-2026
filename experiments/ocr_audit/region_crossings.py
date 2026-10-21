"""Rerun the 6 Oct cross-region OCR study on the 120 manually checked region pages
(100 training + 20 evaluation, data/dfine).
Same rule as experiments/ocr_audit/audit.py: word centres mapped to regions inset by 2 px;
words in zero or several regions ignored; a row is flagged when >=2 regions each receive
>=2 words with >=6 letters. Block checks use >=3 words per region.
Run from repo root: python tools/region_study_120.py
"""
from pathlib import Path
from collections import Counter, defaultdict
import json, re, sys, time, urllib.request, hashlib
sys.path.insert(0, str(Path(__file__).resolve().parent))
from .audit import parse
from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/region_crossings'
OUT.mkdir(parents=True, exist_ok=True)
fam = json.loads((ROOT/'data/corpus/families.json').read_text(encoding='utf-8'))
man = json.loads((ROOT/'data/dfine/manifest.json').read_text(encoding='utf-8'))

cached = {}
for base in [ROOT/'data/ocr_audit/hocr']:
    if base.exists():
        for p in base.rglob('*.hocr'):
            book = next((x for x in p.parts if re.fullmatch(r'bsb\d+', x)), None)
            if book and p.stem.isdigit(): cached.setdefault((book, int(p.stem)), p)

def hocr(book, scan):
    p = cached.get((book, scan))
    if p: return p, 'cached'
    dest = OUT/'hocr'/book/f'{scan:05d}.hocr'
    if dest.exists(): return dest, 'fetched'
    if '--fetch-missing' not in sys.argv:
        raise FileNotFoundError(f'No retained library OCR for {book}/{scan:05d}')
    url = f'https://api.digitale-sammlungen.de/ocr/{book}/{scan}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Historical-Latin-OCR-audit/1.0'})
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r: data = r.read(); break
        except Exception:
            if a == 2: raise
            time.sleep(a+1)
    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
    return dest, 'fetched'

pages = []; errors = []
for pg in man['pages']:
    book, scan = pg['book'], int(pg['scan'])
    try: hp, how = hocr(book, scan)
    except Exception as e: errors.append(dict(key=pg['key'], error=str(e))); continue
    h = parse(hp)
    a = json.loads((ROOT/pg['annotation']).read_text(encoding='utf-8'))
    W, H = a['image']['width'], a['image']['height']
    sx, sy = W/h['bbox'][2], H/h['bbox'][3]
    regions = [(z['id'], Polygon(z['polygon']).buffer(0).buffer(-2)) for z in a['regions']]
    flags = []; bw = defaultdict(Counter); rb = defaultdict(Counter); eligible = assigned = 0
    for l in h['lines']:
        n = Counter(); ch = Counter()
        for w in l['words']:
            letters = sum(c.isalpha() for c in w['text'])
            if letters < 2: continue
            eligible += 1; x0, y0, x1, y1 = w['bbox']
            pt = Point((x0+x1)*sx/2, (y0+y1)*sy/2)
            hits = [rid for rid, poly in regions if poly.contains(pt)]
            if len(hits) != 1: continue
            rid = hits[0]; assigned += 1; n[rid] += 1; ch[rid] += letters
            bw[l['block']][rid] += 1; rb[rid][l['block']] += 1
        sig = [r for r, k in n.items() if k >= 2 and ch[r] >= 6]
        if len(sig) >= 2: flags.append(dict(line=l['id'], bbox=l['bbox'], regions=sig, text=l['text']))
    mixed = {str(b): dict(c) for b, c in bw.items() if sum(v >= 3 for v in c.values()) >= 2}
    frag = {r: dict(c) for r, c in rb.items() if sum(v >= 3 for v in c.values()) >= 2}
    pages.append(dict(key=pg['key'], book=book, scan=scan, partition=pg['partition'], family=fam.get(book),
        hocr=str(hp.relative_to(ROOT)).replace('\\', '/'), hocr_source=how, hocr_sha256=hashlib.sha256(hp.read_bytes()).hexdigest(),
        rows=len(h['lines']), eligible_words=eligible, assigned_words=assigned, regions=len(regions),
        cross_region_rows=len(flags), mixed_blocks=len(mixed), fragmented_regions=len(frag),
        row_flags=flags, mixed_block_details=mixed, fragment_details=frag))

def summ(xs):
    return dict(pages=len(xs), books=len({x['book'] for x in xs}), rows=sum(x['rows'] for x in xs),
        cross_region_rows=sum(x['cross_region_rows'] for x in xs),
        pages_with_cross_region_rows=sum(x['cross_region_rows'] > 0 for x in xs),
        mixed_blocks=sum(x['mixed_blocks'] for x in xs), pages_with_mixed_blocks=sum(x['mixed_blocks'] > 0 for x in xs),
        regions=sum(x['regions'] for x in xs), fragmented_regions=sum(x['fragmented_regions'] for x in xs),
        eligible_words=sum(x['eligible_words'] for x in xs), assigned_words=sum(x['assigned_words'] for x in xs))
S = dict(source='data/dfine/manifest.json', rule='as experiments/ocr_audit/audit.py; no initial exclusion (initials are inside regions here)',
         errors=errors, all=summ(pages), by_partition={p: summ([x for x in pages if x['partition'] == p]) for p in sorted({x['partition'] for x in pages})},
         by_family={f: summ([x for x in pages if x['family'] == f]) for f in sorted({str(x['family']) for x in pages})})
for x in S['by_family']: pass
S['by_family'] = {f: summ([x for x in pages if str(x['family']) == f]) for f in sorted({str(x['family']) for x in pages})}
(OUT/'pages.json').write_text(json.dumps(pages, ensure_ascii=False, indent=1), encoding='utf-8')
(OUT/'summary.json').write_text(json.dumps(S, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: S[k] for k in ['errors', 'all', 'by_partition', 'by_family']}, indent=1))

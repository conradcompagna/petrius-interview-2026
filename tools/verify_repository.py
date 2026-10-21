"""Verify frozen datasets, training inputs, saved results and packaged source."""
import ast
from collections import Counter
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.io import read, sha

def main():
    counts = {}
    for name in ['dfine', 'neural']:
        pages = read(ROOT/f'data/{name}/manifest.json')['pages']
        assert len(pages) == len({p['key'] for p in pages}) == 120
        roles = Counter(p.get('training_role', p.get('partition')) for p in pages)
        assert roles == {'training': 100, 'evaluation': 20}
        for p in pages:
            annotation = ROOT/p['annotation']; assert sha(annotation) == p['annotation_sha256']
            rec = read(annotation); assert rec['key'] == p['key']
            assert rec['image']['sha256'] == p['image_sha256']
            image = ROOT/p['image']
            if image.exists(): assert sha(image) == p['image_sha256']
        counts[name] = dict(pages=len(pages), **roles)
    pages = read(ROOT/'data/dfine/manifest.json')['pages']
    assert sum(p['regions'] for p in pages) == 1428
    for p in pages:
        rec = read(ROOT/p['annotation'])
        boxes = [[min(x for x,y in r['polygon']), min(y for x,y in r['polygon']), max(x for x,y in r['polygon']), max(y for x,y in r['polygon'])] for r in rec['regions']]
        assert boxes == p['boxes']
    split = read(ROOT/'data/neural/split.json')
    neural = read(ROOT/'data/neural/manifest.json')['pages']
    for part in ['training', 'evaluation']:
        assert set(split[part]) == {p['key'] for p in neural if p['partition'] == part}
    labels = Counter()
    for p in neural: labels.update(line['label'] for line in read(ROOT/p['annotation'])['lines'])
    assert set(labels) <= {'text', 'summarium', 'inscriptio', 'other', 'outside'}
    assert sum(labels.values()) == 32018
    source = ROOT/'data/charlm/training_source.jsonl'
    assert sha(source) == read(ROOT/'data/charlm/source_manifest.json')['training_source_sha256']
    assert len(source.read_text(encoding='utf-8').splitlines()) == 19630
    results = read(ROOT/'results/charlm/results.json')
    assert results['pages'] == 50 and not any(results['replication'].values())
    for item in read(ROOT/'source_map.json'):
        assert sha(ROOT/item['published']) == item['published_sha256'], item['published']
    for p in ROOT.rglob('*.py'):
        rel = p.relative_to(ROOT)
        if any(x.startswith('.venv') or x in {'outputs', 'downloads', '__pycache__'} for x in rel.parts): continue
        if rel.parts[0].startswith('presentation'): continue
        ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(rel))
    print(json.dumps(dict(datasets=counts, neural_line_labels=labels, charlm_training_lines=19630, charlm_pages=50), indent=2))

if __name__ == '__main__': main()

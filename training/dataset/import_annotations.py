"""Validate annotated pages without changing frozen training data."""
import argparse
from pathlib import Path
from shared.io import ROOT, read, write

LABELS = {'text', 'summarium', 'inscriptio', 'other', 'outside'}


def validate(reference, annotated):
    assert annotated['key'] == reference['key']
    assert annotated['image']['sha256'] == reference['image']['sha256']
    assert annotated['partition'] == reference['partition']
    regions = {r['id']: r for r in reference['regions']}
    assert regions.keys() == {r['id'] for r in annotated['regions']}
    for r in annotated['regions']:
        assert r['polygon'] == regions[r['id']]['polygon']
    lines = {line['id']: line for line in reference['lines']}
    assert lines.keys() == {line['id'] for line in annotated['lines']}
    for line in annotated['lines']:
        original = lines[line['id']]
        assert line['label'] in LABELS
        assert line['bbox'] == original['bbox']
        assert line['text'] == original['text']
        assert (line.get('region_id') or line['region_ids'][0]) in regions
        for span in line.get('semantic_spans', []):
            start, end = span['start'], span['end']
            assert 0 <= start < end <= len(line['text'])
    return annotated


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('annotations', type=Path)
    p.add_argument('--out', type=Path, default=ROOT/'outputs/imported_annotations')
    args = p.parse_args()
    for item in read(ROOT/'data/neural/manifest.json')['pages']:
        reference = read(ROOT/item['annotation'])
        page = validate(reference, read(args.annotations/(item['key']+'.json')))
        write(args.out/(item['key']+'.json'), page)
    print('Validated 120 pages')


if __name__ == '__main__':
    main()

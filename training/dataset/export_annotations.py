"""Export fixed page images, OCR evidence and annotation templates."""
import argparse
import copy
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
from shared.io import ROOT, read, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('--pages', type=Path, default=ROOT/'data/neural/pages')
    args = p.parse_args()
    manifest = read(ROOT/'data/neural/manifest.json')
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.archive, 'x', compression=ZIP_DEFLATED) as z:
        z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
        z.writestr('annotation_protocol.json', (ROOT/'data/neural/annotation_protocol.json').read_bytes())
        z.writestr('annotation.schema.json', (ROOT/'training/dataset/annotation.schema.json').read_bytes())
        for item in manifest['pages']:
            page = read(args.pages/(item['key']+'.json'))
            assert page['key'] == item['key']
            source = ROOT/item['image']
            assert sha(source) == item['image_sha256']
            evidence = copy.deepcopy(page)
            evidence['image']['path'] = f"images/{item['key']}.jpg"
            for line in evidence['lines']:
                line['label'] = 'outside'
                line['review_status'] = 'needs_review'
                line['semantic_spans'] = []
            for region in evidence['regions']:
                region.pop('selection', None)
                region.pop('duplicate_of', None)
            z.writestr(f"pages/{item['key']}.json", json.dumps(evidence, ensure_ascii=False))
            z.write(source, evidence['image']['path'], compress_type=ZIP_STORED)
    with ZipFile(args.archive) as z:
        assert z.testzip() is None
    print(args.archive)


if __name__ == '__main__':
    main()

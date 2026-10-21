"""Recreate detector/PERO inputs for the frozen neural dataset."""
import argparse
import copy
from pathlib import Path
from shared.io import ROOT, read, write, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    p.add_argument('--limit', type=int)
    p.add_argument('--out', type=Path, default=ROOT/'outputs/dataset')
    args = p.parse_args()
    from inference.run import regions, ocr
    pages = read(ROOT/'data/neural/manifest.json')['pages']
    for item in pages[:args.limit]:
        target = args.out/'pages'/(item['key']+'.json')
        if target.exists():
            saved = read(target)
            assert saved['image']['sha256'] == item['image_sha256']
            continue
        image = ROOT/item['image']
        assert sha(image) == item['image_sha256']
        page = regions(image, item['key'], args.device)
        page = ocr(page, args.device, args.out)
        page['book'], page['scan'], page['partition'] = item['book'], item['scan'], item['partition']
        page['semantic_labels_assigned'] = False
        write(target, page)
        print(item['key'], len(page['regions']), len(page['lines']), flush=True)


if __name__ == '__main__':
    main()

"""Check the published viewer's collections and every bundled asset reference."""
import gzip
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

EXPECTED = {
    'finished-task1-min': 2, 'legacy-gold-review': 102, 'parser-transfer': 132,
    'mdz-ocr-regions': 50, 'mdz-ocr-lexicon': 50, 'stock-models': 14,
    'finished-region-data': 120, 'finished-region-eval': 20,
    'finished-neural-data': 120, 'finished-neural-eval': 20, 'finished-interview': 2,
    'finished-random-pipeline': 10,
}


def validate(root):
    root = root.resolve()

    def local(relative):
        path = (root / relative).resolve()
        assert path.is_relative_to(root) and path.is_file(), relative
        return path

    index = json.loads(local('data/index.json').read_text(encoding='utf8'))
    collections = {}
    annotations, images = set(), set()
    objects = 0
    for dataset in index['datasets']:
        assert dataset['id'] not in collections, dataset['id']
        assert dataset['group'] == 'finished', dataset['id']
        collections[dataset['id']] = len(dataset['pages'])
        keys = set()
        for descriptor in dataset['pages']:
            assert descriptor['key'] not in keys, descriptor['key']
            keys.add(descriptor['key'])
            path = local(descriptor['annotation'])
            assert path not in annotations, str(path)
            annotations.add(path)
            raw = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
            page = json.loads(raw)
            assert page['key'] == descriptor['key'] and page['dataset'] == dataset['id'], descriptor['key']
            assert page['image']['width'] > 0 and page['image']['height'] > 0
            source = descriptor['image_url']
            if urlparse(source).scheme:
                assert source.startswith('https://'), source
            else:
                images.add(local(source))
            objects += len(page['objects'])
    assert collections == EXPECTED, collections
    assert annotations == {p.resolve() for p in (root / 'data/pages').rglob('*.gz')}, 'Unreferenced page data'
    assert images == {p.resolve() for p in (root / 'data/images').rglob('*') if p.is_file()}, 'Unreferenced bundled scans'
    for required in ['index.html', 'app.js', 'style.css', 'SOURCES.html']:
        local(required)
    books = {page['book'] for dataset in index['datasets'] for page in dataset['pages']}
    source_books = set(re.findall(r'<tr><td>([^<]+)</td>', local('SOURCES.html').read_text(encoding='utf8')))
    assert source_books == books, 'Source inventory does not match the reader books'
    size = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    assert size < 1_000_000_000, f'Site exceeds GitHub Pages limit: {size} bytes'
    result = {'datasets': len(collections), 'pages': sum(collections.values()),
              'collections': collections, 'bundled_scans': len(images),
              'objects': objects, 'bytes': size, 'source_books': len(books)}
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    validate(Path(sys.argv[1] if len(sys.argv) > 1 else 'site'))

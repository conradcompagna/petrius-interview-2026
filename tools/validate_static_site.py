"""Check every local reference before publishing the static annotation viewer."""
import gzip
import json
from pathlib import Path
import sys
from urllib.parse import urlparse


def validate(root):
    root = root.resolve()
    def local(relative):
        path = (root / relative).resolve()
        assert path.is_relative_to(root) and path.is_file(), relative
        return path
    index = json.loads(local('data/index.json').read_text(encoding='utf8'))
    count = 0
    finished = {}
    for dataset in index['datasets']:
        if dataset.get('group') == 'finished':
            finished[dataset['id']] = len(dataset['pages'])
        for descriptor in dataset['pages']:
            path = local(descriptor['annotation'])
            raw = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
            page = json.loads(raw)
            assert page['key'] == descriptor['key'] and page['dataset'] == dataset['id'], descriptor['key']
            assert page['image']['width'] > 0 and page['image']['height'] > 0
            source = descriptor['image_url']
            if urlparse(source).scheme:
                assert source.startswith('https://'), source
            else:
                local(source)
            if descriptor.get('text_url'):
                local(descriptor['text_url'])
            count += 1
    expected = {'finished-task1-min': 2, 'finished-interview': 2,
                'finished-region-data': 120, 'finished-neural-data': 120,
                'finished-region-eval': 20, 'finished-neural-eval': 20}
    assert finished == expected, finished
    for required in ['index.html', 'app.js', 'style.css', 'SOURCES.html']:
        local(required)
    size = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    assert size < 1_000_000_000, f'Site exceeds GitHub Pages limit: {size} bytes'
    result = {'datasets': len(index['datasets']), 'pages': count, 'finished': finished, 'bytes': size}
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    validate(Path(sys.argv[1] if len(sys.argv) > 1 else 'site'))

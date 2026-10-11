"""Download unseen pages from the recorded matching-layout book cohort."""
from pathlib import Path
import hashlib
import json
import random
import secrets
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent


def get(url):
    request = Request(url, headers={'User-Agent': 'historical-latin-random-page-inference'})
    with urlopen(request, timeout=60) as response:
        return response.read()


def eligible_scans(book, canvases):
    excluded = set(book['excluded_scans'])
    first, last = max(1, int(len(canvases) * .1)), int(len(canvases) * .9)
    return [scan for scan in range(first, last + 1)
            if scan not in excluded and canvases[scan - 1].get('images')]


def image_url(canvas):
    resource = canvas['images'][0]['resource']
    service = resource['service']
    if isinstance(service, list):
        service = service[0]
    url = service.get('@id', service.get('id', '')).rstrip('/') + '/full/full/0/default.jpg'
    if not url.startswith('https://api.digitale-sammlungen.de/iiif/image/'):
        raise ValueError('Unexpected MDZ image service: ' + url)
    return url


def prepare_pages(out, count, seed=None, books=None):
    from PIL import Image
    if count < 1:
        raise ValueError('The number of random pages must be at least 1.')
    cohort = json.loads((HERE / 'random_books.json').read_text(encoding='utf8'))
    available = cohort['books']
    if books:
        unknown = set(books) - {book['id'] for book in available}
        if unknown:
            raise ValueError('Books outside the matching-layout cohort: ' + ', '.join(sorted(unknown)))
        available = [book for book in available if book['id'] in books]
    seed = secrets.randbits(63) if seed is None else seed
    rng = random.Random(seed)
    chosen = rng.sample(available, min(count, len(available)))
    pools, native, manifests = {}, {}, {}
    for book in chosen:
        print('Reading book manifest: ' + book['id'], flush=True)
        raw = get(book['manifest_url'])
        manifest = json.loads(raw)
        canvases = manifest['sequences'][0]['canvases']
        pools[book['id']] = eligible_scans(book, canvases)
        native[book['id']] = canvases
        manifests[book['id']] = {
            'book': book['id'], 'title': book['title'], 'url': book['manifest_url'],
            'sha256': hashlib.sha256(raw).hexdigest(), 'total_scans': len(canvases),
            'eligible_scans': len(pools[book['id']]),
        }
    if count > sum(len(pool) for pool in pools.values()):
        raise ValueError('Requested more pages than remain in the selected books.')
    selected = []
    while len(selected) < count:
        active = [book for book in chosen if pools[book['id']]]
        rng.shuffle(active)
        for book in active:
            pool = pools[book['id']]
            scan = rng.choice(pool)
            pool.remove(scan)
            selected.append((book, scan, native[book['id']][scan - 1]))
            if len(selected) == count:
                break
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    record = {'seed': seed, 'selection_basis': cohort['selection_basis'],
              'sampling_policy': cohort['sampling_policy'],
              'manifests': list(manifests.values()), 'pages': []}
    sources = []
    for book, scan, canvas in selected:
        key = f"{book['id']}/{scan:05d}"
        url = image_url(canvas)
        relative = f"images/{book['id']}_{scan:05d}.jpg"
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        print('Downloading random page: ' + key, flush=True)
        if not path.exists():
            payload = get(url)
            pending = path.with_suffix('.jpg.part')
            pending.write_bytes(payload)
            pending.replace(path)
        with Image.open(path) as image:
            image.load()
            width, height = image.size
        record['pages'].append({
            'key': key, 'book': book['id'], 'scan': scan, 'title': book['title'],
            'scan_label': canvas.get('label', ''), 'source_url': url,
            'image': relative, 'width': width, 'height': height,
            'image_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'excluded_training_evaluation_and_reader_pages': True,
        })
        sources.append((path, key))
    (out / 'random_sample.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(f'Random sample: {count} pages; seed {seed}', flush=True)
    return sources

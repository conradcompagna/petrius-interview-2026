"""The submission collections, with earlier runs kept in a separate archive."""
from copy import deepcopy
from pathlib import Path


def add_finished(catalog, root):
    definitions = [
        ('finished-interview', 'Interview pages · neural pipeline', 'prediction',
         ['legacy-line-nn-v3-task'],
         'Scans 40–41: D-FINE regions, PERO lines and OCR, then the v3 neural region and line taggers.', None),
        ('finished-region-data', 'D-FINE annotation dataset', 'reference',
         ['seg-original-regions-training100', 'seg-original-regions-evaluation20'],
         '120 annotated pages: 100 training pages and 20 evaluation pages. Source region polygons and page images.', None),
        ('finished-neural-data', 'Neural classifier annotation dataset', 'reference',
         ['legacy-webgpt-central-block'],
         '120 annotated pages: 100 training pages and 20 evaluation pages. Central blocks, line labels, OCR and mixed-line spans.', None),
        ('finished-region-eval', 'D-FINE · 20 evaluation pages', 'prediction',
         ['seg-dfine-eval'],
         'Region detections on the 20 evaluation pages. Compare with the region annotation dataset.', 'finished-region-data'),
        ('finished-neural-eval', 'Neural classifier · 20 evaluation pages', 'prediction',
         ['legacy-line-nn-v3'],
         'V3 region and line labels on the 20 evaluation pages. Compare with the neural annotation dataset; red outlines mark label differences.', 'finished-neural-data'),
    ]
    minimal = root / 'task1_min/viewer_manifest.json'
    if minimal.exists():
        import json
        manifest = json.loads(minimal.read_text(encoding='utf8'))
        catalog.add_dataset('finished-task1-min', 'Task I · minimal image rules', 'prediction',
                            'The submitted OpenCV and NumPy program on scans 40–41. Click a line or structural object to inspect its label.')
        catalog.datasets['finished-task1-min']['group'] = 'finished'
        for p in manifest['pages']:
            catalog.add_page('finished-task1-min', p['book'], p['scan'], image=p['image'], annotation=p['annotation'], split='interview Task I')
    for identity, name, kind, sources, description, reference in definitions:
        if not all(s in catalog.datasets for s in sources):
            continue
        catalog.add_dataset(identity, name, kind, description)
        target = catalog.datasets[identity]
        target.update(group='finished', reference_dataset=reference)
        for source in sources:
            target['pages'].update(deepcopy(catalog.datasets[source]['pages']))
        if identity == 'finished-neural-data':
            for page in target['pages'].values():
                page['split'] = page.get('split', '').split(' · ')[0]
        if identity == 'finished-interview':
            for page in target['pages'].values():
                page['split'] = 'interview Task I'
        if identity == 'finished-region-eval':
            frozen = root / 'out/submission_final_20261007/dfine_eval'
            for key, page in target['pages'].items():
                prediction = frozen / (key + '.json')
                if prediction.exists():
                    page['annotation'] = prediction.relative_to(root).as_posix()
    for d in catalog.datasets.values():
        d.setdefault('group', 'archive')
    # Dict order supplies a consistent initial selection for the portable viewer.
    catalog.datasets = dict(sorted(catalog.datasets.items(), key=lambda pair: pair[1]['group'] != 'finished'))

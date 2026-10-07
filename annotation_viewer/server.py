"""Local, read-only annotation browser. Python standard library; no models loaded."""
from __future__ import annotations

import argparse
import json
import mimetypes
import struct
import threading
import webbrowser
from collections import Counter
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from .legacy import adapt as adapt_legacy, review_index
from .region_pack import adapt as adapt_region_pack
from .finished import add_finished

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent
LABELS = ['text', 'summarium', 'inscriptio', 'other']


def local(path):
    p = (ROOT / str(path).replace('\\', '/')).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError('Path outside project')
    return p


def read(path):
    return json.loads(local(path).read_text(encoding='utf-8'))


def relative(path):
    return local(path).relative_to(ROOT).as_posix()


def image_size(path):
    """Read PNG/JPEG dimensions without decoding the image or importing ML packages."""
    with local(path).open('rb') as f:
        head = f.read(24)
        if head[:8] == b'\x89PNG\r\n\x1a\n':
            return struct.unpack('>II', head[16:24])
        if head[:2] != b'\xff\xd8':
            raise ValueError('Only JPEG and PNG page images are supported')
        f.seek(2)
        while True:
            byte = f.read(1)
            if not byte:
                break
            if byte != b'\xff':
                continue
            marker = f.read(1)
            while marker == b'\xff':
                marker = f.read(1)
            if marker in [b'\xd8', b'\xd9']:
                continue
            raw = f.read(2)
            if len(raw) != 2:
                break
            length = struct.unpack('>H', raw)[0]
            if marker and marker[0] in [0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf]:
                _, height, width = struct.unpack('>BHH', f.read(5))
                return width, height
            f.seek(length - 2, 1)
    raise ValueError('Cannot read image dimensions')


class Catalog:
    def __init__(self):
        split = read('corpus/learning_split.json')
        self.training = set(split['training_books'])
        self.validation = set(split['validation_books'])
        self.allowed = self.training | self.validation
        self.datasets = {}
        self.titles = {}
        self.warnings = []
        for path, key in [('corpus/benchmark_discovery/verified_candidates.json', None), ('corpus/training_seed/manifest.json', 'books')]:
            if local(path).exists():
                data = read(path)
                for b in data[key] if key else data:
                    self.titles[b['id']] = b.get('short_title') or b.get('title') or b['id']
        self.add_dataset('training', 'Reviewed training labels', 'training',
                         'Latest curated regions, lines, spans and initials. AI-reviewed silver; some pages contain only selected examples. Draft rows are a separate, optional layer.')
        self.add_dataset('cpu-training', 'CPU classifier training examples', 'training',
                         'Examples recorded in the CPU classifier training matrix, excluding augmented duplicates. Region outlines are context; only the displayed examples belong to this classifier snapshot.')
        self.add_dataset('validation', 'Validation reference', 'reference',
                         'Complete reviewed main-text windows on 16 development pages. AI-reviewed silver, not human gold. Surrounding unannotated material is not an omission claim.')
        self.build_training()
        self.build_original_book()
        # This exact sample was explicitly requested for test-set OCR. Other
        # reserved scans remain unavailable through the viewer.
        self.ocr_test_keys = set()
        ocr_manifest = local('corpus/ocr_test100_v1/manifest.json')
        if ocr_manifest.exists():
            self.add_dataset('ocr-test100', '100-page OCR test set', 'ocr',
                             'Fresh random test sample: 5 pages from each of 20 reserved books. Kraken OCR of all detected text; semantic labels have not been assigned.')
            for p in read(ocr_manifest)['pages']:
                if p['book'] not in set(split['sealed_test_books']):
                    raise ValueError('OCR test page is not from a reserved test book')
                self.ocr_test_keys.add(p['key'])
                self.titles[p['book']] = p['title']
                self.add_page('ocr-test100', p['book'], p['scan'], image=p['image'],
                              annotation=f"out/ocr_test100_v1/{p['book']}/{p['scan']:05d}.json")
        comparisons = [
            ('corpus/segmentation_bakeoff_v1/manifest.json', 'out/segmentation_bakeoff_v1'),
            ('corpus/surya_regions10_v1/manifest.json', 'out/surya_regions10_v1'),
            ('corpus/capricciosa10_v1/manifest.json', 'out/capricciosa10_v1'),
            ('corpus/dfine10_v1/manifest.json', 'out/dfine10_v1'),
            ('corpus/qwen8_10_v1/manifest.json', 'out/qwen8_10_v1'),
        ]
        for manifest_path, output_root in comparisons:
            comparison = local(manifest_path)
            if not comparison.exists():
                continue
            experiment = read(comparison)
            for system, config in experiment['systems'].items():
                ds = 'seg-' + system
                self.add_dataset(ds, config['name'], 'segmentation', config['description'])
                for p in experiment['pages']:
                    if p['key'] not in self.ocr_test_keys:
                        raise ValueError('Comparison page is outside the selected OCR set')
                    original = self.datasets['ocr-test100']['pages'][p['key']]
                    self.add_page(ds, p['book'], p['scan'], image=original['image'],
                                  annotation=f"{output_root}/{system}/{p['book']}/{p['scan']:05d}.json")
        self.build_webgpt()
        self.build_kraken_region_pack()
        self.review_page_keys = set(self.ocr_test_keys)
        self.build_surya_revision()
        self.build_region_constrained()
        self.build_original_regions()
        self.build_finetuned_kraken()
        self.build_instance_kraken()
        self.build_dfine_training()
        self.build_dfine_joint()
        self.build_orli_preview()
        self.build_historical_layout_previews()
        for p in read('corpus/expanded_seed/complete_validation_index.json')['pages']:
            if p['book'] in self.validation:
                self.add_page('validation', p['book'], p['scan'], annotation=p['annotation'], image=p['image'])
        runs = [
            ('cpu', 'CPU repair v1', 'out/cpu_repair_v1', 'Repaired lines, semantic spans and initial objects. Saved predictions; no inference runs in this app.'),
            ('gpu', 'GPU regions · 1152', 'out/gpu_regions_hr1152/parser', 'Saved high-resolution region-model run. Inspect which semantic labels are actually present.'),
            ('v2', 'Original pipeline v2', 'out/validation_pipeline_v2', 'The original 16-page validation predictions, before the CPU repair.'),
            ('run1', 'First corpus run', 'out/new_layout_test', 'Saved first-run predictions from training and development-validation books.'),
            ('pilot', 'Early pilot', 'out/new_layout_pilot', 'Early development predictions.'),
        ]
        for ds, name, folder, note in runs:
            files = sorted(local(folder).glob('*/predictions/*.json'))
            if not files:
                continue
            self.add_dataset(ds, name, 'prediction', note)
            for p in files:
                book = p.parent.parent.name
                # Never load sealed/quarantined records just to build the browser.
                if book in self.allowed and p.stem.isdigit():
                    self.add_page(ds, book, int(p.stem), annotation=relative(p))

        add_finished(self, ROOT)

    def add_dataset(self, key, name, kind, description):
        self.datasets[key] = dict(id=key, name=name, kind=kind, description=description, pages={})

    def build_webgpt(self):
        folder = 'out/webgpt_annotations100_v1'
        manifest = local(folder + '/input_manifest.json')
        if not manifest.exists():
            return
        pages = read(manifest)['pages']
        if len(pages) != 100 or {p['key'] for p in pages} != self.ocr_test_keys:
            raise ValueError('WebGPT annotations do not match the selected 100-page set')
        self.add_dataset('seg-webgpt', 'WebGPT · semantic annotations', 'segmentation',
            'All 100 returned pages: 99 partial; one blank page complete. Unreviewed LLM semantic regions, with labels projected onto clipped Surya lines. Regions preserve interior cutouts. Text anchors are not full transcriptions.')
        for p in pages:
            original = self.datasets['ocr-test100']['pages'][p['key']]
            self.add_page('seg-webgpt', original['book'], original['scan'], image=original['image'],
                annotation=f"{folder}/annotations/{p['key']}.json", expected_image=p['image'],
                semantic_labels_assigned=True, sources=[folder + '/coverage.json'])

    def build_kraken_region_pack(self):
        folder = 'out/kraken_region_annotations_v2'
        manifest = local(folder + '/manifest.json')
        if not manifest.exists():
            return
        pages = read(manifest)['pages']
        if len(pages) != 100 or {p['key'] for p in pages} != self.ocr_test_keys:
            raise ValueError('Kraken region annotations do not match the selected 100-page set')
        self.add_dataset('seg-kraken-regions-v2', 'WebGPT · Kraken region annotations', 'segmentation',
            '100 pages, one geometric class: TextRegion. Package marks 97 complete and 3 partial. Model-assisted annotations, not human-adjudicated gold. Rows show exported Kraken lines with recorded edits; no OCR or semantic labels.')
        for p in pages:
            original = self.datasets['ocr-test100']['pages'][p['key']]
            xml = f"{folder}/pagexml/{Path(p['image']['path']).stem}.xml"
            self.add_page('seg-kraken-regions-v2', original['book'], original['scan'], image=original['image'],
                annotation=f"{folder}/annotations/{p['key']}.json", expected_image=p['image'],
                adapter='region-pack', layout=xml, line_source=xml,
                sources=[xml, folder + '/ANNOTATION_PROVENANCE.json'])

    def build_surya_revision(self):
        path = 'out/region_surya_kraken_v4/manifest.json'
        if not local(path).exists():
            return
        manifest = read(path)
        pages = manifest['pages']
        training = [p for p in pages if p['partition'] == 'training']
        test = [p for p in pages if p['partition'] == 'test']
        if len(training) != 100 or len(test) != 20 or len({p['key'] for p in pages}) != 120:
            raise ValueError('Revised set must contain 100 training and 20 unique test pages')
        if {p['book'] for p in training} & {p['book'] for p in test}:
            raise ValueError('Revised training and test books overlap')
        import_folder = 'out/webgpt_regions_new24_v1'
        imported = local(import_folder + '/IMPORT_RECEIPT.json').exists()
        imported_keys = set()
        if imported:
            imported_keys = set(read(import_folder + '/IMPORT_RECEIPT.json')['page_keys'])
            if imported_keys != {p['key'] for p in pages if not p['annotation_source']}:
                raise ValueError('Returned region pages differ from the 24 new scan identities')
            self.add_dataset('seg-regions-new24', 'New 24 · WebGPT regions', 'segmentation',
                '292 returned TextRegion polygons on four training replacements and 20 test pages. Package marks all 24 complete for regions; review the boundaries here. Rows retain unchanged Surya lines and same-crop Kraken OCR, awaiting line correction.')
        review_sequence = 0
        for partition, group, name, note in [
            ('training', training, 'Training 100 · Surya + Kraken OCR',
             'Revised 100 training pages. Surya lines with Kraken OCR from those same crops; lines await correction. Existing regions retained on 96 pages; four replacement pages need regions.'),
            ('test', test, 'Test 20 new books · Surya + Kraken OCR',
             '20 held-out content pages from 20 new books. Surya lines with same-crop Kraken OCR. Lines await correction and regions await annotation. Excluded from model fitting and selection.'),
        ]:
            ds = f'seg-{partition}{len(group)}-v4'
            if imported:
                note = ('Revised 100 training pages. All pages now have region annotations, including the four returned replacements. '
                        if partition == 'training' else '20 held-out pages from new books, now with returned WebGPT regions. Excluded from model fitting and selection. ')
                note += 'Surya lines and same-crop Kraken OCR are unchanged; line correction is still pending.'
            self.add_dataset(ds, name, 'segmentation', note)
            for p in group:
                self.titles[p['book']] = p['title']
                self.review_page_keys.add(p['key'])
                descriptor = self.add_page(ds, p['book'], p['scan'], image=p['image'], annotation=p['annotation'],
                    expected_image=p['archive_image'], adapter='surya-regions', split=partition,
                    sequence=p['index'], display_id=f"{'P' if partition == 'training' else 'T'}{p['index']:03d}",
                    region_source=f"out/region_surya_kraken_v4/regions/{p['key']}.json" if p['annotation_source'] else None,
                    sources=[p['detection_source'], p['ocr_source'], path])
                if p['key'] in imported_keys:
                    overlay = f"{import_folder}/annotations/{p['key']}.json"
                    descriptor.update(region_overlay=overlay, region_source=overlay)
                    descriptor['sources'] += [overlay, import_folder + '/IMPORT_RECEIPT.json']
                    review_sequence += 1
                    data = {k:v for k,v in descriptor.items() if k not in ('book','scan','key','units')}
                    data['sequence'] = review_sequence
                    self.add_page('seg-regions-new24', p['book'], p['scan'], **data)

    def build_region_constrained(self):
        path = 'out/region_constrained_v5/manifest.json'
        if not local(path).exists():
            return
        manifest = read(path)
        review_path = 'out/region_constrained_v5/quality_review.json'
        review = read(review_path)['pages'] if local(review_path).exists() else {}
        for partition, count in [('training',100),('test',20)]:
            pages = [p for p in manifest['pages'] if p['partition']==partition]
            if len(pages)!=count or any(p['key'] not in self.review_page_keys for p in pages):
                raise ValueError('Constrained inference pages differ from the revised sample')
            ds = f'seg-constrained-{partition}{count}'
            self.add_dataset(ds, f'Region-constrained · {partition} {count}', 'segmentation',
                'Fresh Surya inference with its line probability map decoded separately inside each accepted region. Fresh Kraken OCR on masked line crops. Uses supplied region boundaries; automatic lines and text still need review. Compare with the previous whole-page run.')
            for p in pages:
                self.add_page(ds,p['book'],p['scan'],image=p['image'],annotation=p['constrained_annotation'],
                    expected_image=p['archive_image'],adapter='surya-regions',split=partition,
                    sequence=p['index'],display_id=f"{'P' if partition=='training' else 'T'}{p['index']:03d}",
                    review_flags=review.get(p['key'], []),
                    region_source=p['region_source'], sources=[p['region_source'],path])

    def build_original_regions(self):
        path = 'out/original_region_annotations120_v1/manifest.json'
        if not local(path).exists():
            return
        manifest = read(path)
        for partition, count in [('training', 100), ('evaluation', 20)]:
            pages = [p for p in manifest['pages'] if p['partition'] == partition]
            if len(pages) != count or any(p['key'] not in self.review_page_keys for p in pages):
                raise ValueError('Original region annotations differ from the existing 100/20 split')
            ds = f'seg-original-regions-{partition}{count}'
            self.add_dataset(ds, f'Original region annotations · {partition} {count}', 'segmentation',
                'Original accepted region polygons, preserved before D-FINE converted its training targets to boxes. Region contours only; no model predictions, lines or OCR. Copied unchanged from the original annotation sources.')
            for p in pages:
                self.add_page(ds, p['book'], p['scan'], image=p['image'], annotation=p['annotation'],
                    adapter='surya-regions', sequence=p['index'], split=partition,
                    display_id=f"{'P' if partition == 'training' else 'T'}{p['index']:03d}",
                    sources=[p['original_source'], path])

    def build_original_book(self):
        book = 'bsb10144443'
        if book not in self.allowed:
            raise ValueError('Original book is outside the development collection')
        self.titles.setdefault(book, 'Decretales Gregorii IX · Rome 1582')
        files = sorted(local(f'out/{book}/pages').glob('[0-9][0-9][0-9][0-9][0-9].json'))
        if files:
            self.add_dataset('legacy-book', 'Original classifier · full book', 'prediction',
                'All 1,072 saved scans from the original classifier, trained on weak labels. Primary-text blocks, classified lines, outside candidates and structural objects. OCR is from MDZ. No new inference.')
            for path in files:
                self.add_page('legacy-book', book, int(path.stem), annotation=relative(path),
                    image=f'data/{book}/images/{path.stem}.jpg', adapter='legacy', split='original book')
        html = local(f'out/{book}/gold_review/index.html')
        if html.exists():
            self.add_dataset('legacy-gold-review', 'Original gold review · 102 pages', 'reference',
                'The exact saved 102-page gold-review sample. Parser-derived, AI-reviewed silver rather than independent human gold. Coverage is limited to the original review windows; block outlines and objects are automatic context.')
            for page in review_index(html):
                stem = f'{page["scan"]:05d}'
                source = f'gold/{book}/{stem}.json'
                if not local(source).exists():
                    source = f'gold/{book}/draft/{stem}.json'
                review = read(source)
                snapshot = [dict(id=r['id'], label=r['label'], text=r.get('text', '')) for r in review['lines']]
                if snapshot != page['lines']:
                    raise ValueError(f'Original HTML review and saved labels disagree for scan {stem}')
                self.add_page('legacy-gold-review', book, page['scan'], annotation=source,
                    image=f'data/{book}/images/{stem}.jpg', layout=f'out/{book}/pages/{stem}.json',
                    adapter='legacy-review', split='review sample',
                    sources=[relative(html), f'out/{book}/pages/{stem}.json'])

        path = 'out/pero_interview_v1/manifest.json'
        if local(path).exists():
            manifest = read(path)
            self.add_dataset('legacy-pero-task', manifest['name'], 'prediction', manifest['description'])
            for p in manifest['pages']:
                self.add_page('legacy-pero-task', p['book'], p['scan'], image=p['image'],
                    annotation=f"out/pero_interview_v1/predictions/{p['key']}.json",
                    split='interview Task I', sources=[path])

        path = 'out/dfine_pero_interview_v1/manifest.json'
        if local(path).exists():
            manifest = read(path)
            self.add_dataset('legacy-dfine-pero-task', manifest['name'], 'prediction', manifest['description'])
            for p in manifest['pages']:
                self.add_page('legacy-dfine-pero-task', p['book'], p['scan'], image=p['image'],
                    annotation=f"out/dfine_pero_interview_v1/predictions/{p['key']}.json",
                    split='interview Task I', sources=[path])

        path = 'out/same_scheme10_v1/manifest.json'
        if local(path).exists():
            manifest = read(path)
            for ds, folder, name, description in [
                ('legacy-same-scheme-classified', 'classified', 'Same-scheme books · classified · 10 pages',
                 'One seeded random content page per user-selected edition, visually checked before inference. Our D-FINE epoch-14 regions, PERO lines and matching-crop OCR, then the unchanged task1_regions.py type-size selection and typographic/sequence classifier. All geometry and OCR retained; outside marks lines excluded by the classifier. Predictions for review, without accuracy labels or retraining.'),
                ('legacy-same-scheme-pero', 'pero', 'Same-scheme books · D-FINE + PERO OCR · 10 pages',
                 'Fresh D-FINE epoch-14 region predictions on the ten original scans. Native PERO detects lines within each fixed region and reads matching region-masked crops. No reference regions or annotations supplied. Same ten pages as the classified collection, before semantic classification.')]:
                self.add_dataset(ds, name, 'prediction', description)
                for p in manifest['pages']:
                    self.titles[p['book']] = p['title']
                    self.add_page(ds, p['book'], p['scan'], image=p['image'], sequence=p['index'],
                        annotation=f"out/same_scheme10_v1/{folder}/predictions/{p['key']}.json",
                        split='same-scheme transfer preview', sources=[path])

        path = 'out/central_block_annotations_v1/manifest.json'
        if local(path).exists():
            manifest = read(path)
            ds = 'legacy-webgpt-central-block'
            self.add_dataset(ds, manifest['name'], 'prediction', manifest['description'])
            for sequence, p in enumerate(manifest['pages'], 1):
                self.titles[p['book']] = p['title']
                self.add_page(ds, p['book'], p['scan'], image=p['image'], sequence=sequence,
                              annotation=p['annotation'], split=f"{p['partition']} · {p['imported_status']}",
                              sources=[path, f"out/central_block_annotations_v1/returned/annotations/{p['key']}.json"])

        path = 'out/qwen_text5_v1/manifest.json'
        if local(path).exists():
            manifest = read(path)
            ds = 'legacy-qwen-text5'
            self.add_dataset(ds, manifest['name'], 'prediction', manifest['description'])
            for sequence, p in enumerate(manifest['pages'], 1):
                prediction = f"out/qwen_text5_v1/predictions/{p['key']}.json"
                if local(prediction).exists():
                    self.titles[p['book']] = p['title']
                    self.add_page(ds, p['book'], p['scan'], image=p['image'], sequence=sequence,
                                  annotation=prediction, split='OCR-only exploratory trial', sources=[path])

        path = 'out/same_scheme_dataset_v1/manifest.json'
        if local(path).exists():
            manifest = read(path)
            for split in ('training', 'evaluation'):
                pages = [p for p in manifest['pages'] if p['partition'] == split]
                ds = f'legacy-same-scheme-{split}'
                self.add_dataset(ds, f'Same-scheme books · {split} · {len(pages)} pages', 'segmentation',
                    'Dataset preparation: our D-FINE epoch-14 region instances, fixed during native PERO line detection and matching-crop OCR. Content pages from ten editions; image-only content review before inference. No semantic classifier or corrected task labels yet. '
                    + ('Reserved page-level evaluation from the same books: ten earlier inspected pages plus ten new pages; not a sealed unseen-book test.' if split == 'evaluation' else 'Ten new pages per book, reserved for future classifier training.'))
                for sequence, p in enumerate(pages, 1):
                    self.titles[p['book']] = p['title']
                    self.add_page(ds, p['book'], p['scan'], image=p['image'], sequence=sequence,
                        annotation=p['prediction'], split=split, sources=[path, p['pagexml']])

        path = 'out/pretrained_layout_task_v1/manifest.json'
        if local(path).exists():
            manifest = read(path)
            for system, config in manifest['systems'].items():
                if system == 'pero':
                    continue  # Reuse the original PERO collection, including its OCR.
                ds = config['dataset']
                self.add_dataset(ds, config['name'] + ' · task pages 40–41', 'prediction', config['description'])
                for p in manifest['pages']:
                    self.add_page(ds, p['book'], p['scan'], image=p['image'],
                        annotation=f"{config['prediction_root']}/{p['key']}.json",
                        split='interview Task I', sources=[path])

    def build_finetuned_kraken(self):
        manifest_path='corpus/kraken_finetuned_new100_v1/manifest.json'
        if not local(manifest_path).exists():return
        manifest=read(manifest_path)
        for partition,ds,name in [
            ('new','seg-kraken-epoch11-new100','Kraken epoch 11 · 100 new pages'),
            ('interview','seg-kraken-epoch11-task','Kraken epoch 11 · Interview Task I')]:
            pages=[p for p in manifest['pages'] if p['partition']==partition]
            if not pages:continue
            self.add_dataset(ds,name,'segmentation',
                'Epoch-11 fine-tuned Kraken detects regions and lines from the raw image, then the existing Kraken recognizer reads those exact predicted lines. No supplied region boundaries or Surya detections. Automatic output; semantic summarium/inscriptio labels have not been assigned.')
            for p in pages:
                self.titles[p['book']]=p['title']
                self.add_page(ds,p['book'],p['scan'],image=p['image'],
                    annotation=f"out/kraken_finetuned_new100_v1/{p['book']}/{p['scan']:05d}.json",
                    split=partition,sequence=p['index'],display_id=p.get('slot',f"Task {p['scan']}"),
                    sources=[manifest_path,'models/kraken_finetuned_v1/default.json'])

    def build_instance_kraken(self):
        manifest_path='out/kraken_segmenter_training_v2/data_manifest.json'
        if not local(manifest_path).exists():return
        pages=read(manifest_path)['pages']
        pilot_keys={'bsb00026118/00051','bsb00026118/00137','bsb10494707/01009'}
        for ds,name,folder,selected in [
            ('seg-kraken-v2-pilot','Kraken v2 · overfit pilot (3 training pages)','pilot_native_lines',[p for p in pages if p['key'] in pilot_keys]),
            ('seg-kraken-v2-eval','Kraken v2 · current evaluation (20 pages)','full',[p for p in pages if p['training_role']=='evaluation'])]:
            self.add_dataset(ds,name,'segmentation',
                'Instance-aware Kraken with separate region cores and boundaries, followed by region-constrained line decoding. Latest saved evaluation predictions; no supplied reference regions. This collection shows segmentation only, without OCR. The three-page pilot is an overfit check, not an unseen-page accuracy test.')
            for p in selected:
                book,scan=p['key'].split('/')
                self.add_page(ds,book,int(scan),image=p['image'],
                    annotation=f"out/kraken_segmenter_training_v2/{folder}/latest_predictions/{p['key']}.json",
                    split=p['training_role'],sources=[manifest_path,'out/kraken_segmenter_training_v2/README.md'])

    def build_dfine_training(self):
        manifest_path='out/dfine_region_training_v1/data_manifest.json'
        if not local(manifest_path).exists():return
        pages=read(manifest_path)['pages']
        pilot_keys={'bsb00026118/00051','bsb00026118/00137','bsb10494707/01009'}
        for ds,name,folder,selected in [
            ('seg-dfine-pilot','D-FINE Large · fine-tuning pilot (3 training pages)','pilot',[p for p in pages if p['key'] in pilot_keys]),
            ('seg-dfine-eval','D-FINE Large · fine-tuned evaluation (20 pages)','full',[p for p in pages if p['training_role']=='evaluation'])]:
            self.add_dataset(ds,name,'segmentation',
                'REGION-ONLY run: LADaS D-FINE Large fine-tuned on the 100 accepted-region pages, with every polygon converted separately to a bounding box. Resumed from epoch 15 / step 1500 at user request. This collection updates with each evaluation on all 20 held-out pages at threshold 0.50; each page JSON records its epoch and step. No reference regions are supplied at inference; no line detector or OCR is included. Evaluation pages monitor training and select checkpoints. Pilot is a training overfit check.')
            for p in selected:
                book,scan=p['key'].split('/')
                self.add_page(ds,book,int(scan),image=p['image'],
                    annotation=f"out/dfine_region_training_v1/{folder}/latest_predictions/{p['key']}.json",
                    split=p['training_role'],sources=[manifest_path])

    def build_dfine_joint(self):
        manifest_path='out/dfine_joint_training_v1/data_manifest.json'
        if local(manifest_path).exists():
            pages=read(manifest_path)['pages']
            pilot_keys={'bsb00026118/00051','bsb00026118/00137','bsb10494707/01009'}
            for ds,name,folder,selected in [
                ('seg-dfine-joint-pilot','D-FINE JOINT lines + regions · pilot (3 pages)','pilot',[p for p in pages if p['key'] in pilot_keys]),
                ('seg-dfine-joint-eval','D-FINE JOINT lines + regions · evaluation (20 pages)','full',[p for p in pages if p['training_role']=='evaluation'])]:
                self.add_dataset(ds,name,'segmentation','One D-FINE Large detection head jointly predicts line boxes and independent region boxes. 600 queries, 1536px input. Region and line layers both come from this model; no supplied reference regions or OCR. Pilot is a training overfit check; evaluation pages are excluded from training.')
                for p in selected:
                    book,scan=p['key'].split('/')
                    self.add_page(ds,book,int(scan),image=p['image'],annotation=f"out/dfine_joint_training_v1/{folder}/latest_predictions/{p['key']}.json",split=p['training_role'],sources=[manifest_path])
        path='out/dfine_saved_epoch15_random10/manifest.json'
        if local(path).exists():
            manifest=read(path);ds='seg-dfine-saved15-random10'
            self.add_dataset(ds,manifest['name'],'segmentation',manifest['description'])
            for p in manifest['pages']:
                self.add_page(ds,p['book'],p['scan'],image=p['image'],annotation=f"out/dfine_saved_epoch15_random10/predictions/{p['key']}.json",split='new random preview',sources=[path])

    def build_orli_preview(self):
        path = 'out/orli_random10_v1/manifest.json'
        if not local(path).exists():
            return
        manifest = read(path)
        ds = 'seg-orli-random10'
        self.add_dataset(ds, manifest['name'], 'segmentation', manifest['description'])
        for p in manifest['pages']:
            self.add_page(ds, p['book'], p['scan'], image=p['image'],
                annotation=f"out/orli_random10_v1/predictions/{p['key']}.json",
                split='new random preview', sources=[path])

    def build_historical_layout_previews(self):
        for system in ('pero', 'eynollah'):
            folder = f'out/{system}_random10_v1'
            path = folder + '/manifest.json'
            if not local(path).exists():
                continue
            manifest = read(path)
            ds = f'seg-{system}-random10'
            self.add_dataset(ds, manifest['name'], 'segmentation', manifest['description'])
            for p in manifest['pages']:
                self.add_page(ds, p['book'], p['scan'], image=p['image'],
                    annotation=f"{folder}/predictions/{p['key']}.json",
                    split='new random preview', sources=[path])

        book = 'bsb10144443'
        nnp = sorted(local('out/line_nn_v1/predictions').glob('*/[0-9][0-9][0-9][0-9][0-9].json'))
        if nnp:
            self.add_dataset('legacy-line-nn', 'Neural line classifier · held-out book · 10 pages', 'prediction',
                'line_nn: CNN on the grey line image + character CNN on the PERO text + layout numbers, BiGRU over the lines of each D-FINE region. Each page was labelled by a model that never saw that book. Click a line: the note gives the network label, the rule label and the reference label. Reference labels are model-drafted, not human gold.')
            for path in nnp:
                rec = read(relative(path))
                self.titles.setdefault(rec['book'], rec['book'])
                self.add_page('legacy-line-nn', rec['book'], rec['scan'], annotation=relative(path),
                    image=rec['image']['path'].replace('\\', '/'), split='held-out book')
        nn3 = sorted(local('out/line_nn_v3/predictions').glob('*/[0-9][0-9][0-9][0-9][0-9].json'))
        if nn3:
            self.add_dataset('legacy-line-nn-v3', f'Transformer taggers v3 · evaluation pages · {len(nn3)} pages', 'prediction',
                'line_nn_v3 on the 20 evaluation pages, exactly as scored in the training run. Duplicate D-FINE boxes were removed by hand (annotation); a region tagger picks the central block and a line tagger labels its lines. Red = label differs from the reference. Both are small transformers trained from scratch on the 100 training pages, on colour pictures, raw OCR characters and raw coordinates. The evaluation pages were used to choose the best training round. Click a line: network label, confidence and reference label.')
            for path in nn3:
                rec = read(relative(path))
                self.titles.setdefault(rec['book'], rec['book'])
                self.add_page('legacy-line-nn-v3', rec['book'], rec['scan'], annotation=relative(path),
                    image=rec['image']['path'].replace('\\', '/'), split='evaluation page')
        nn3t = sorted(local(f'out/line_nn_v3/task_predictions/{book}').glob('[0-9][0-9][0-9][0-9][0-9].json'))
        if nn3t:
            self.add_dataset('legacy-line-nn-v3-task', 'Transformer taggers v3 · task pages 40-41', 'prediction',
                'line_nn_v3 on the two interview task pages of the 1582 Decretals, on our D-FINE regions and PERO lines/OCR. Both taggers were trained on 100 pages of ten other editions and never saw this book. Click a line: network label, confidence and the label of the rule classifier task1_regions.py.')
            for path in nn3t:
                self.add_page('legacy-line-nn-v3-task', book, int(path.stem), annotation=relative(path),
                    image=f'data/{book}/images/{path.stem}.jpg', split='original book · unseen by the taggers')
        nn2 = sorted(local('out/line_nn_v2/predictions').glob('*/[0-9][0-9][0-9][0-9][0-9].json'))
        if nn2:
            self.add_dataset('legacy-line-nn-v2', f'Neural line tagger v2 · evaluation pages · {len(nn2)} pages', 'prediction',
                'line_nn_v2 on the 20 frozen evaluation pages; trained on the 100 training pages only. Duplicate D-FINE detections dropped by a line-twin rule, a region model selects the central block, then CNN on the grey line image + character CNN on the PERO text + layout numbers, BiGRU over the whole central block of the page, CRF output. Click a line: the note gives the network label, its confidence and the reference label. Reference labels are reviewed LLM annotations, not independent human gold.')
            for path in nn2:
                rec = read(relative(path))
                self.titles.setdefault(rec['book'], rec['book'])
                self.add_page('legacy-line-nn-v2', rec['book'], rec['scan'], annotation=relative(path),
                    image=rec['image']['path'].replace('\\', '/'), split='frozen evaluation page')
        nn2t = sorted(local(f'out/line_nn_v2/task_predictions/{book}').glob('[0-9][0-9][0-9][0-9][0-9].json'))
        if nn2t:
            self.add_dataset('legacy-line-nn-v2-task', 'Neural line tagger v2 · task pages 40-41', 'prediction',
                'line_nn_v2 on the two interview task pages of the 1582 Decretals, on our D-FINE regions and PERO lines/OCR. The tagger was trained on 100 pages of ten other editions and never saw this book. Click a line: the note gives the network label, its confidence and the label of the rule classifier task1_regions.py.')
            for path in nn2t:
                self.add_page('legacy-line-nn-v2-task', book, int(path.stem), annotation=relative(path),
                    image=f'data/{book}/images/{path.stem}.jpg', split='original book · unseen by the tagger')
        t1r = sorted(local(f'out/task1_regions_v1/{book}').glob('[0-9][0-9][0-9][0-9][0-9].json'))
        if t1r:
            self.add_dataset('legacy-task1-regions', 'Region + line classifier on D-FINE regions and PERO lines · task pages 40-41', 'prediction',
                'task1_regions.py: (1) the D-FINE regions set in the larger type are chosen as text blocks; (2) each PERO line in them is labelled from red ink, slant and letter size, read top to bottom in the order of the edition (inscriptio, summarium, heading, text). Regions and lines are unchanged inputs. No training.')
            for path in t1r:
                self.add_page('legacy-task1-regions', book, int(path.stem), annotation=relative(path),
                    image=f'data/{book}/images/{path.stem}.jpg', split='original book')
        simple = sorted(local(f'out/simple_task1_v1/{book}').glob('[0-9][0-9][0-9][0-9][0-9].json'))
        if simple:
            self.add_dataset('legacy-simple-task', 'Simple two-step labeller on PERO lines · task pages 40-41', 'prediction',
                'simple_task1.py: (1) block per column from the lines in the larger type; (2) each PERO line in the block labelled by red ink, slant and letter size with four thresholds. No training. Lines outside the blocks are not shown.')
            for path in simple:
                self.add_page('legacy-simple-task', book, int(path.stem), annotation=relative(path),
                    image=f'data/{book}/images/{path.stem}.jpg', split='original book')
        mdz = sorted(local(f'out/mdz_hocr_v1/{book}').glob('[0-9][0-9][0-9][0-9][0-9].json'))
        if mdz:
            self.add_dataset('legacy-mdz-hocr', 'MDZ hOCR as served · task pages 40-41', 'prediction',
                'Exactly what the MDZ OCR endpoint returns for the two task pages: paragraph, line and word boxes with text. No blocks or columns, no font or italic information, no baselines, no confidences. Nothing was recomputed.')
            for path in mdz:
                self.add_page('legacy-mdz-hocr', book, int(path.stem), annotation=relative(path),
                    image=f'data/{book}/images/{path.stem}.jpg', split='original book')

    def add_page(self, ds, book, scan, **data):
        key = f'{book}/{int(scan):05d}'
        pages = self.datasets[ds]['pages']
        if key not in pages:
            pages[key] = dict(book=book, scan=int(scan), key=key, units={}, sources=[])
        pages[key].update(data)
        return pages[key]

    def build_training(self):
        for p in read('corpus/training_seed/index.json')['pages']:
            if p['book'] in self.training:
                self.add_page('training', p['book'], p['scan'], annotation=p['annotation'], image=p['image'])
        audit = read('corpus/expanded_seed/region_audit_decisions.json')['pages']
        for p in read('corpus/benchmark_run1/reference_index.json')['pages']:
            if p['book'] in self.training:
                review = audit.get(p['book'], {})
                path = review.get('development_annotation_path') or p['annotation']
                self.add_page('training', p['book'], p['scan'], annotation=path, image=p['image'])
        source_index = read('corpus/expanded_seed/combined_source_index.json')
        for component in source_index['components']:
            source = component['path']
            for row in read(source).get('entries', []):
                if row['book'] not in self.training:
                    continue
                page = self.add_page('training', row['book'], row['scan'])
                page.setdefault('image', row['image'])
                unit = dict(row, viewer_source=source)
                if component['unit_kind'] == 'structural_objects':
                    unit['viewer_kind'] = 'object'
                elif component['unit_kind'] == 'semantic_spans':
                    unit['viewer_kind'] = 'span'
                else:
                    unit['viewer_kind'] = 'row'
                page['units'][row['id']] = unit
                if source not in page['sources']:
                    page['sources'].append(source)
        # Match the actual fitted training snapshot, not the newer curation inventory.
        metadata = read('book_layout_cpu/work/train_meta.json')
        labels = {m['id']: LABELS[m['y']] for m in metadata if m['part'] == 'training' and not m['aug']}
        candidates = {}
        for row in read('out/fusion_dataset_v2/index.json')['rows']:
            if row['partition'] == 'training':
                candidates[row['id']] = dict(row, viewer_source='out/fusion_dataset_v2/index.json', viewer_kind='row')
        for source in ['corpus/expanded_seed/mixed_semantic_seed.json', 'corpus/expanded_seed/civil_inscription_seed.json']:
            for row in read(source)['entries']:
                if row['book'] not in self.training:
                    continue
                for unit in row.get('spans') or [row]:
                    context = {k: row[k] for k in ('book', 'scan', 'image')}
                    context.update({k: v for k, v in unit.items() if k != 'spans'})
                    context.update(viewer_source=source, viewer_kind='span',
                                   viewer_parent=row['id'] if row.get('spans') else None)
                    candidates[unit['id']] = context
        for uid, label in labels.items():
            if uid not in candidates:
                self.warnings.append(f'Training example unavailable: {uid}')
                continue
            unit = dict(candidates[uid], label=label)
            page = self.add_page('cpu-training', unit['book'], unit['scan'], image=unit['image'])
            key = page['key']
            base = self.datasets['training']['pages'].get(key, {})
            if base.get('annotation'):
                page['annotation'] = base['annotation']
            page['units'][uid] = unit
            if unit['viewer_source'] not in page['sources']:
                page['sources'].append(unit['viewer_source'])

    def index(self):
        datasets = []
        for ds in self.datasets.values():
            rows = []
            for p in ds['pages'].values():
                rows.append(dict(key=p['key'], book=p['book'], scan=p['scan'], title=self.titles.get(p['book'], p['book']),
                                 sequence=p.get('sequence', 0), display_id=p.get('display_id', ''),
                                 split=p.get('split') or ('test' if ds['kind'] in ('ocr', 'segmentation') else 'training' if p['book'] in self.training else 'validation'),
                                 semantic_units=len(p['units']),
                                 ocr_ready=local(p['annotation']).exists() if ds['kind'] in ('ocr', 'segmentation') else None,
                                 counterparts=[k for k, d in self.datasets.items() if p['key'] in d['pages'] and k != ds['id']]))
            datasets.append(dict(**{k: v for k, v in ds.items() if k != 'pages'}, pages=sorted(rows, key=lambda p: (p['sequence'], p['book'], p['scan'])),
                                 completed_pages=sum(p['ocr_ready'] is True for p in rows) if ds['kind'] in ('ocr', 'segmentation') else None))
        return dict(datasets=datasets, warnings=self.warnings, excluded_books='Only explicitly selected scan identities are exposed from the original OCR sample and revised 100/20 dataset.', read_only=True)

    def page(self, dataset, key):
        descriptor = self.datasets[dataset]['pages'][key]
        path = local(descriptor['annotation']) if descriptor.get('annotation') else None
        stamp = path.stat().st_mtime_ns if path and path.exists() else 0
        if descriptor.get('layout'):
            stamp = (stamp, local(descriptor['layout']).stat().st_mtime_ns)
        if descriptor.get('region_overlay'):
            stamp = (stamp, local(descriptor['region_overlay']).stat().st_mtime_ns)
        return self._page(dataset, key, stamp)

    @lru_cache(maxsize=96)
    def _page(self, dataset, key, source_mtime):
        descriptor = self.datasets[dataset]['pages'][key]
        ds = self.datasets[dataset]
        pending = ds['kind'] in ('ocr', 'segmentation') and not source_mtime
        record = read(descriptor['annotation']) if descriptor.get('annotation') and not pending else {}
        image_path = descriptor.get('image') or record['image']['path']
        size = image_size(image_path)
        if descriptor.get('expected_image'):
            expected = descriptor['expected_image']
            if size != (expected['width'], expected['height']) or (not pending and (record['key'] != key or record['image'] != expected)):
                raise ValueError('Imported annotation identity or image dimensions differ from source scan')
        if descriptor.get('adapter') == 'region-pack':
            record = adapt_region_pack(record, local(descriptor['layout']))
        if descriptor.get('region_overlay'):
            overlay = read(descriptor['region_overlay'])
            if (overlay['key'] != key or overlay['image'] != descriptor['expected_image']
                    or overlay['partition'] != descriptor['split']
                    or overlay['training_forbidden'] != (descriptor['split'] == 'test')):
                raise ValueError('Returned region identity, image or partition differs from the source page')
            record['regions'] = overlay['regions']
            record['region_annotation_status'] = overlay['annotation_status']
            record['annotation_status'] = f"regions_{overlay['annotation_status']}_lines_awaiting_correction"
            record['notes'] = overlay.get('notes', '')
            record['provenance'] = dict(record.get('provenance', {}), region_source=descriptor['region_overlay'],
                region_import_receipt='out/webgpt_regions_new24_v1/IMPORT_RECEIPT.json')
        if descriptor.get('adapter') == 'surya-regions':
            record['regions'] = [dict(r, label='text_region',
                review_status='imported_webgpt_region_annotation' if descriptor.get('region_overlay') else 'retained_region_annotation',
                geometry_review_status='unchanged_source_polygon') for r in record.get('regions', [])]
        if descriptor.get('adapter') in ('legacy', 'legacy-review'):
            layout = read(descriptor['layout']) if descriptor.get('layout') else record
            if list(size) != list(reversed(layout['shape'])):
                raise ValueError('Original parser dimensions differ from source image')
            record = adapt_legacy(layout, record if descriptor['adapter'] == 'legacy-review' else None)
        objects = []
        seen = {}

        def add(unit, kind, source, parent=None, draft=False):
            polygon = unit.get('polygon')
            box = unit.get('bbox')
            baseline_only = not polygon and bool(unit.get('baseline'))
            if baseline_only:
                # Preserve the model's open curve; do not invent a line polygon.
                polygon = unit['baseline']
            elif not polygon and box:
                a, b, c, d = box
                polygon = [[a, b], [c, b], [c, d], [a, d]]
            if not polygon:
                return
            if not box:
                box = [min(p[0] for p in polygon), min(p[1] for p in polygon), max(p[0] for p in polygon), max(p[1] for p in polygon)]
            label = unit.get('label') or unit.get('role') or ('mixed' if unit.get('spans') else unit.get('region_role')) or ('ocr' if ds['kind'] == 'ocr' else 'unknown')
            uid = str(unit.get('id') or f'{kind}_{len(objects)}')
            identity = kind + ':' + uid
            review = unit.get('review_status') or unit.get('label_review_status') or ('unreviewed_prediction' if ds['kind'] == 'prediction' else 'status_not_recorded')
            item = dict(id=identity, source_id=uid, kind=kind, label=label, polygon=polygon, bbox=box,
                                geometry_type='baseline' if baseline_only else 'polygon',
                                holes=unit.get('holes', []), components=unit.get('components', []),
                                line_ids=unit.get('line_ids', []), baseline=unit.get('baseline'),
                                input_line_refs=unit.get('input_line_refs', []), subtype=unit.get('subtype'),
                                parent=parent or (unit.get('region_ids') or [None])[0],
                                draft=draft, text=unit.get('text') or unit.get('ocr_text') or unit.get('source_reading_excerpt') or '',
                                review_status=review, geometry_status=unit.get('geometry_review_status') or unit.get('boundary_status') or '',
                                certainty=unit.get('certainty') or unit.get('label_certainty') or '',
                                probabilities=unit.get('label_probabilities') or unit.get('region_probabilities') or {},
                                note=unit.get('source_review_note') or unit.get('note') or unit.get('notes') or unit.get('provenance') or '',
                                source=relative(source), counts_as_task_unit=unit.get('counts_as_task_unit', True),
                                reading_order=unit.get('reading_order'), spatial_role=unit.get('region_role'),
                                ocr_confidence=unit.get('confidence'), detection_score=unit.get('detection_score'),
                                classification_score=unit.get('classification_score'),
                                mistake=unit.get('mistake'), mistake_reason=unit.get('mistake_reason') or '')
            if identity in seen:
                objects[seen[identity]] = item
            else:
                seen[identity] = len(objects)
                objects.append(item)

        source = descriptor.get('annotation', '')
        context_source = descriptor.get('layout', source) if descriptor.get('adapter') == 'legacy-review' else source
        if descriptor.get('region_source'):
            context_source = descriptor['region_source']
        for region in record.get('regions', []):
            add(region, 'object' if region.get('role') == 'initial' and dataset != 'cpu-training' else 'region', context_source)
        if ds['kind'] == 'training':
            if dataset == 'training':
                for line in record.get('lines', []):
                    add(line, 'draft', source, draft=True)
            for unit in descriptor['units'].values():
                kind = unit.get('viewer_kind', 'row')
                add(unit, kind, unit['viewer_source'], parent=unit.get('viewer_parent'))
                for span in unit.get('spans', []):
                    add(span, 'span', unit['viewer_source'], parent=unit['id'])
        else:
            for line in record.get('lines', []):
                add(line, 'row', descriptor.get('line_source', source))
                for span in line.get('semantic_spans') or line.get('spans') or []:
                    add(span, 'span', source, parent=line['id'])
            for unit in record.get('structural_units', []):
                add(unit, 'object', context_source)
        counts = dict(Counter(o['label'] for o in objects if o['kind'] not in ('draft', 'region')))
        return dict(dataset=dataset, dataset_name=ds['name'], kind=ds['kind'], key=key, book=descriptor['book'], scan=descriptor['scan'],
                    pending=pending, semantic_labels_assigned=record.get('semantic_labels_assigned', descriptor.get('semantic_labels_assigned', False)),
                    annotation_status=record.get('annotation_status'),
                    region_annotation_status=record.get('region_annotation_status'),
                    line_annotation_status=record.get('line_annotation_status'), provenance=record.get('provenance'),
                    has_ocr=any(bool(line.get('text')) for line in record.get('lines', [])),
                    page_notes=record.get('notes', ''),
                    title=self.titles.get(descriptor['book'], descriptor['book']), image_path=relative(image_path),
                    image=dict(width=size[0], height=size[1]), objects=objects, counts=counts,
                    description=ds['description'], sources=([relative(source)] if source else []) + descriptor['sources'],
                    flags=record.get('qa', {}).get('flags', []) + record.get('warnings', []) + descriptor.get('review_flags', []), page_type=record.get('page_type'),
                    note='Region outlines and reviewed examples may have different coverage. Empty areas are not necessarily reviewed negatives.' if ds['kind'] == 'training' else ds['description'])


class PortableCatalog:
    """Read a self-contained snapshot without the development checkout."""
    def __init__(self):
        self.snapshot = read('viewer_data/index.json')
        self.datasets = {
            d['id']: dict(d, pages={p['key']: p for p in d['pages']})
            for d in self.snapshot['datasets']
        }

    def index(self):
        return self.snapshot

    @lru_cache(maxsize=24)
    def page(self, dataset, key):
        return read(self.datasets[dataset]['pages'][key]['annotation'])


def handler_for(catalog):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, raw, mime='application/json; charset=utf-8', status=200):
            if not isinstance(raw, bytes):
                raw = json.dumps(raw, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            try:
                if url.path in ['/', '/app.js', '/style.css']:
                    asset = ASSETS / ('index.html' if url.path == '/' else url.path[1:])
                    mime = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript'}[asset.suffix]
                    return self.respond(asset.read_bytes(), mime + '; charset=utf-8')
                if url.path == '/api/health':
                    return self.respond(dict(app='petrius-annotation-desk', root=str(ROOT)))
                if url.path == '/api/index':
                    return self.respond(catalog.index())
                if url.path == '/api/ocr-status':
                    ds = catalog.datasets.get(q.get('dataset', ['ocr-test100'])[0], {'pages': {}})
                    return self.respond(dict(ready=[k for k,p in ds['pages'].items() if local(p['annotation']).exists()], total=len(ds['pages'])))
                if url.path in ['/api/page', '/image', '/text']:
                    page = catalog.page(q.get('dataset', [''])[0], q.get('key', [''])[0])
                    if url.path == '/api/page':
                        return self.respond(page)
                    if url.path == '/text':
                        if not page['has_ocr']:
                            return self.respond(dict(error='No OCR text stored for this page'), status=404)
                        rows = [o for o in page['objects'] if o['kind'] == 'row']
                        content = '\n'.join(f"{r['source_id']}\t{r['text']}" for r in rows) + '\n'
                        return self.respond(content.encode('utf-8'), 'text/plain; charset=utf-8')
                    path = local(page['image_path'])
                    return self.respond(path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
                return self.respond(dict(error='Not found'), status=404)
            except (KeyError, ValueError, FileNotFoundError) as error:
                return self.respond(dict(error='Page unavailable: ' + str(error)), status=404)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def log_message(self, *args):
            pass
    return Handler


def static_handler():
    """Serve the checked-in web viewer when the optional offline images are absent."""
    class StaticHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / 'site'), **kwargs)

        def do_GET(self):
            if urlparse(self.path).path == '/api/health':
                data = json.dumps(dict(app='petrius-annotation-desk', root=str(ROOT))).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                super().do_GET()

        def log_message(self, *args):
            pass
    return StaticHandler


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port', type=int, default=8877)
    ap.add_argument('--open', action='store_true', help='Open in your default browser')
    ap.add_argument('--static', action='store_true', help='Use the web viewer and library-hosted images')
    args = ap.parse_args()
    request_handler = None
    for port in range(args.port, min(args.port + 20, 65536)):
        url = f'http://127.0.0.1:{port}/'
        # Reuse this copy; another checkout may already occupy the default port.
        try:
            with urlopen(url + 'api/health', timeout=1) as response:
                health = json.load(response)
            if health.get('app') == 'petrius-annotation-desk' and health.get('root') == str(ROOT):
                if args.open:
                    webbrowser.open(url)
                print(f'Annotation desk already running: {url}', flush=True)
                return
            # Do not bind over another checkout's listener on Windows.
            continue
        except (OSError, ValueError):
            pass
        if request_handler is None:
            offline = local('viewer_data/index.json').exists()
            if args.static or (not offline and local('site/data/index.json').exists()):
                request_handler = static_handler()
            else:
                request_handler = handler_for(PortableCatalog() if offline else Catalog())
        try:
            server = ThreadingHTTPServer(('127.0.0.1', port), request_handler)
            break
        except OSError as error:
            if error.errno not in (48, 98, 10048):
                raise
    else:
        raise OSError('No available local port; choose another with --port.')
    print(f'Annotation desk: {url} (read-only; no models loaded)', flush=True)
    if args.open:
        threading.Timer(.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

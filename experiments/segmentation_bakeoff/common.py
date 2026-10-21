import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/segmentation_bakeoff'
MANIFEST = ROOT / 'data/segmentation_bakeoff/manifest.json'
SOURCE = ROOT / 'data/segmentation_bakeoff/source.json'
SYSTEMS = {
    'surya': dict(name='Surya · text lines', level='line',
                  source='https://github.com/datalab-to/surya',
                  description='Stock Surya text-line detector, default thresholds. Geometry only; no OCR or task labels.'),
    'ppdoclayout': dict(name='PP-DocLayoutV3 · blocks', level='region',
                       model='PaddlePaddle/PP-DocLayoutV3_safetensors',
                       source='https://huggingface.co/PaddlePaddle/PP-DocLayoutV3_safetensors',
                       description='Stock PP-DocLayoutV3 block polygons and reading order through the official Transformers implementation. Blocks are not individual lines.'),
    'ppocr': dict(name='PP-OCRv5 · text lines', level='line',
                 model='PaddlePaddle/PP-OCRv5_server_det_safetensors',
                 source='https://huggingface.co/PaddlePaddle/PP-OCRv5_server_det_safetensors',
                 description='Stock PP-OCRv5 server text detector through the official Transformers implementation. Default thresholds; geometry only.'),
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.part')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def prepare():
    if MANIFEST.exists():
        manifest = read(MANIFEST)
        assert manifest['source_sha256'] == sha(SOURCE)
        return manifest
    source = read(SOURCE)
    manifest = dict(source=SOURCE.relative_to(ROOT).as_posix(), source_sha256=sha(SOURCE),
                    policy='All 100 original pages; no resampling, training, or threshold tuning. Qualitative comparison, not a scored gold benchmark.',
                    systems=SYSTEMS, pages=source['pages'])
    write(MANIFEST, manifest)
    return manifest

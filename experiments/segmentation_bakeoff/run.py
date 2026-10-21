"""Run a frozen pretrained detector with stock processing, one page at a time."""
import argparse
import importlib.metadata
import json
import os
import sys
import time
import traceback

from .common import MANIFEST, OUT, ROOT, SYSTEMS, prepare, read, sha, write


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, 'detach'):
        return value.detach().cpu().tolist()
    if hasattr(value, 'tolist'):
        return value.tolist()
    return value


def unit(index, polygon, score, label, order):
    polygon = [[float(x), float(y)] for x, y in polygon]
    return dict(id=f'detection_{index:04d}', polygon=polygon,
                bbox=[min(p[0] for p in polygon), min(p[1] for p in polygon),
                      max(p[0] for p in polygon), max(p[1] for p in polygon)],
                label=label, detector_label=label, detection_score=float(score) if score is not None else None,
                reading_order=order, text='', review_status='unreviewed_prediction',
                geometry_review_status='stock_pretrained_detector',
                note='Detection only. No transcription or summarium/inscriptio/text/other task label has been assigned.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--system', choices=SYSTEMS, required=True)
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
    os.environ.setdefault('HF_HUB_DISABLE_PROGRESS_BARS', '1')
    os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
    import torch
    from PIL import Image
    torch.set_num_threads(4)
    assert torch.cuda.is_available(), 'GPU required; no silent CPU fallback'
    manifest = prepare()
    spec = SYSTEMS[args.system]
    folder = OUT / args.system
    folder.mkdir(parents=True, exist_ok=True)
    signature = dict(system=args.system, manifest_sha256=sha(MANIFEST),
                     torch=torch.__version__, gpu=torch.cuda.get_device_name(0), device='cuda:0',
                     batch_size=1, custom_layout_rules=False, fine_tuned=False,
                     source=spec['source'], level=spec['level'])
    print('LOAD ' + args.system, flush=True)
    if args.system == 'surya':
        os.environ['TORCH_DEVICE'] = 'cuda'
        os.environ['DETECTOR_BATCH_SIZE'] = '1'
        os.environ['DETECTOR_SERVER_AUTOSTART'] = 'false'
        os.environ['MODEL_CACHE_DIR'] = str(ROOT / 'models/segmentation_bakeoff/surya')
        from surya.detection import DetectionPredictor
        from surya.settings import settings
        detector = DetectionPredictor.local(device='cuda')
        assert next(detector.model.parameters()).is_cuda
        signature.update(surya=importlib.metadata.version('surya-ocr'),
                         model=settings.DETECTOR_MODEL_CHECKPOINT,
                         thresholds=dict(text=settings.DETECTOR_TEXT_THRESHOLD, blank=settings.DETECTOR_BLANK_THRESHOLD),
                         chunk_height=settings.DETECTOR_IMAGE_CHUNK_HEIGHT,
                         precision=str(next(detector.model.parameters()).dtype),
                         processor=detector.processor.to_dict())

        def predict(image):
            result = detector([image])[0]
            raw = result.model_dump(mode='json')
            units = [unit(i, b['polygon'], b.get('confidence'), 'detected_line', None)
                     for i, b in enumerate(raw['bboxes'])]
            return raw, units, []
    else:
        from huggingface_hub import HfApi, snapshot_download
        from transformers import AutoImageProcessor, AutoModelForObjectDetection
        model_folder = ROOT / 'models/segmentation_bakeoff' / args.system
        provenance = model_folder / 'provenance.json'
        revision = read(provenance)['revision'] if provenance.exists() else spec['revision']
        snapshot_download(spec['model'], revision=revision, local_dir=model_folder,
                          allow_patterns=['*.safetensors', 'config.json', 'preprocessor_config.json'])
        write(provenance, dict(model=spec['model'], revision=revision,
                              weights_sha256=sha(model_folder/'model.safetensors')))
        model = AutoModelForObjectDetection.from_pretrained(model_folder, local_files_only=True).to('cuda').eval()
        processor = AutoImageProcessor.from_pretrained(model_folder, local_files_only=True)
        assert next(model.parameters()).is_cuda
        signature.update(transformers=importlib.metadata.version('transformers'), **read(provenance),
                         processor=processor.to_dict(), precision='float32')

        def predict(image):
            inputs = processor(images=image, return_tensors='pt').to('cuda')
            target_sizes = inputs.pop('target_sizes', [image.size[::-1]])
            with torch.inference_mode():
                output = model(**inputs)
            result = processor.post_process_object_detection(output, target_sizes=target_sizes)[0]
            raw = plain(result)
            units = []
            if args.system == 'ppdoclayout':
                for i, (score, label, box, polygon) in enumerate(zip(raw['scores'], raw['labels'], raw['boxes'], raw['polygon_points'])):
                    # The processor may return None for an empty mask; retain its
                    # own bounding box solely as the display representation.
                    if polygon is None or len(polygon) < 3:
                        a,b,c,d = box
                        polygon = [[a,b],[c,b],[c,d],[a,d]]
                    units.append(unit(i, polygon, score, 'layout_' + model.config.id2label[int(label)], i))
                return raw, [], units
            for i, (score, polygon) in enumerate(zip(raw['scores'], raw['boxes'])):
                units.append(unit(i, polygon, score, 'detected_line', None))
            return raw, units, []

    if args.system == 'surya':
        signature['model_files'] = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT/'models/segmentation_bakeoff/surya').rglob('*')
                                    if p.is_file() and p.suffix in ('.safetensors', '.json')}
    # Compare the same JSON representation on resume (processor configs contain
    # tuples, integer-keyed dictionaries and enum-like values before saving).
    signature = json.loads(json.dumps(plain(signature)))
    write(folder/'run_config.json', signature)
    print('GPU_READY ' + json.dumps({k:v for k,v in signature.items() if k not in ['processor','model_files']}), flush=True)
    attempted = 0
    errors = []
    for page in manifest['pages']:
        path = folder / page['book'] / f"{page['scan']:05d}.json"
        if path.exists():
            assert read(path)['signature'] == signature, 'Saved output has different provenance'
            continue
        attempted += 1
        write(folder/'progress.json', dict(page=page['key'], stage='detecting', errors=errors))
        start = time.monotonic()
        try:
            image = Image.open(ROOT/page['image']).convert('RGB')
            raw, lines, regions = predict(image)
            torch.cuda.synchronize()
            write(folder/'raw'/page['book']/f"{page['scan']:05d}.json", raw)
            record = dict(book=page['book'], scan=page['scan'], partition='test',
                          training_forbidden=True, human_gold=False, semantic_labels_assigned=False,
                          signature=signature, image=dict(path=page['image'], width=image.width, height=image.height,
                                                         sha256=sha(ROOT/page['image'])),
                          lines=lines, regions=regions, warnings=[],
                          timing_seconds=round(time.monotonic()-start,3),
                          gpu_peak_allocated_mib=round(torch.cuda.max_memory_allocated()/2**20,1))
            write(path, record)
            print(f"DONE {page['index']}/100 {page['key']} lines={len(lines)} blocks={len(regions)} seconds={record['timing_seconds']}",flush=True)
        except Exception as error:
            errors.append(dict(key=page['key'], error=repr(error)))
            traceback.print_exc()
        if args.limit and attempted >= args.limit:
            break
    completed = list(folder.glob('bsb*/*.json'))
    write(folder/'progress.json', dict(stage='finished', completed=len(completed), expected=100, errors=errors))
    print(f'FINISHED {args.system} completed={len(completed)}/100 errors={len(errors)}',flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

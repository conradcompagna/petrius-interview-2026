"""D-FINE Large region-instance fine-tuning with a separate, inspected pilot."""
import argparse
import copy
import importlib.metadata
import json
import math
import os
if os.name == "nt":
    import msvcrt
else:
    import fcntl
import random
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault('NO_ALBUMENTATIONS_UPDATE', '1')
import numpy as np
import torch
from PIL import Image, ImageDraw
from scipy.optimize import linear_sum_assignment
from torchvision.ops import box_convert, box_iou
from torchvision.transforms import v2
from dfine.dfine import DFINEModel
from dfine.dataset import XMLDetectionDataset
from dfine.modules import build_criterion
from kraken.containers import Region, Segmentation
from kraken.models import load_safetensors, write_safetensors
from shared.io import ROOT, read, write, sha
from shared.records import unit

OUT = ROOT / 'outputs/training/dfine'
BASE = ROOT / 'models/dfine/ladas_l.safetensors'
SOURCE = ROOT / 'data/dfine/manifest.json'
PILOT = ['bsb00026118/00051', 'bsb00026118/00137', 'bsb10494707/01009']
MAPPING = {'lines': {}, 'regions': {'text': 0}}
SEED = 20261005


def cpu_tree(value):
    if isinstance(value, torch.Tensor): return value.detach().cpu().clone()
    if isinstance(value, dict): return {k: cpu_tree(v) for k, v in value.items()}
    if isinstance(value, list): return [cpu_tree(v) for v in value]
    if isinstance(value, tuple): return tuple(cpu_tree(v) for v in value)
    return value


def float_tree(value):
    if isinstance(value, torch.Tensor):
        if value.is_floating_point():
            assert torch.isfinite(value).all(), 'Non-finite detector output'
            return value.float()
        return value
    if isinstance(value, dict): return {k: float_tree(v) for k, v in value.items()}
    if isinstance(value, list): return [float_tree(v) for v in value]
    if isinstance(value, tuple): return tuple(float_tree(v) for v in value)
    return value


def verify_state(state):
    for name,value in state.items():
        if name=='decoder.anchors':
            # D-FINE deliberately uses +inf for invalid fixed anchors. These
            # are geometry buffers, not learned weights or failed gradients.
            valid=state['decoder.valid_mask'].expand_as(value)
            assert torch.isfinite(value[valid]).all()
            assert torch.isposinf(value[~valid]).all()
        else:assert torch.isfinite(value).all(),name


def verified_source_transition(previous, current):
    if previous == current:
        return True
    repairs = read(OUT/'verified_source_repairs.json') if (OUT/'verified_source_repairs.json').exists() else {'allowed_transitions': []}
    return [previous, current] in repairs['allowed_transitions']


def prepare():
    source = read(SOURCE); pages = []
    for item in source['pages']:
        assert sha(ROOT / item['annotation']) == item['annotation_sha256']
        assert sha(ROOT / item['image']) == item['image_sha256']
        data = read(ROOT / item['annotation'])
        width, height = Image.open(ROOT / item['image']).size
        assert (width, height) == (data['image']['width'], data['image']['height'])
        regions = data['regions']; ids = [r['id'] for r in regions]
        assert len(regions) == item['regions'] and len(set(ids)) == len(ids)
        boxes = []
        for r in regions:
            pts = np.asarray(r['polygon']); x1, y1 = pts.min(0); x2, y2 = pts.max(0)
            assert 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height
            boxes.append([float(x1), float(y1), float(x2), float(y2)])
        assert len(set(map(tuple, boxes))) == len(boxes), 'Identical boxes for different reference regions'
        assert len(boxes) < 300
        pages.append(dict(item, width=width, height=height, region_ids=ids, boxes=boxes))
    train = [p for p in pages if p['training_role'] == 'training']
    val = [p for p in pages if p['training_role'] == 'evaluation']
    assert len(train) == 100 and len(val) == 20
    assert not {p['key'] for p in train} & {p['key'] for p in val}
    assert set(PILOT) <= {p['key'] for p in train}
    manifest = dict(source=str(SOURCE.relative_to(ROOT)), source_sha256=sha(SOURCE), pages=pages,
                    target_policy='One independent axis-aligned box per accepted region ID; no rasterization, union, or line targets.',
                    class_mapping=MAPPING, training_pages=100, evaluation_pages=20,
                    training_regions=sum(p['regions'] for p in train), evaluation_regions=sum(p['regions'] for p in val))
    if (OUT / 'data_manifest.json').exists(): assert read(OUT / 'data_manifest.json') == manifest
    else: write(OUT / 'data_manifest.json', manifest)
    return manifest


def dataset(pages):
    ds = XMLDetectionDataset(class_mapping=copy.deepcopy(MAPPING), augmentation=False, image_size=(1280, 1280))
    for p in pages:
        data = read(ROOT / p['annotation'])
        regions = [Region(id=r['id'], boundary=r['polygon']) for r in data['regions']]
        ds.add(Segmentation(type='bbox', imagename=str(ROOT / p['image']), text_direction='horizontal-lr',
                            script_detection=False, lines=[], regions={'text': regions}))
    for i, p in enumerate(pages):
        item = ds[i]
        assert len(item['boxes']) == len(p['boxes']) == p['regions']
        restored = box_convert(item['boxes'], 'cxcywh', 'xyxy') * torch.tensor([p['width'], p['height']] * 2)
        assert torch.allclose(restored, torch.tensor(p['boxes']), atol=.002, rtol=0)
        assert item['labels'].eq(0).all()
    return ds


def metrics(pred, reference, threshold):
    iou = box_iou(torch.tensor(pred).reshape(-1, 4), torch.tensor(reference).reshape(-1, 4)).numpy()
    row, col = linear_sum_assignment(-((iou >= threshold) * 100 + iou))
    ok = iou[row, col] >= threshold
    matches = [(int(a), int(b), float(iou[a, b])) for a, b, good in zip(row, col, ok) if good]
    n, g, tp = len(pred), len(reference), int(ok.sum())
    return dict(tp=tp, fp=n-tp, fn=g-tp, precision=tp/max(1,n), recall=tp/max(1,g),
                f1=2*tp/max(1,n+g), predicted_regions=n, reference_regions=g,
                matched=matches, missed_reference_indices=[i for i in range(g) if i not in {b for a,b,v in matches}],
                unmatched_prediction_indices=[i for i in range(n) if i not in {a for a,b,v in matches}])


def comparison(image, boxes, refs, path):
    # Side-by-side views make overlaps and missed adjacent boxes visible.
    image = image.copy(); image.thumbnail((1100, 1500)); w, h = image.size
    canvas = Image.new('RGB', (w*2, h+35), 'white')
    colors = ['#e6194b','#3cb44b','#4363d8','#f58231','#911eb4','#00a6a6','#f032e6']
    for side, (items, title) in enumerate([(refs, 'REFERENCE: individual region boxes'), (boxes, 'PREDICTION: score >= 0.50')]):
        canvas.paste(image, (side*w,35)); draw=ImageDraw.Draw(canvas); draw.text((side*w+10,8),title,fill='black')
        for i, coords in enumerate(items):
            x1,y1,x2,y2=coords; color=colors[i%len(colors)]
            draw.rectangle((side*w+x1*w,35+y1*h,side*w+x2*w,35+y2*h),outline=color,width=3)
            draw.text((side*w+x1*w+2,35+y1*h+2),str(i+1),fill=color,stroke_width=1,stroke_fill='white')
    path.parent.mkdir(parents=True,exist_ok=True);canvas.save(path,quality=93)


TRANSFORM = v2.Compose([v2.Resize((1280,1280)),v2.RGB(),v2.ToImage(),v2.ToDtype(torch.float32,scale=True)])


@torch.inference_mode()
def evaluate(net, pages, run, step, epoch, status, compute_map=False):
    net.eval(); rows=[]; predictions=[]
    if compute_map:
        from torchmetrics.detection import MeanAveragePrecision
        ap = MeanAveragePrecision(box_format='xyxy',iou_type='bbox')
    for i,p in enumerate(pages):
        status('evaluation',batch=i+1,evaluation_pages=len(pages),page=p['key'])
        image=Image.open(ROOT/p['image']).convert('RGB')
        # Deployment transform and FP32, matching stock DFINEModel.predict.
        result=net(TRANSFORM(image).unsqueeze(0).cuda())
        scores,indices=torch.topk(result['pred_logits'].sigmoid().flatten(1),300,dim=-1)
        assert result['pred_logits'].shape[-1]==1
        boxes=box_convert(result['pred_boxes'],'cxcywh','xyxy').gather(1,indices.unsqueeze(-1).repeat(1,1,4))[0].cpu()
        scores=scores[0].cpu(); size=torch.tensor([p['width'],p['height']]*2)
        all_boxes=boxes*size; keep=scores>=.5
        assert torch.isfinite(all_boxes).all() and torch.isfinite(scores).all()
        kept=all_boxes[keep].round().int().tolist()
        assert all(b[2]>=b[0] and b[3]>=b[1] for b in kept)
        # Stock region inference rounds to pixels. A subpixel prediction can
        # become a zero-area box; retain it as an unmatched false positive.
        zero_area = [j for j,b in enumerate(kept) if b[2]==b[0] or b[3]==b[1]]
        m50=metrics(kept,p['boxes'],.5);m75=metrics(kept,p['boxes'],.75)
        regions=[]
        for j,(b,score) in enumerate(zip(kept,scores[keep].tolist())):
            x1,y1,x2,y2=b
            regions.append(unit(j,[[x1,y1],[x2,y1],[x2,y2],[x1,y2]],score,'text',None))
        record=dict(key=p['key'],book=p['book'],scan=int(p['key'].split('/')[1]),partition=p['training_role'],
            image=dict(path=p['image'],width=p['width'],height=p['height'],sha256=p['image_sha256']),
            regions=regions,lines=[],human_gold=False,semantic_labels_assigned=False,
            provenance=dict(model='D-FINE Large',step=step,epoch=epoch,region_instances=True,
                confidence_threshold=.5,ocr=False,line_detection=False,source='accepted region polygons converted individually to boxes'),
            metrics_at_50=m50,metrics_at_75=m75,
            zero_area_prediction_indices=zero_area,
            warnings=[f'{len(zero_area)} zero-area rounded predictions retained as false positives.'] if zero_area else [])
        write(run/'latest_predictions'/f'{p["key"]}.json',record)
        write(run/'previews'/f'step_{step:06d}'/f'{p["key"]}.json',record)
        factor=np.array([p['width'],p['height']]*2)
        comparison(image,np.asarray(kept).reshape(-1,4)/factor,np.asarray(p['boxes'])/factor,
            run/'previews'/f'step_{step:06d}'/f'{p["key"]}.jpg')
        rows.append(dict(key=p['key'],at_50=m50,at_75=m75));predictions.append((p,kept))
        if compute_map:
            ap.update([dict(boxes=all_boxes,scores=scores,labels=torch.zeros(len(scores),dtype=torch.int64))],
                [dict(boxes=torch.tensor(p['boxes']),labels=torch.zeros(len(p['boxes']),dtype=torch.int64))])
    summary=dict(step=step,epoch=epoch,pages=rows,
        macro_f1_50=float(np.mean([r['at_50']['f1'] for r in rows])),
        macro_f1_75=float(np.mean([r['at_75']['f1'] for r in rows])),
        exact_instances_at_75=all(r['at_75']['fp']==r['at_75']['fn']==0 for r in rows))
    if compute_map:
        values=ap.compute();summary.update(map_50=float(values['map_50']),map_50_95=float(values['map']))
    write(run/'latest_metrics.json',summary)
    with (run/'epoch_metrics.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(summary)+'\n')
    net.train();return summary


def export(net,path):
    metadata=copy.deepcopy(net.user_metadata)
    state=cpu_tree(net.state_dict())
    snapshot=DFINEModel(**metadata);snapshot.load_state_dict(state,strict=True);snapshot.eval()
    temp=path.with_suffix('.tmp.safetensors')
    assert Path(write_safetensors([snapshot],temp))==temp
    restored=load_safetensors(temp,tasks=['segmentation'])[0]
    assert restored.user_metadata['class_mapping']==MAPPING
    for name,value in state.items():
        assert torch.equal(value,restored.state_dict()[name]),name
    temp.replace(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['pilot','full'],required=True)
    parser.add_argument('--resume',type=Path)
    parser.add_argument('--max-steps',type=int,default=600)
    parser.add_argument('--epochs',type=int,default=100)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True);run=OUT/args.mode;run.mkdir(exist_ok=True)
    lock=(OUT/'training.lock').open('a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    if os.name == "nt": msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    else: fcntl.flock(lock.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
    log_file=(run/'training.log').open('a',encoding='utf-8',buffering=1)
    def log(msg):
        value=f'{time.strftime("%Y-%m-%d %H:%M:%S")} {msg}';print(value,flush=True);log_file.write(value+'\n')
    step=0;epoch=0;position=0;order=[];best=-1.;net=None;optimizer=None
    def status(phase,**kw):write(run/'status.json',dict(status=phase,pid=os.getpid(),time=time.time(),step=step,epoch=epoch,position=position,**kw))
    status('initializing')
    try:
        if not args.resume and (run/'last.ckpt').exists():raise RuntimeError('Existing run: use --resume explicitly')
        torch.set_num_threads(4);torch.set_float32_matmul_precision('high')
        assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
        random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED)
        manifest=prepare();pages=manifest['pages']
        train=[p for p in pages if p['training_role']=='training'];validation=[p for p in pages if p['training_role']=='evaluation']
        if args.mode=='pilot':train=[p for k in PILOT for p in train if p['key']==k];validation=train
        else:
            gate=read(OUT/'pilot/gate.json');visual=read(OUT/'pilot/visual_review.json')
            assert gate['passed'] and visual['passed'] and visual['checkpoint_sha256']==gate['checkpoint_sha256']
            assert gate['manifest_sha256']==sha(OUT/'data_manifest.json')
            assert verified_source_transition(gate['code_sha256'],sha(__file__))
        ds=dataset(train)
        # Audit all 120 independent-box targets before any optimization.
        if args.mode=='pilot':dataset([p for p in pages if p['key'] not in PILOT])
        write(OUT/'target_verification.json',dict(pages=120,regions=1428,all_region_ids_preserved=True,
            all_dataset_boxes_roundtrip=True,training_pages=100,evaluation_pages=20,manifest_sha256=sha(OUT/'data_manifest.json')))
        cfg=dict(mode=args.mode,model_variant='large',image_size=[1280,1280],batch_size=1,precision='bf16-mixed',
            optimizer='AdamW',learning_rate=.0001,backbone_learning_rate=.00001,weight_decay=.0001,
            augmentation='none for pilot; mild brightness/contrast only for full',confidence_threshold=.5,
            save_every_steps=25,seed=SEED,epochs=args.epochs,max_pilot_steps=args.max_steps,
            model_sha256=sha(BASE),manifest_sha256=sha(OUT/'data_manifest.json'),code_sha256=sha(__file__),
            dfine=importlib.metadata.version('dfine_kraken'),class_mapping=MAPPING,
            training_pages=len(train),evaluation_pages=len(validation),gpu=torch.cuda.get_device_name(0))
        if args.resume:
            checkpoint=torch.load(args.resume,map_location='cpu',weights_only=False)
            old_cfg=copy.deepcopy(checkpoint['config'])
            if old_cfg['code_sha256']!=cfg['code_sha256']:
                assert verified_source_transition(old_cfg['code_sha256'],cfg['code_sha256'])
                old_cfg['code_sha256']=cfg['code_sha256']
            assert old_cfg==cfg,'Resume configuration/source differs'
            verify_state(checkpoint['model'])
            net=DFINEModel(**checkpoint['metadata']);net.load_state_dict(checkpoint['model'],strict=True)
        else:
            net=load_safetensors(BASE,tasks=['segmentation'])[0]
            old_classes=net.num_classes
            # Official class-head resize: replace LADaS taxonomy with one generic
            # region class. Each box is still an independent Hungarian target.
            net.resize_output(1,del_indices=list(range(old_classes)))
            net.user_metadata.update(class_mapping=copy.deepcopy(MAPPING),_full_class_mapping=copy.deepcopy(MAPPING),accuracy=[],metrics=[])
        net.cuda();net.train()
        backbone=[p for n,p in net.named_parameters() if n.startswith('backbone.') and p.requires_grad]
        heads=[p for n,p in net.named_parameters() if not n.startswith('backbone.') and p.requires_grad]
        optimizer=torch.optim.AdamW([dict(params=backbone,lr=cfg['backbone_learning_rate']),dict(params=heads,lr=cfg['learning_rate'])],weight_decay=cfg['weight_decay'])
        scheduler=torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer,mode='max',factor=.5,patience=8,min_lr=1e-7)
        criterion=build_criterion(model_variant='large',class_mapping=MAPPING).cuda()
        if args.resume:
            optimizer.load_state_dict(checkpoint['optimizer']);scheduler.load_state_dict(checkpoint['scheduler'])
            step=checkpoint['step'];epoch=checkpoint['epoch'];position=checkpoint['position'];order=checkpoint['order'];best=checkpoint['best']
            random.setstate(checkpoint['rng_python']);np.random.set_state(checkpoint['rng_numpy']);torch.set_rng_state(checkpoint['rng_torch']);torch.cuda.set_rng_state_all(checkpoint['rng_cuda'])
            log(f'RESUMED full checkpoint {args.resume} step={step} epoch={epoch} position={position}')
        write(run/'config.json',cfg)
        def save(name,weights=False):
            status('saving',checkpoint=name)
            assert sha(__file__)==cfg['code_sha256'],'Training source changed during run'
            state=dict(config=cfg,metadata=copy.deepcopy(net.user_metadata),model=cpu_tree(net.state_dict()),
                optimizer=cpu_tree(optimizer.state_dict()),scheduler=scheduler.state_dict(),step=step,epoch=epoch,
                position=position,order=order,best=best,rng_python=random.getstate(),rng_numpy=np.random.get_state(),
                rng_torch=torch.get_rng_state(),rng_cuda=[s.cpu() for s in torch.cuda.get_rng_state_all()])
            path=run/f'{name}.ckpt';temp=path.with_suffix('.tmp.ckpt');torch.save(state,temp)
            checked=torch.load(temp,map_location='cpu',weights_only=False)
            assert checked['step']==step and checked['optimizer']['state']
            verify_state(checked['model'])
            for k,v in state['model'].items():assert torch.equal(v,checked['model'][k]),k
            temp.replace(path)
            if weights:export(net,run/f'{name}.safetensors')
            log(f'SAVED {name} step={step}'+(' and verified safetensors' if weights else ''))
        log(f'D-FINE LARGE | {len(train)} training pages | {len(validation)} evaluation pages | 1280 x 1280 | batch 1 | BF16')
        log('Every accepted region is an independent bounding-box target. No union, raster masks, NMS, or supplied inference regions.')
        log('Ctrl+C once saves interrupted.ckpt and interrupted.safetensors. Please allow saving to finish.')
        # Cache only the three pilot images, never the complete corpus.
        cache={i:ds[i] for i in range(len(ds))} if args.mode=='pilot' else {}
        while epoch<args.epochs and (args.mode=='full' or step<args.max_steps):
            if not order:order=list(range(len(ds)));random.shuffle(order);position=0
            while position<len(order):
                idx=order[position];sample=cache.get(idx) if cache else ds[idx]
                images=sample['image'].unsqueeze(0).cuda();target=[dict(boxes=sample['boxes'].cuda(),labels=sample['labels'].cuda())]
                if args.mode=='full':
                    images=(images*random.uniform(.9,1.1)+random.uniform(-.035,.035)).clamp(0,1)
                status('training',batch=position+1,training_pages=len(train),page=train[idx]['key'])
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast('cuda',dtype=torch.bfloat16):outputs=net(images,targets=target)
                # Keep the official box/Hungarian criterion in FP32.
                losses=criterion(float_tree(outputs),target);loss=sum(losses.values())
                assert torch.isfinite(loss) and loss>0,'Invalid loss'
                loss.backward();grad=torch.nn.utils.clip_grad_norm_(net.parameters(),.1,error_if_nonfinite=True)
                optimizer.step();step+=1;position+=1
                if step%5==0:log(f'TRAIN step={step} epoch={epoch+1} page={position}/{len(train)} loss={loss.item():.4f} grad={float(grad):.3f} peakVRAM={torch.cuda.max_memory_allocated()/2**20:.0f}MiB')
                del outputs,losses,loss,images,target
                if step%25==0:save('last')
            epoch+=1;order=[];position=0
            if args.mode=='full' or step%30==0:
                summary=evaluate(net,validation,run,step,epoch,status,compute_map=args.mode=='full')
                log(f'EVAL step={step} epoch={epoch} instanceF1@.50={summary["macro_f1_50"]:.4f} instanceF1@.75={summary["macro_f1_75"]:.4f} exact={summary["exact_instances_at_75"]}')
                if args.mode=='full':scheduler.step(summary['macro_f1_75'])
                score=summary['macro_f1_75']
                if score>best:best=score;save('best_instances',weights=True)
                save('last',weights=True)
                if args.mode=='pilot' and summary['exact_instances_at_75']:
                    write(run/'gate.json',dict(passed=True,step=step,epoch=epoch,metrics=summary,
                        code_sha256=cfg['code_sha256'],manifest_sha256=cfg['manifest_sha256'],
                        checkpoint_sha256=sha(run/'last.ckpt'),weights_sha256=sha(run/'last.safetensors'),
                        rule='All reference boxes on all three training pilot pages matched one-to-one at IoU >= 0.75, with no missing or extra detections at the stock 0.50 score cutoff. Visual inspection still required; not an unseen-data accuracy test.'))
                    status('awaiting_visual_review');log('PILOT PASSED numerical instance gate. Waiting for visual review before full training.');return
        save('last',weights=True)
        status('completed' if args.mode=='full' else 'pilot_gate_failed')
        log('Run finished.' if args.mode=='full' else 'Pilot budget ended without exact-instance gate. Full training remains blocked.')
    except KeyboardInterrupt:
        if net is not None and optimizer is not None and step:save('interrupted',weights=True)
        status('interrupted');log('Stopped intentionally; saved current state. No automatic restart.')
    except BaseException:
        error=traceback.format_exc();log(error);write(run/'startup_error.json',dict(time=time.time(),error=error,step=step))
        status('failed');raise
    finally:log_file.close();lock.close()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8');main()

"""D-FINE regions -> PERO lines/OCR -> neural v3 labels, using bundled weights."""
from pathlib import Path
import argparse, copy, hashlib, json, os, sys, time, urllib.request
from datetime import datetime

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
os.environ.setdefault('NO_ALBUMENTATIONS_UPDATE','1')
os.environ.setdefault('PYTHONUTF8','1')

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def box(poly):
    return [min(p[0] for p in poly),min(p[1] for p in poly),max(p[0] for p in poly),max(p[1] for p in poly)]

def regions(image_path,key,device):
    import torch, dfine.dfine
    from PIL import Image
    from kraken.tasks import SegmentationTaskModel
    from kraken.configs import SegmentationInferenceConfig
    task=SegmentationTaskModel.load_model(str(ROOT/'models/dfine/regions.safetensors'))
    config=SegmentationInferenceConfig(accelerator=device,device=[0] if device=='cuda' else 'auto',precision='32-true',num_threads=4)
    image=Image.open(image_path).convert('RGB')
    result=task.predict(image,config)
    rr=[]
    for kind,items in result.regions.items():
        for r in items:
            poly=r.boundary
            if box(poly)[0]>=box(poly)[2] or box(poly)[1]>=box(poly)[3]:
                continue
            rr.append(dict(id=f'detection_{len(rr):04d}',polygon=poly,bbox=box(poly),label='text_region',detector_label=kind))
    return dict(key=key,image=dict(path=str(image_path),width=image.width,height=image.height,sha256=sha(image_path)),regions=rr,lines=[])

def ocr(page,device,out):
    import configparser, cv2, numpy as np, torch
    from pero_ocr.document_ocr.page_parser import PageParser
    from pero_ocr.core.layout import PageLayout,RegionLayout
    folder=ROOT/'models/pero'
    config=configparser.ConfigParser();config.read(folder/'config.ini')
    config['LAYOUT_PARSER_1'].update(DETECT_REGIONS='no',DETECT_LINES='no',DETECT_STRAIGHT_LINES_IN_REGIONS='yes',
        MERGE_LINES='no',ADJUST_HEIGHTS='no',MULTI_ORIENTATION='no',ADJUST_BASELINES='no',USE_CPU='yes' if device=='cpu' else 'no')
    config['OCR']['USE_CPU']='yes' if device=='cpu' else 'no'
    parser=PageParser(config,device=torch.device(device),config_path=str(folder))
    image=cv2.imread(page['image']['path'])
    layout=PageLayout(id=page['key'].replace('/','_'),page_size=image.shape[:2])
    layout.regions=[RegionLayout(r['id'],np.asarray(r['polygon'],dtype=np.float64)) for r in page['regions']]
    try:
        for engine in parser.layout_parsers:
            if type(engine).__name__=='SmartRegionSorter':
                ordered=engine.process_page(image,copy.deepcopy(layout));by={r.id:r for r in layout.regions}
                layout.regions=[by[r.id] for r in ordered.regions]
            else:
                layout=engine.process_page(image,layout)
        for region in layout.regions:
            mask=np.zeros(image.shape[:2],np.uint8);cv2.fillPoly(mask,[region.polygon.astype(np.int32)],1)
            masked=np.full_like(image,255);masked[mask==1]=image[mask==1]
            for line in region.lines:
                line.crop=parser.line_cropper.crop_engine.crop(masked,line.baseline,line.heights)
                if line.crop is None or not line.crop.size:raise RuntimeError('Empty crop: '+line.id)
        layout=parser.ocr.process_page(image,layout)
        parser.update_confidences(layout)
        xml=out/'pagexml'/(page['key']+'.xml');xml.parent.mkdir(parents=True,exist_ok=True)
        layout.to_pagexml(str(xml),creator='D-FINE epoch14 + PERO + multimodal neural v3')
        # Match the integer PAGE coordinates consumed by the trained classifier.
        import xml.etree.ElementTree as ET
        parsed=ET.parse(xml); ns={'p':parsed.getroot().tag.split('}')[0].strip('{')}
        for n,r in enumerate(parsed.findall('.//p:TextRegion',ns)):
            rid=r.attrib['id']
            for el in r.findall('p:TextLine',ns):
                poly=[[int(v) for v in pair.split(',')] for pair in el.find('p:Coords',ns).attrib['points'].split()]
                base=[[int(v) for v in pair.split(',')] for pair in el.find('p:Baseline',ns).attrib['points'].split()]
                text=el.find('p:TextEquiv/p:Unicode',ns)
                page['lines'].append(dict(id=el.attrib['id'],region_id=rid,region_ids=[rid],bbox=box(poly),polygon=poly,baseline=base,
                    text=text.text or '' if text is not None else '',label='outside',reading_order=len(page['lines'])))
        by={r['id']:r for r in page['regions']}
        page['regions']=[by[r.id] for r in layout.regions]
        for r in page['regions']:r['line_ids']=[l['id'] for l in page['lines'] if l['region_id']==r['id']]
    finally:
        for engine in parser.layout_parsers:
            if hasattr(engine,'pool'):engine.pool.close();engine.pool.join()
    return page

def label(page,device,out):
    sys.path.insert(0,str(HERE/'neural'))
    from .neural import predict
    path=out/'ocr'/(page['key']+'.json');write(path,page)
    if page['lines']:
        predict.main(str(out/'raw_labels'),[str(path)],device=device)
        raw=json.loads((out/'raw_labels'/(page['key']+'.json')).read_text(encoding='utf-8'))
        ll={l['id']:l for l in raw['lines']};rr={r['id']:r for r in raw['regions']}
        for l in page['lines']:l.update(label=ll[l['id']]['label'],confidence=ll[l['id']]['confidence'])
        for r in page['regions']:r.update(central=rr[r['id']]['central'],central_probability=rr[r['id']]['central_probability'],label='main_text_block' if rr[r['id']]['central'] else 'outside')
        page['duplicate_regions_dropped']=raw['duplicate_regions_dropped']
    return page

def overlay(page,out):
    import cv2,numpy as np
    im=cv2.imread(page['image']['path']);colors={'text':(60,160,60),'summarium':(200,120,0),'inscriptio':(160,0,160),'other':(0,0,220)}
    for l in page['lines']:
        if l['label'] not in colors:continue
        a,b,c,d=[int(v) for v in l['bbox']];a=max(a,0);b=max(b,0);c=min(c,im.shape[1]);d=min(d,im.shape[0])
        im[b:d,a:c]=(im[b:d,a:c]*.65+np.array(colors[l['label']])*.35).astype(np.uint8)
    for r in page['regions']:
        if r.get('central'):
            a,b,c,d=map(int,r['bbox']);cv2.rectangle(im,(a,b),(c,d),(0,0,0),3)
    p=out/'overlays'/(page['key']+'.jpg');p.parent.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(p),im)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('images', nargs='+', help='Local page images.')
    ap.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto')
    ap.add_argument('--out', type=Path, default=ROOT/'outputs/inference')
    args = ap.parse_args()
    import torch,cv2
    torch.set_num_threads(4);cv2.setNumThreads(2)
    device='cuda' if args.device=='auto' and torch.cuda.is_available() else 'cpu' if args.device=='auto' else args.device
    if device=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA selected but no CUDA device is available.')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'models/manifest.json').read_text(encoding='utf-8'))
    for r in manifest['files']:
        if sha(ROOT/r['path'])!=r['sha256']:raise RuntimeError('Model file hash mismatch: '+r['path'])
    sources=[(Path(p).resolve(),'custom/'+Path(p).stem) for p in args.images]
    if len({k for _,k in sources})!=len(sources):raise ValueError('Use distinct image filenames.')
    report=[]
    for p,key in sources:
        start=time.perf_counter();print(f'{key}: D-FINE regions ({device})',flush=True)
        page=regions(p,key,device);write(out/'regions'/(key+'.json'),page)
        print(f'{key}: {len(page["regions"])} regions; PERO lines and OCR',flush=True)
        page=ocr(page,device,out);print(f'{key}: {len(page["lines"])} lines; neural classification',flush=True)
        page=label(page,device,out);page['provenance']=dict(pipeline='D-FINE epoch14 / PERO / neural v3',device=device,models=manifest)
        write(out/'predictions'/(key+'.json'),page);overlay(page,out)
        text='\n'.join(l['text'] for l in page['lines'] if l['label']!='outside')
        p=out/'text'/(key+'.txt');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
        report.append(dict(key=key,regions=len(page['regions']),lines=len(page['lines']),selected_lines=sum(l['label']!='outside' for l in page['lines']),seconds=round(time.perf_counter()-start,2)))
        write(out/'run_report.json',dict(device=device,pages=report));print('Completed '+key,flush=True)
    print('Outputs: '+str(out),flush=True)

if __name__=='__main__':
    main()

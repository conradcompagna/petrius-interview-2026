"""Verify a passed D-FINE pilot through Kraken's stock deployment entry point."""
import json
import os
from pathlib import Path
os.environ.setdefault('NO_ALBUMENTATIONS_UPDATE','1')
import torch
import numpy as np
from scipy.optimize import linear_sum_assignment
from PIL import Image
import xml.etree.ElementTree as ET
from kraken.tasks import SegmentationTaskModel
from kraken.configs import SegmentationInferenceConfig
from kraken.serialization import serialize
from shared.io import ROOT,read,write,sha
from .train import metrics


def main():
    run=ROOT/'outputs/training/dfine/pilot'
    gate=read(run/'gate.json');assert gate['passed']
    assert sha(run/'last.safetensors')==gate['weights_sha256']
    assert read(run/'status.json')['status']=='awaiting_visual_review'
    torch.set_num_threads(4);torch.set_float32_matmul_precision('high')
    model=SegmentationTaskModel.load_model(str(run/'last.safetensors'))
    references={p['key']:p for p in read(run.parent/'data_manifest.json')['pages']}
    cfg=SegmentationInferenceConfig(accelerator='cuda',device=[0],precision='32-true',num_threads=4)
    rows=[]
    for row in gate['metrics']['pages']:
        p=read(run/'latest_predictions'/f'{row["key"]}.json')
        image=Image.open(ROOT/p['image']['path']).convert('RGB');image.filename=p['image']['path']
        pred=model.predict(image,cfg);assert not pred.lines
        regions=[r for rr in pred.regions.values() for r in rr]
        def bbox(poly):
            x,y=zip(*poly);return (min(x),min(y),max(x),max(y))
        expected=sorted(bbox(r['polygon']) for r in p['regions'])
        actual=sorted(bbox(r.boundary) for r in regions)
        assert len(actual)==len(expected)
        distances=np.abs(np.asarray(actual)[:,None,:]-np.asarray(expected)[None,:,:]).max(2)
        ri,ci=linear_sum_assignment(distances)
        delta=float(distances[ri,ci].max(initial=0))
        # CPU/GPU scaling and rounding of nearly half-pixel coordinates can
        # differ by one original-image pixel. Never tolerate changed instances.
        assert delta<=1,(row['key'],delta)
        actual_metric=metrics(actual,references[row['key']]['boxes'],.75)
        assert actual_metric['fp']==actual_metric['fn']==0
        xml=serialize(pred,image_size=image.size,template='pagexml')
        xml_regions=ET.fromstring(xml).findall('.//{*}TextRegion')
        assert len(xml_regions)==len(regions)==len({r.attrib['id'] for r in xml_regions})
        output=run/'previews'/f'step_{gate["step"]:06d}'/f'{row["key"]}.xml'
        output.write_text(xml,encoding='utf-8')
        rows.append(dict(key=row['key'],regions=len(regions),same_individual_region_instances=True,
            maximum_coordinate_difference_pixels=delta,stock_inference_f1_at_75=actual_metric['f1'],unique_pagexml_ids=True))
    write(run/'deployment_verification.json',dict(passed=True,checkpoint_sha256=gate['checkpoint_sha256'],weights_sha256=gate['weights_sha256'],pages=rows))
    print(json.dumps(rows,indent=2))


if __name__=='__main__':main()

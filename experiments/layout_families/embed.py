"""Image embeddings for family assignment: whole-page thumbnail (layout) and native-resolution patch (typeface).
Frozen ImageNet MobileNetV3-small; channel mean and max pooled. CPU.

    python -m experiments.layout_families.embed [--work outputs/layout_families]
"""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image
from .common import PKG, WORK

W = PKG / 'work'


def main(work):
    W = work
    WORK.mkdir(parents=True, exist_ok=True)
    import torch, torchvision
    net = torchvision.models.mobilenet_v3_small(weights=torchvision.models.MobileNet_V3_Small_Weights.DEFAULT).features.eval()
    mean = torch.tensor([.485, .456, .406])[:, None, None]; std = torch.tensor([.229, .224, .225])[:, None, None]
    def emb(path, size, upto, gray=False):
        im = Image.open(path).convert('RGB').resize(size)
        if gray:   # paper tone and scan colour say nothing about the layout family: stretch a grey version to full range
            g = np.asarray(im.convert('L'), dtype=np.float32); lo, hi = np.percentile(g, [2, 98])
            g = np.clip((g - lo) / max(1., hi - lo), 0, 1) * 255; im = Image.fromarray(np.stack([g] * 3, -1).astype(np.uint8))
        t = ((torch.from_numpy(np.asarray(im, dtype=np.float32) / 255).permute(2, 0, 1) - mean) / std)[None]
        with torch.inference_mode(): f = net[:upto](t)[0]
        return torch.cat([f.mean((1, 2)), f.amax((1, 2))]).numpy()
    names = sorted(p.name for p in (W / 'thumbs').glob('*.jpg'))
    page = np.stack([emb(W / 'thumbs' / n, (352, 512), 13, gray=True) for n in names])      # deep features: page composition
    patch = np.stack([emb(W / 'patches' / n, (384, 384), 9, gray=True) for n in names])     # mid features: letter texture
    np.savez_compressed(WORK / 'embeddings.npz', names=np.array(names), page=page, patch=patch)
    print(page.shape, patch.shape)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, default=W)
    main(parser.parse_args().work)

"""Input batches and prediction for the two final trained taggers."""
import os
import numpy as np
import torch
import torch.nn.functional as F
from .model import ROLE, TMAX, RTMAX, LineTagger, RegionTagger
HERE = os.path.dirname(os.path.abspath(__file__))
LAB = ROLE + ['outside']
DEV = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def encode(texts, voc, n):
    T = np.zeros((len(texts), n), np.int64)
    for i, t in enumerate(texts):
        v = [voc.get(ch, 1) for ch in t[:n]]
        T[i, :len(v)] = v
    return T

def augment_img(x, rng, train):
    """x: uint8 B,H,W,3 -> float tensor B,3,H,W on DEV, ink = high. Training: small shifts, contrast and brightness changes."""
    x = torch.from_numpy(np.ascontiguousarray(x)).to(DEV).float().permute(0, 3, 1, 2)
    return 1 - x / 255.0

class Lines:
    """Line tagger. seqs: list of pages, each a list of line indices (any order)."""

    def __init__(self, d, voc, seed=0):
        self.d, self.voc = (d, voc)
        self.T = encode(d['text'], voc, TMAX)
        self.nchar = len(voc) + 2
        torch.manual_seed(seed)
        self.rng = np.random.default_rng(seed)
        self.model = LineTagger(self.nchar).to(DEV)

    def batch(self, seqs, train):
        d = self.d
        ii = np.array([i for s in seqs for i in s])
        lens = [len(s) for s in seqs]
        x = augment_img(d['X'][ii], self.rng, train)
        c = d['coords'][ii].copy()
        T = self.T[ii]
        return (x, torch.from_numpy(d['w'][ii].astype(np.int64)).to(DEV), torch.from_numpy(T).to(DEV), torch.from_numpy(c).to(DEV), lens, ii)

    @torch.no_grad()
    def predict(self, seqs):
        self.model.eval()
        out = {}
        for a in range(0, len(seqs), 8):
            x, w, t, c, lens, ii = self.batch(seqs[a:a + 8], False)
            p = F.softmax(self.model(x, w, t, c, lens), 1).cpu().numpy()
            out.update({int(i): q for i, q in zip(ii, p)})
        return out

class Regions:
    """Region tagger. pages: list of pages, each a list of region indices."""

    def __init__(self, d, voc, seed=0):
        self.d, self.voc = (d, voc)
        self.T = encode(d['R_text'], voc, RTMAX)
        self.nchar = len(voc) + 2
        torch.manual_seed(seed)
        self.rng = np.random.default_rng(seed)
        self.model = RegionTagger(self.nchar).to(DEV)

    def batch(self, pages, train):
        d = self.d
        ii = np.array([i for s in pages for i in s])
        lens = [len(s) for s in pages]
        oy, ox = (int(self.rng.integers(0, 33)), int(self.rng.integers(0, 33))) if train else (16, 16)
        x = augment_img(d['R_T'][ii][:, oy:oy + 96, ox:ox + 96], self.rng, train)
        c = d['R_coords'][ii].copy()
        T = self.T[ii]
        return (x, torch.from_numpy(T).to(DEV), torch.from_numpy(c).to(DEV), lens, ii)

    @torch.no_grad()
    def predict(self, pages):
        self.model.eval()
        out = {}
        for a in range(0, len(pages), 16):
            x, t, c, lens, ii = self.batch(pages[a:a + 16], False)
            out.update({int(i): float(q) for i, q in zip(ii, torch.sigmoid(self.model(x, t, c, lens)).cpu().numpy())})
        return out

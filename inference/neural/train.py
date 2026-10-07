"""Data, training and prediction for the two taggers."""
import os, glob, time, collections, numpy as np, torch, torch.nn.functional as F
from model import *

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = ROLE + ["outside"]
DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load(only=None):
    files = [f for f in sorted(glob.glob(os.path.join(HERE, "work", "bsb*.npz"))) if not only or os.path.basename(f)[:-4] in only]
    D = [np.load(f, allow_pickle=False) for f in files]
    d = {k: np.concatenate([x[k] for x in D]) for k in D[0].files}
    d["y"] = d["y"].astype(np.int64); d["R_y"] = d["R_y"].astype(np.int64)
    d["coords"] = np.concatenate([d["lbox"] / np.tile(d["page"], 2), d["rbox"] / np.tile(d["page"], 2)], 1).astype(np.float32)
    d["R_coords"] = (d["R_box"] / np.tile(d["R_page"], 2)).astype(np.float32)
    return d


def vocab(texts):
    c = collections.Counter(ch for t in texts for ch in t)
    return {ch: i + 2 for i, ch in enumerate(sorted(ch for ch, n in c.items() if n >= 3))}    # 0 = padding, 1 = unknown


def encode(texts, voc, n):
    T = np.zeros((len(texts), n), np.int64)
    for i, t in enumerate(texts):
        v = [voc.get(ch, 1) for ch in t[:n]]; T[i, :len(v)] = v
    return T


def augment_img(x, rng, train):
    """x: uint8 B,H,W,3 -> float tensor B,3,H,W on DEV, ink = high. Training: small shifts, contrast and brightness changes."""
    x = torch.from_numpy(np.ascontiguousarray(x)).to(DEV).float().permute(0, 3, 1, 2)
    if train:
        m = x.mean((1, 2, 3), keepdim=True)
        x = (x - m) * torch.empty(len(x), 1, 1, 1, device=DEV).uniform_(0.7, 1.3) + m + torch.empty(len(x), 1, 1, 1, device=DEV).uniform_(-25, 25)
        x = torch.roll(x, (int(rng.integers(-3, 4)), int(rng.integers(-4, 5))), (2, 3)).clamp(0, 255)
    return 1 - x / 255.0


def decolour(x, pages_len, rng, p=0.25):
    """training only: the colour of whole pages is removed at random, so that the network cannot depend on red ink alone"""
    s = 0
    for n in pages_len:
        if rng.random() < p:
            x[s:s + n] = x[s:s + n].mean(1, keepdim=True)
        s += n
    return x


def noisy_text(T, rng, nchar, drop=0.15, noise=0.05):
    T = T.copy(); T[rng.random(len(T)) < drop] = 0
    m = (rng.random(T.shape) < noise) & (T > 0); T[m] = rng.integers(1, nchar, int(m.sum()))
    return T


def sched(opt, lr, steps):
    return torch.optim.lr_scheduler.OneCycleLR(opt, lr, total_steps=steps, pct_start=0.15)


class Lines:
    """Line tagger. seqs: list of pages, each a list of line indices (any order)."""
    def __init__(self, d, voc, seed=0):
        self.d, self.voc = d, voc; self.T = encode(d["text"], voc, TMAX); self.nchar = len(voc) + 2
        torch.manual_seed(seed); self.rng = np.random.default_rng(seed); self.model = LineTagger(self.nchar).to(DEV)

    def batch(self, seqs, train):
        d = self.d; ii = np.array([i for s in seqs for i in s]); lens = [len(s) for s in seqs]
        x = augment_img(d["X"][ii], self.rng, train); c = d["coords"][ii].copy(); T = self.T[ii]
        if train:
            x = decolour(x, lens, self.rng); T = noisy_text(T, self.rng, self.nchar); c += self.rng.normal(0, 0.002, c.shape).astype(np.float32)
        return x, torch.from_numpy(d["w"][ii].astype(np.int64)).to(DEV), torch.from_numpy(T).to(DEV), torch.from_numpy(c).to(DEV), lens, ii

    def fit(self, seqs, y, epochs=24, lr=1e-3, bs=6, log=None, evalfn=None, every=2):
        """evalfn() -> score on the evaluation pages; called every `every` epochs, the best-scoring weights are kept"""
        best, keep = -1.0, None
        m = self.model; opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=1e-2)
        sc = sched(opt, lr, epochs * ((len(seqs) + bs - 1) // bs))
        yy = y[np.array([i for s in seqs for i in s])]; c = np.bincount(yy[yy >= 0], minlength=4).astype(float) + 1
        wts = torch.tensor((c.sum() / c) ** 0.5 / ((c.sum() / c) ** 0.5).mean(), dtype=torch.float32, device=DEV)
        for ep in range(epochs):
            m.train(); order = self.rng.permutation(len(seqs)); tot = n = 0; t0 = time.time()
            for a in range(0, len(order), bs):
                x, w, t, c_, lens, ii = self.batch([seqs[j] for j in order[a:a + bs]], True)
                lab = torch.from_numpy(y[ii]).to(DEV); ok = lab >= 0
                loss = F.cross_entropy(m(x, w, t, c_, lens)[ok], lab[ok], weight=wts)
                opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step(); sc.step()
                tot += loss.item() * int(ok.sum()); n += int(ok.sum())
            if evalfn and (ep % every == every - 1 or ep == epochs - 1):
                sc_ = evalfn(); star = sc_ > best
                if star: best, keep = sc_, {k: v.detach().cpu().clone() for k, v in m.state_dict().items()}
                if log: log("  lines   epoch %2d/%d  loss %.4f  evaluation macro-F1 %.4f%s  %.0fs" % (ep + 1, epochs, tot / max(1, n), sc_, "  <- best so far" if star else "", time.time() - t0))
            elif log and (ep % 6 == 5 or ep == epochs - 1):
                log("  lines   epoch %2d/%d  loss %.4f  %.0fs" % (ep + 1, epochs, tot / max(1, n), time.time() - t0))
        if keep is not None: m.load_state_dict(keep)
        return best

    def start(self, seqs, y, lr=1e-3, bs=6, patience=12):
        self.seqs, self.y, self.bs, self.lr, self.ep = seqs, y, bs, lr, 0
        self.opt = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-2)
        self.plateau = torch.optim.lr_scheduler.ReduceLROnPlateau(self.opt, mode="max", factor=0.5, patience=patience, min_lr=2e-5)
        yy = y[np.array([i for s in seqs for i in s])]; c = np.bincount(yy[yy >= 0], minlength=4).astype(float) + 1
        self.wts = torch.tensor((c.sum() / c) ** 0.5 / ((c.sum() / c) ** 0.5).mean(), dtype=torch.float32, device=DEV)

    def epoch(self):
        """one pass over the training pages; returns the mean loss"""
        m = self.model; m.train(); order = self.rng.permutation(len(self.seqs)); tot = n = 0; nb = (len(order) + self.bs - 1) // self.bs
        for b, a in enumerate(range(0, len(order), self.bs)):
            if self.ep < 4:                                                    # warm-up over the first four epochs
                for g in self.opt.param_groups: g["lr"] = self.lr * (self.ep * nb + b + 1) / (4 * nb)
            x, w, t, c_, lens, ii = self.batch([self.seqs[j] for j in order[a:a + self.bs]], True)
            lab = torch.from_numpy(self.y[ii]).to(DEV); ok = lab >= 0
            loss = F.cross_entropy(m(x, w, t, c_, lens)[ok], lab[ok], weight=self.wts)
            self.opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); self.opt.step()
            tot += loss.item() * int(ok.sum()); n += int(ok.sum())
        self.ep += 1
        return tot / max(1, n)

    def stalled(self, score):
        if self.ep > 4: self.plateau.step(score)
        return self.opt.param_groups[0]["lr"]

    @torch.no_grad()
    def predict(self, seqs):
        self.model.eval(); out = {}
        for a in range(0, len(seqs), 8):
            x, w, t, c, lens, ii = self.batch(seqs[a:a + 8], False)
            p = F.softmax(self.model(x, w, t, c, lens), 1).cpu().numpy()
            out.update({int(i): q for i, q in zip(ii, p)})
        return out


class Regions:
    """Region tagger. pages: list of pages, each a list of region indices."""
    def __init__(self, d, voc, seed=0):
        self.d, self.voc = d, voc; self.T = encode(d["R_text"], voc, RTMAX); self.nchar = len(voc) + 2
        torch.manual_seed(seed); self.rng = np.random.default_rng(seed); self.model = RegionTagger(self.nchar).to(DEV)

    def batch(self, pages, train):
        d = self.d; ii = np.array([i for s in pages for i in s]); lens = [len(s) for s in pages]
        oy, ox = (int(self.rng.integers(0, 33)), int(self.rng.integers(0, 33))) if train else (16, 16)   # 96 x 96 window of the 128 x 128 thumbnail
        x = augment_img(d["R_T"][ii][:, oy:oy + 96, ox:ox + 96], self.rng, train); c = d["R_coords"][ii].copy(); T = self.T[ii]
        if train:
            x = decolour(x, lens, self.rng); T = noisy_text(T, self.rng, self.nchar); c += self.rng.normal(0, 0.003, c.shape).astype(np.float32)
        return x, torch.from_numpy(T).to(DEV), torch.from_numpy(c).to(DEV), lens, ii

    def fit(self, pages, epochs=40, lr=1e-3, bs=8, log=None, evalfn=None, every=5):
        best, keep = -1.0, None
        m = self.model; opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=1e-2); y = self.d["R_y"]
        sc = sched(opt, lr, epochs * ((len(pages) + bs - 1) // bs))
        yy = y[np.array([i for s in pages for i in s])]; pw = torch.tensor(float(((yy == 0).sum() / max(1, (yy == 1).sum())) ** 0.5), device=DEV)
        for ep in range(epochs):
            m.train(); order = self.rng.permutation(len(pages)); tot = n = 0; t0 = time.time()
            for a in range(0, len(order), bs):
                x, t, c, lens, ii = self.batch([pages[j] for j in order[a:a + bs]], True)
                loss = F.binary_cross_entropy_with_logits(m(x, t, c, lens), torch.from_numpy(y[ii]).float().to(DEV), pos_weight=pw)
                opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step(); sc.step()
                tot += loss.item() * len(ii); n += len(ii)
            if evalfn and (ep % every == every - 1 or ep == epochs - 1):
                sc_ = evalfn(); star = sc_ > best
                if star: best, keep = sc_, {k: v.detach().cpu().clone() for k, v in m.state_dict().items()}
                if log: log("  regions epoch %2d/%d  loss %.4f  evaluation accuracy %.4f%s  %.0fs" % (ep + 1, epochs, tot / n, sc_, "  <- best so far" if star else "", time.time() - t0))
            elif log and (ep % 10 == 9 or ep == epochs - 1):
                log("  regions epoch %2d/%d  loss %.4f  %.0fs" % (ep + 1, epochs, tot / n, time.time() - t0))
        if keep is not None: m.load_state_dict(keep)
        return best

    def start(self, pages, lr=1e-3, bs=8, patience=12):
        self.pages, self.bs, self.lr, self.ep = pages, bs, lr, 0
        self.opt = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-2)
        self.plateau = torch.optim.lr_scheduler.ReduceLROnPlateau(self.opt, mode="max", factor=0.5, patience=patience, min_lr=2e-5)
        yy = self.d["R_y"][np.array([i for s in pages for i in s])]
        self.pw = torch.tensor(float(((yy == 0).sum() / max(1, (yy == 1).sum())) ** 0.5), device=DEV)

    def epoch(self):
        m = self.model; m.train(); order = self.rng.permutation(len(self.pages)); tot = n = 0; nb = (len(order) + self.bs - 1) // self.bs; y = self.d["R_y"]
        for b, a in enumerate(range(0, len(order), self.bs)):
            if self.ep < 4:
                for g in self.opt.param_groups: g["lr"] = self.lr * (self.ep * nb + b + 1) / (4 * nb)
            x, t, c, lens, ii = self.batch([self.pages[j] for j in order[a:a + self.bs]], True)
            loss = F.binary_cross_entropy_with_logits(m(x, t, c, lens), torch.from_numpy(y[ii]).float().to(DEV), pos_weight=self.pw)
            self.opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); self.opt.step()
            tot += loss.item() * len(ii); n += len(ii)
        self.ep += 1
        return tot / n

    def stalled(self, score):
        if self.ep > 4: self.plateau.step(score)
        return self.opt.param_groups[0]["lr"]

    @torch.no_grad()
    def predict(self, pages):
        self.model.eval(); out = {}
        for a in range(0, len(pages), 16):
            x, t, c, lens, ii = self.batch(pages[a:a + 16], False)
            out.update({int(i): float(q) for i, q in zip(ii, torch.sigmoid(self.model(x, t, c, lens)).cpu().numpy())})
        return out


def f1s(g, p, n=4):
    out = []
    for c in range(n):
        tp = ((g == c) & (p == c)).sum(); pr = tp / max(1, (p == c).sum()); rc = tp / max(1, (g == c).sum()); out.append(2 * pr * rc / max(1e-9, pr + rc))
    return out

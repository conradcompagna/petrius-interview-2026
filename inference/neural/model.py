"""line_nn_v3: two small transformers trained from scratch on raw inputs.
RegionTagger (step 6): every D-FINE box of a page -> central block or outside.
LineTagger (steps 8-9): every line of the central block -> text / summarium / inscriptio / other.
No reading-order rule, no layout formulas, no text clean-up: boxes go in as raw page-relative coordinates."""
import math, torch, torch.nn as nn, torch.nn.functional as F

ROLE = ["text", "summarium", "inscriptio", "other"]
TMAX, RTMAX = 48, 96


def fourier(c, k=8):
    """coordinates in [0,1], shape (..., n) -> (..., n*2k): sines and cosines at k octaves, so that small offsets are resolvable"""
    f = (2.0 ** torch.arange(k, device=c.device)) * math.pi
    a = c[..., None] * f
    return torch.cat([a.sin(), a.cos()], -1).flatten(-2)


def blk(i, o, s):
    return nn.Sequential(nn.Conv2d(i, o, 3, s, 1), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


class CharReader(nn.Module):
    def __init__(self, nchar):
        super().__init__()
        self.emb = nn.Embedding(nchar, 32, padding_idx=0)
        self.t3, self.t5 = nn.Conv1d(32, 64, 3, padding=1), nn.Conv1d(32, 64, 5, padding=2)

    def forward(self, t):
        e = self.emb(t).transpose(1, 2); m = (t > 0).float()[:, None]
        return (torch.cat([F.relu(self.t3(e)), F.relu(self.t5(e))], 1) * m).amax(2)          # B,128


class LineReader(nn.Module):
    """Step 8: one line's colour strip and raw characters -> one vector. Sees the line in isolation."""
    def __init__(self, nchar, d=256):
        super().__init__()
        self.cnn = nn.Sequential(blk(3, 24, 2), blk(24, 48, 2), blk(48, 96, 2), blk(96, 128, (1, 2)))
        self.txt = CharReader(nchar)
        self.fuse = nn.Sequential(nn.Linear(256 + 128, d), nn.ReLU(inplace=True), nn.Dropout(0.2))

    def forward(self, x, w, t):
        f = self.cnn(x).mean(2)                                                              # B,128,24
        m = (torch.arange(f.shape[2], device=x.device)[None] < torch.clamp((w.float() / 16).ceil(), min=1)[:, None]).float()[:, None]
        img = torch.cat([(f * m).sum(2) / m.sum(2), (f - 1e4 * (1 - m)).amax(2)], 1)
        return self.fuse(torch.cat([img, self.txt(t)], 1))


class LineTagger(nn.Module):
    """Step 9: all line vectors of a page's central block + their raw coordinates -> one role per line."""
    def __init__(self, nchar, d=256, layers=4, heads=4):
        super().__init__()
        self.reader = LineReader(nchar, d)
        self.pos = nn.Sequential(nn.Linear(8 * 16, d), nn.ReLU(inplace=True), nn.Linear(d, d))
        self.enc = nn.TransformerEncoder(nn.TransformerEncoderLayer(d, heads, 2 * d, 0.1, batch_first=True, norm_first=True), layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(d); self.out = nn.Linear(d, len(ROLE))

    def forward(self, x, w, t, coords, lens):
        """lines of several pages concatenated; coords B,8 (line box, region box; page fractions); lens = lines per page"""
        z = self.reader(x, w, t) + self.pos(fourier(coords))
        pad = nn.utils.rnn.pad_sequence(torch.split(z, lens), batch_first=True)
        mask = torch.arange(pad.shape[1], device=z.device)[None] < torch.tensor(lens, device=z.device)[:, None]
        h = self.norm(self.enc(pad, src_key_padding_mask=~mask))
        return self.out(h)[mask]                                                             # same order as the input lines


class RegionTagger(nn.Module):
    """Step 6: all boxes of a page (thumbnail, raw coordinates, text read inside) -> central block or outside."""
    def __init__(self, nchar, d=128, layers=2, heads=4):
        super().__init__()
        self.cnn = nn.Sequential(blk(3, 24, 2), blk(24, 48, 2), blk(48, 96, 2), blk(96, 128, 2))
        self.txt = CharReader(nchar)
        self.fuse = nn.Sequential(nn.Linear(256 + 128, d), nn.ReLU(inplace=True), nn.Dropout(0.2))
        self.pos = nn.Sequential(nn.Linear(4 * 16, d), nn.ReLU(inplace=True), nn.Linear(d, d))
        self.enc = nn.TransformerEncoder(nn.TransformerEncoderLayer(d, heads, 2 * d, 0.1, batch_first=True, norm_first=True), layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(d); self.out = nn.Linear(d, 1)

    def forward(self, thumb, t, coords, lens):
        f = self.cnn(thumb).flatten(2)
        z = self.fuse(torch.cat([f.mean(2), f.amax(2), self.txt(t)], 1)) + self.pos(fourier(coords))
        pad = nn.utils.rnn.pad_sequence(torch.split(z, lens), batch_first=True)
        mask = torch.arange(pad.shape[1], device=z.device)[None] < torch.tensor(lens, device=z.device)[:, None]
        return self.out(self.norm(self.enc(pad, src_key_padding_mask=~mask)))[mask][:, 0]

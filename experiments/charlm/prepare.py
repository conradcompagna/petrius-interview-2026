"""Fetch text columns and diplomatic ground truth; never download CATMuS images."""
from pathlib import Path
import concurrent.futures as cf
import hashlib
import io
import json
import tarfile
import time
import urllib.request

import pyarrow.parquet as pq
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "data/charlm"
DATA.mkdir(parents=True, exist_ok=True)
SOURCES = HERE.parents[1] / "outputs/charlm/sources"
SOURCES.mkdir(parents=True, exist_ok=True)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class HTTPRangeFile(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.pos = url, size, 0
        self.session = requests.Session()
        self.transferred = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def read(self, n=-1):
        if self.pos >= self.size:
            return b""
        n = self.size - self.pos if n < 0 else min(n, self.size - self.pos)
        if not n:
            return b""
        start, end = self.pos, self.pos + n - 1
        for attempt in range(4):
            try:
                r = self.session.get(self.url, headers={"Range": f"bytes={start}-{end}"}, timeout=45, stream=True)
                r.raise_for_status()
                if r.status_code != 206:
                    r.close()
                    raise RuntimeError(f"Server did not honor byte range: {r.status_code}")
                cr = r.headers.get("Content-Range", "")
                if not cr.startswith(f"bytes {start}-{end}/"):
                    raise RuntimeError(f"Unexpected byte range: {cr}")
                data = r.content
                self.url = r.url
                r.close()
                if len(data) != n:
                    raise RuntimeError(f"Expected {n} bytes, got {len(data)}")
                self.transferred += n
                self.pos += n
                return data
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(1 + attempt)

    def close(self):
        self.session.close()
        super().close()


def catmus_shard(item):
    cache = SOURCES / f"catmus_train_{item['filename'].replace('.parquet', '.json')}"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    f = HTTPRangeFile(item["url"], item["size"])
    try:
        p = pq.ParquetFile(f)
        names = p.schema_arrow.names
        idx = p.schema.names.index("language")
        can_have_latin = False
        for i in range(p.metadata.num_row_groups):
            stats = p.metadata.row_group(i).column(idx).statistics
            if not stats or not stats.has_min_max or stats.min <= "Latin" <= stats.max:
                can_have_latin = True
        rows = []
        if can_have_latin:
            cols = [c for c in ("text", "language", "century", "script_type", "shelfmark", "genre", "project") if c in names]
            for j, row in enumerate(p.read(columns=cols, use_threads=False).to_pylist()):
                if row["language"] == "Latin":
                    row.update(source="CATMuS", source_id=f"train/{item['filename']}/{j}")
                    rows.append(row)
        result = {"url": item["url"], "rows": rows, "transferred_bytes": f.transferred, "parquet_rows": p.metadata.num_rows}
        cache.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result
    finally:
        f.close()


def get_catmus():
    url = "https://datasets-server.huggingface.co/parquet?dataset=CATMuS/medieval"
    with urllib.request.urlopen(url, timeout=30) as r:
        index = json.load(r)
    (SOURCES / "catmus_parquet_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    items = [x for x in index["parquet_files"] if x["split"] == "train"]
    out, transfers = [], 0
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(catmus_shard, x): x for x in items}
        for n, future in enumerate(cf.as_completed(futures), 1):
            result = future.result()
            out.extend(result["rows"])
            transfers += result["transferred_bytes"]
            if n % 20 == 0 or n == len(items):
                print(f"CATMuS {n}/{len(items)} shards: {len(out)} Latin lines", flush=True)
    out.sort(key=lambda x: x["source_id"])
    return out, {"url": url, "shards": len(items), "text_and_metadata_bytes": transfers}


def get_gt4():
    # Locate the EarlyModernLatin member by scanning tar headers, skipping all other payloads.
    url = "https://zenodo.org/records/1344132/files/GT4HistOCR.tar?download=1"
    outer_size = 4025354240
    f = HTTPRangeFile(url, outer_size)
    pos = 0
    while True:
        f.seek(pos)
        header = f.read(512)
        name = header[:100].split(b"\0")[0].decode()
        size = int(header[124:136].rstrip(b"\0 ") or b"0", 8)
        if name == "corpus/EarlyModernLatin.tar.bz2":
            break
        if not name:
            raise RuntimeError("EarlyModernLatin tar member not found")
        pos += 512 + ((size + 511) // 512) * 512
    archive = SOURCES / "EarlyModernLatin.tar.bz2"
    if not archive.exists():
        f.seek(pos + 512)
        with archive.open("wb") as target:
            remaining = size
            while remaining:
                chunk = f.read(min(8 * 1024 * 1024, remaining))
                target.write(chunk)
                remaining -= len(chunk)
                print(f"GT4HistOCR Latin archive: {(size-remaining)/size:.0%}", flush=True)
    f.close()
    if archive.stat().st_size != size:
        raise RuntimeError("Incomplete GT4 archive")
    rows = []
    with tarfile.open(archive, "r:bz2") as tar:
        for member in tar:
            if member.isfile() and member.name.endswith(".gt.txt"):
                text = tar.extractfile(member).read().decode("utf-8-sig").strip()
                if text:
                    rows.append({"source": "GT4HistOCR", "source_id": member.name, "text": text,
                                 "shelfmark": str(Path(member.name).parent), "language": "Latin"})
    rows.sort(key=lambda x: x["source_id"])
    return rows, {"url": url, "outer_tar_member": name, "member_offset": pos+512, "size": size,
                  "sha256": sha(archive.read_bytes()), "lines": len(rows)}


def main():
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        cat = pool.submit(get_catmus)
        gt = pool.submit(get_gt4)
        cat_rows, cat_meta = cat.result()
        gt_rows, gt_meta = gt.result()
    # Match the late-medieval writing domain: Latin of centuries 12-16, excluding humanistic hands.
    cat_selected = [r for r in cat_rows if r.get("century") is not None and 12 <= r["century"] <= 16
                    and "humanistic" not in (r.get("script_type") or "").lower()]
    # This is the documented Gothic printing in the GT4 Latin collection.
    gt_selected = [r for r in gt_rows if "1476-SpeculumNaturale" in r["source_id"]]
    if not gt_selected:
        raise RuntimeError("Speculum naturale source selection matched no lines")
    selected = cat_selected + gt_selected
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in selected).encode("utf-8")
    (DATA / "training_source.jsonl").write_bytes(data)
    (SOURCES / "gt4_all_latin.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in gt_rows), encoding="utf-8")
    manifest = {"catmus": cat_meta, "gt4": gt_meta, "catmus_latin_total": len(cat_rows),
                "catmus_selected": len(cat_selected), "speculum_selected": len(gt_selected),
                "selection": "CATMuS train: Latin, centuries 12-16, non-humanistic scripts; GT4: 1476 Speculum naturale",
                "lines": len(selected), "characters": sum(len(r["text"]) for r in selected),
                "training_source_sha256": sha(data)}
    (DATA / "source_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()

"""Pack inference weights into verified GitHub release ZIP archives."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--max-bytes', type=int, default=750_000_000)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in (ROOT / 'models').rglob('*') if p.is_file())
    if not files:
        raise SystemExit('No files under models/')
    chunks, chunk, size = [], [], 0
    for path in files:
        n = path.stat().st_size
        if n > args.max_bytes:
            raise SystemExit('Single file exceeds archive budget: ' + str(path))
        if chunk and size + n > args.max_bytes:
            chunks.append(chunk)
            chunk, size = [], 0
        chunk.append(path)
        size += n
    if chunk:
        chunks.append(chunk)
    assets = []
    for index, chunk in enumerate(chunks, 1):
        dest = args.out / f'assets-models-{index:02d}.zip'
        if dest.exists():
            raise SystemExit('Refusing to overwrite ' + str(dest))
        records = []
        with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=4) as archive:
            for path in chunk:
                name = path.relative_to(ROOT).as_posix()
                records.append({'path': name, 'bytes': path.stat().st_size, 'sha256': digest(path)})
                archive.write(path, name)
        with zipfile.ZipFile(dest) as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError('CRC failure ' + bad)
            for record in records:
                if hashlib.sha256(archive.read(record['path'])).hexdigest() != record['sha256']:
                    raise RuntimeError('Member hash mismatch ' + record['path'])
        assets.append({'name': dest.name, 'bytes': dest.stat().st_size, 'sha256': digest(dest), 'files': records})
        print(f'{dest.name}: {dest.stat().st_size:,} bytes / {len(records)} files', flush=True)
    manifest = {'repository': 'conradcompagna/petrius-interview-2026',
                'release': 'interview-2026-10-07', 'distribution': 'github_release', 'assets': assets}
    (ROOT / 'docs/release_assets.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf8')
    sums = args.out / 'SHA256SUMS.txt'
    extra = []
    if sums.exists():
        extra = [row for row in sums.read_text(encoding='ascii').splitlines()
                 if row.endswith('  Task_I_written_submission.zip')]
    sums.write_text(''.join(f"{v['sha256']}  {v['name']}\n" for v in assets)
                    + ''.join(row + '\n' for row in extra), encoding='ascii')
    print('Every archive passed CRC and every member matched its source hash.', flush=True)


if __name__ == '__main__':
    main()

"""Download the selected models and source images with recorded checksums."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def installed(item):
    p = ROOT/item['path']
    return p.is_file() and p.stat().st_size == item['bytes'] and digest(p) == item['sha256']

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--group', choices=['core', 'training', 'experiments', 'bakeoff', 'all'], default='core')
    args = p.parse_args()
    manifest = json.loads((ROOT/'tools/assets.json').read_text(encoding='utf-8'))
    folder = ROOT/'downloads'; folder.mkdir(exist_ok=True)
    for asset in manifest['assets']:
        if args.group != 'all' and args.group not in asset['groups']: continue
        if all(installed(item) for item in asset['files']):
            print(asset['name']+': installed and verified'); continue
        archive = folder/asset['name']
        if not archive.exists():
            pending = archive.with_suffix('.part')
            url = f"https://github.com/{manifest['repository']}/releases/download/{manifest['release']}/{asset['name']}"
            try:
                with urlopen(Request(url, headers={'User-Agent': 'Historical-Latin-Document-Analysis'}), timeout=60) as response, pending.open('wb') as f:
                    shutil.copyfileobj(response, f)
                pending.replace(archive)
            except (OSError, TimeoutError):
                pending.unlink(missing_ok=True)
                if not shutil.which('gh'): raise
                subprocess.run(['gh', 'release', 'download', manifest['release'], '--repo', manifest['repository'], '--pattern', asset['name'], '--dir', str(folder)], check=True)
        if archive.stat().st_size != asset['bytes'] or digest(archive) != asset['sha256']:
            raise RuntimeError('Archive checksum differs: '+asset['name'])
        expected = {item['path']: item for item in asset['files']}
        with ZipFile(archive) as z:
            if set(z.namelist()) != set(expected) or len(z.namelist()) != len(expected): raise RuntimeError('Archive file list differs')
            for name, item in expected.items():
                target = (ROOT/name).resolve()
                if not target.is_relative_to(ROOT): raise RuntimeError('Archive path outside repository')
                target.parent.mkdir(parents=True, exist_ok=True)
                pending = target.with_suffix(target.suffix+'.part')
                with z.open(name) as source, pending.open('wb') as out: shutil.copyfileobj(source, out)
                if pending.stat().st_size != item['bytes'] or digest(pending) != item['sha256']:
                    pending.unlink(); raise RuntimeError('File checksum differs: '+name)
                pending.replace(target)
        print(asset['name']+': installed and verified')

if __name__ == '__main__': main()

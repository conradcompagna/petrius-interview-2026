"""Download and verify the private release assets for a source-only checkout."""
from pathlib import Path
import hashlib,json,shutil,subprocess,zipfile

ROOT=Path(__file__).resolve().parents[1]
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(4*1024*1024),b''):h.update(data)
    return h.hexdigest()

def main():
    manifest=json.loads((ROOT/'docs/release_assets.json').read_text(encoding='utf-8'))
    downloads=ROOT/'downloads';downloads.mkdir(exist_ok=True)
    for asset in manifest['assets']:
        if all((ROOT/r['path']).is_file() and (ROOT/r['path']).stat().st_size==r['bytes'] and digest(ROOT/r['path'])==r['sha256'] for r in asset['files']):
            print(asset['name']+': already installed');continue
        archive=downloads/asset['name']
        if not archive.exists():
            if not shutil.which('gh'):raise SystemExit('Install GitHub CLI and run gh auth login, then rerun GET_ASSETS.bat.')
            subprocess.run(['gh','release','download',manifest['release'],'--repo',manifest['repository'],'--pattern',asset['name'],'--dir',str(downloads)],check=True)
        if digest(archive)!=asset['sha256']:raise SystemExit('Download checksum does not match: '+str(archive))
        with zipfile.ZipFile(archive) as z:
            expected={r['path']:r for r in asset['files']}
            if set(z.namelist())!=set(expected):raise SystemExit('Archive member list does not match manifest')
            for name in z.namelist():
                target=(ROOT/name).resolve()
                if not target.is_relative_to(ROOT.resolve()):raise SystemExit('Invalid archive path')
                data=z.read(name)
                if hashlib.sha256(data).hexdigest()!=expected[name]['sha256']:raise SystemExit('Member checksum does not match '+name)
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        archive.unlink()
        print(asset['name']+': installed and verified')
    print('Ready. Run RUN_VIEWER.bat or task1_min/run.bat.')

if __name__=='__main__':main()

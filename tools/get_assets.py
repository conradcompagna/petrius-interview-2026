"""Download and verify the selected model weights for a source-only checkout."""
from pathlib import Path
import hashlib,json,shutil,subprocess,zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(4*1024*1024),b''):h.update(data)
    return h.hexdigest()

def download(manifest, asset, archive):
    url='https://github.com/{}/releases/download/{}/{}'.format(
        manifest['repository'], quote(manifest['release'],safe=''), quote(asset['name'],safe=''))
    pending=archive.with_suffix(archive.suffix+'.part')
    try:
        print('Downloading '+asset['name']+' over HTTPS...',flush=True)
        request=Request(url,headers={'User-Agent':'PetrIUS-model-downloader'})
        with urlopen(request,timeout=60) as response, pending.open('wb') as stream:
            shutil.copyfileobj(response,stream,4*1024*1024)
        pending.replace(archive)
    except (HTTPError,URLError,TimeoutError,OSError) as exc:
        pending.unlink(missing_ok=True)
        if not shutil.which('gh'):
            raise SystemExit('Direct download unavailable. For private repository access, install GitHub CLI, run gh auth login, and rerun GET_ASSETS.bat. You can also extract assets-models-01.zip beside README.md.') from exc
        print('Using authenticated GitHub CLI access...',flush=True)
        subprocess.run(['gh','release','download',manifest['release'],'--repo',manifest['repository'],
                        '--pattern',asset['name'],'--dir',str(archive.parent)],check=True)

def main():
    manifest=json.loads((ROOT/'docs/release_assets.json').read_text(encoding='utf-8'))
    downloads=ROOT/'downloads';downloads.mkdir(exist_ok=True)
    for asset in manifest['assets']:
        if all((ROOT/r['path']).is_file() and (ROOT/r['path']).stat().st_size==r['bytes'] and digest(ROOT/r['path'])==r['sha256'] for r in asset['files']):
            print(asset['name']+': already installed');continue
        archive=downloads/asset['name']
        if not archive.exists():
            download(manifest,asset,archive)
        if archive.stat().st_size!=asset['bytes'] or digest(archive)!=asset['sha256']:
            archive.unlink()
            raise SystemExit('Download checksum does not match. Rerun GET_ASSETS.bat to download again.')
        with zipfile.ZipFile(archive) as z:
            expected={r['path']:r for r in asset['files']}
            if set(z.namelist())!=set(expected):raise SystemExit('Archive member list does not match manifest')
            for name in z.namelist():
                target=(ROOT/name).resolve()
                if not target.is_relative_to(ROOT.resolve()):raise SystemExit('Invalid archive path')
                data=z.read(name)
                if len(data)!=expected[name]['bytes'] or hashlib.sha256(data).hexdigest()!=expected[name]['sha256']:
                    raise SystemExit('Member checksum does not match '+name)
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        archive.unlink()
        print(asset['name']+': installed and verified')
    print('Model weights are ready. Run inference/run.bat.')

if __name__=='__main__':main()

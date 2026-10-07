"""Pack release models and optional local offline data into separate ZIP manifests."""
from pathlib import Path
import argparse, hashlib, json, zipfile

ROOT = Path(__file__).resolve().parents[1]
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''):h.update(block)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--max-bytes',type=int,default=750_000_000)
    ap.add_argument('--directories',nargs='+',choices=['models','viewer_data'],default=['models','viewer_data'])
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    for directory in a.directories:
        is_offline=directory=='viewer_data'
        manifest_path=ROOT/('docs/offline_assets.json' if is_offline else 'docs/release_assets.json')
        assets=[]
        files=sorted(p for p in (ROOT/directory).rglob('*') if p.is_file())
        if not files:raise SystemExit('No files under '+directory)
        chunks=[];chunk=[];size=0
        for p in files:
            n=p.stat().st_size
            if n>a.max_bytes:raise SystemExit('Single file exceeds archive budget: '+str(p))
            if chunk and size+n>a.max_bytes:chunks.append(chunk);chunk=[];size=0
            chunk.append(p);size+=n
        if chunk:chunks.append(chunk)
        for index,chunk in enumerate(chunks,1):
            dest=a.out/f'assets-{directory}-{index:02d}.zip'
            if dest.exists():raise SystemExit('Refusing to overwrite '+str(dest))
            records=[]
            with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
                for p in chunk:
                    name=p.relative_to(ROOT).as_posix()
                    records.append({'path':name,'bytes':p.stat().st_size,'sha256':digest(p)})
                    z.write(p,name)
            with zipfile.ZipFile(dest) as z:
                bad=z.testzip()
                if bad:raise RuntimeError('CRC failure '+bad)
                for record in records:
                    if hashlib.sha256(z.read(record['path'])).hexdigest()!=record['sha256']:
                        raise RuntimeError('Member hash mismatch '+record['path'])
            assets.append({'name':dest.name,'bytes':dest.stat().st_size,'sha256':digest(dest),'files':records})
            print(f'{dest.name}: {dest.stat().st_size:,} bytes / {len(records)} files',flush=True)
        manifest={'repository':'conradcompagna/petrius-interview-2026','release':'interview-2026-10-07',
                  'distribution':'local_optional_offline' if is_offline else 'github_release','assets':assets}
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        sums=a.out/('OFFLINE_SHA256SUMS.txt' if is_offline else 'SHA256SUMS.txt')
        extra=[]
        if not is_offline and sums.exists():
            extra=[row for row in sums.read_text(encoding='ascii').splitlines()
                   if row.endswith('  Task_I_written_submission.zip')]
        sums.write_text(''.join(f"{v['sha256']}  {v['name']}\n" for v in assets)
                        +''.join(row+'\n' for row in extra),encoding='ascii')
    print('Every archive passed CRC and every extracted member matched its source hash.',flush=True)

if __name__=='__main__':main()

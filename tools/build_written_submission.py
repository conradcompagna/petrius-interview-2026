"""Create the compact advance written Task I handoff."""
from pathlib import Path
import argparse,csv,hashlib,io,json,zipfile

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT.parent/'Task_I_written_submission.zip'
FILES=[
 'task1_min/task1.py','task1_min/task1_baseline.py',
 'task1_min/requirements.txt','task1_min/run.bat','task1_min/README.md',
 'task1_min/reference.csv','task1_min/evaluation.json','task1_min/lines.csv',
 'task1_min/labels_00040.jpg','task1_min/labels_00041.jpg',
 'task1_min/page_00040.json','task1_min/page_00041.json',
 'docs/task1_note.pdf','docs/SOURCES.md','docs/library_rights_inventory.json',
]
README='''# Historical Latin Document Analysis Task I written submission

Conrad Compagna · 7 October 2026

Start with **docs/task1_note.pdf**, the two-page method, errors, scaling and tools note.

To run the program, install Python 3.12 and double-click **task1_min/run.bat**. It installs NumPy and OpenCV, downloads both page images and their hOCR from MDZ, then produces the labels and evaluation. First-run internet access is required for the downloads.

- **task1_min/task1.py** is the completed submission runner.
- **task1_min/task1_baseline.py** preserves the original 162-line solution.
- **task1_min/labels_00040.jpg** and **labels_00041.jpg** are the coloured page images.
- **task1_min/confusion_matrix.csv** and **evaluation.json** give the 131 of 131 result and the separately recorded gutter numbers and woodcut initial.
- **task1_min/lines.csv** and **page_00040.json / page_00041.json** contain the detailed labels.
- **docs/SOURCES.md** lists the exact MDZ image, OCR and manifest interfaces.

I checked both original page overlays personally. The note discloses Claude, Codex and ChatGPT use directly. The full viewer, trained models and presentation are supplied separately as supporting material. Task II is a separate document.
'''

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--replace',action='store_true');args=ap.parse_args()
 if DEST.exists() and not args.replace:raise SystemExit('Refusing to overwrite '+str(DEST)+'; use --replace to rebuild')
 data={name:(ROOT/name).read_bytes() for name in FILES}
 data['README.md']=README.encode('utf-8')
 evaluation=json.loads(data['task1_min/evaluation.json'])
 csvout=io.StringIO(newline='');writer=csv.writer(csvout)
 writer.writerow(['Reference / program',*evaluation['labels']])
 for label,row in zip(evaluation['labels'],evaluation['confusion_matrix']):writer.writerow([label,*row])
 data['task1_min/confusion_matrix.csv']=csvout.getvalue().encode('utf-8')
 pending=DEST.with_suffix('.zip.pending')
 with zipfile.ZipFile(pending,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,content in data.items():z.writestr(name,content)
 with zipfile.ZipFile(pending) as z:
  assert z.testzip() is None
  assert set(z.namelist())==set(data)
  for name,content in data.items():assert z.read(name)==content,name
 pending.replace(DEST)
 sha=hashlib.sha256(DEST.read_bytes()).hexdigest()
 verification=ROOT/'docs/package_verification.json'
 report=json.loads(verification.read_text(encoding='utf-8'))
 report['written_task1']={'file':DEST.name,'bytes':DEST.stat().st_size,'sha256':sha,'members':len(data),'crc_and_member_bytes_verified':True}
 verification.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 sums=ROOT.parent/'release_assets_20261007/SHA256SUMS.txt'
 existing=[row for row in sums.read_text(encoding='ascii').splitlines() if not row.endswith('  '+DEST.name)]
 sums.write_text('\n'.join(existing+[f'{sha}  {DEST.name}'])+'\n',encoding='ascii')
 print(json.dumps(report['written_task1']))

if __name__=='__main__':main()

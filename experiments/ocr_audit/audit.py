"""Corpus OCR diagnostics; writes new evidence under outputs/ocr_audit.

No training, annotation, or existing OCR outputs are changed. Run from repo root:
  python tools/findings_ocr_audit.py fetch
  python tools/findings_ocr_audit.py analyze
"""
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse, csv, hashlib, json, re, time, urllib.request
from lxml import etree
from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/ocr_audit'
def read(p): return json.loads((ROOT / p).read_text(encoding='utf-8'))
def write(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def bbox(e):
    m = re.search(r'\bbbox\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)', e.get('title',''))
    return [float(x) for x in m.groups()] if m else None
def cls(e, c): return c in e.get('class','').split()
def parse(p):
    root = etree.fromstring(p.read_bytes(), etree.XMLParser(recover=True))
    pg = next(e for e in root.iter() if cls(e, 'ocr_page'))
    blocks = [e for e in pg.iter() if cls(e,'ocrx_block') or cls(e,'ocr_carea')]
    bid = {e:i+1 for i,e in enumerate(blocks)}
    lines=[]
    for i,e in enumerate(e for e in pg.iter() if cls(e,'ocr_line')):
        words=[{'bbox':bbox(w),'text':''.join(w.itertext()).strip()} for w in e.iter() if cls(w,'ocrx_word')]
        words=[w for w in words if w['bbox'] and w['text']]
        parent=next((a for a in e.iterancestors() if a in bid),None)
        lines.append({'id':i+1,'bbox':bbox(e),'block':bid.get(parent,0),'words':words,'text':' '.join(w['text'] for w in words)})
    return {'bbox':bbox(pg),'blocks_total':len(blocks),'blocks_nonempty':len({l['block'] for l in lines if l['words']}),'lines':lines}
def rows():
    m=read('data/ocr_audit/census.json')
    return [dict(book=b['id'],provider=b['provider'],**p) for b in m['books'] for p in b['sample']]
def fetch():
    OUT.mkdir(exist_ok=True,parents=True)
    cached={}
    for base in [ROOT/'data', ROOT/'data/ocr_audit/hocr', ROOT/'outputs/ocr_audit/hocr']:
        for p in base.rglob('*.hocr'):
            book=next((x for x in p.parts if re.fullmatch(r'bsb\d+',x)),None)
            if book and p.stem.isdigit(): cached.setdefault((book,int(p.stem)),p)
    tasks=rows()
    def one(r):
        ans={k:r.get(k) for k in ['book','scan','provider','hocr_url','image_path','source_width','source_height']}
        if r['provider']!='mdz': return dict(ans,status='not_mdz')
        dest=OUT/'hocr'/r['book']/f"{r['scan']:05d}.hocr"
        p=cached.get((r['book'],r['scan']),dest)
        try:
            if not p.exists():
                req=urllib.request.Request(r['hocr_url'],headers={'User-Agent':'Historical-Latin-OCR-audit/1.0'})
                for attempt in range(3):
                    try:
                        with urllib.request.urlopen(req,timeout=30) as resp: data=resp.read()
                        break
                    except Exception:
                        if attempt==2: raise
                        time.sleep(attempt+1)
                dest.parent.mkdir(exist_ok=True,parents=True); dest.write_bytes(data)
            h=parse(p)
            return dict(ans,status='ok',path=str(p.relative_to(ROOT)).replace('\\','/'),sha256=sha(p),line_count=len(h['lines']))
        except Exception as e: return dict(ans,status='error',error=str(e))
    result=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures=[ex.submit(one,r) for r in tasks]
        for f in as_completed(futures):
            result.append(f.result())
            if len(result)%100==0: print(len(result),dict(Counter(r['status'] for r in result)),flush=True)
    result.sort(key=lambda x:(x['book'],x['scan']))
    write(ROOT/'data/ocr_audit/acquisition.json',{'sampling_manifest':'data/ocr_audit/census.json','sampling_manifest_sha256':sha(ROOT/'data/ocr_audit/census.json'),'records':result})
    print(dict(Counter(r['status'] for r in result)),flush=True)
def analyze():
    fam=read('data/corpus/families.json'); inv=read('data/corpus/books.json')
    refs={(r['book'],r['scan']):r for r in read('data/ocr_audit/reference_index.json')['pages']}
    acq=read('data/ocr_audit/acquisition.json')['records']
    OUT.mkdir(parents=True, exist_ok=True)
    stats=[]; details=[]
    for r in acq:
        if r['status']!='ok': continue
        h=parse(ROOT/r['path']); text='\n'.join(l['text'] for l in h['lines']); letters=[c for c in text if c.isalpha()]
        s={'book':r['book'],'scan':r['scan'],'family':fam[r['book']],'lines':len(h['lines']),'words':sum(len(l['words']) for l in h['lines']),'chars':len(text),'blocks':h['blocks_nonempty'],'empty_blocks':h['blocks_total']-h['blocks_nonempty'],'long_s':text.count('ſ'),'f':text.count('f'),'cyrillic_chars':sum('\u0400'<=c<='\u052f' for c in text),'greek_chars':sum('\u0370'<=c<='\u03ff' or '\u1f00'<=c<='\u1fff' for c in text),'medieval_abbreviation_chars':sum(c in 'ꝑꝓꝯꝰꝝꝗꝙ⁊' for c in text),'wide_lines_70pct':sum(l['bbox'][2]-l['bbox'][0]>.7*h['bbox'][2] for l in h['lines'] if l['bbox'])}
        stats.append(s)
        ref=refs.get((r['book'],r['scan']))
        if not ref: continue
        a=read(ref['annotation']); sx=a['image']['width']/h['bbox'][2]; sy=a['image']['height']/h['bbox'][3]
        regions=[]
        for z in a['regions']:
            if z['role']=='initial': continue
            poly=Polygon(z['polygon'],z.get('holes',[])).buffer(0).buffer(-2)
            regions.append((z['id'],z['role'],poly))
        line_flags=[]; block_words=defaultdict(Counter); reg_blocks=defaultdict(Counter); assigned=0; allwords=0; role_words=Counter()
        for l in h['lines']:
            counts=Counter(); chars=Counter(); rolecounts=Counter()
            for w in l['words']:
                if sum(c.isalpha() for c in w['text'])<2: continue
                allwords+=1; x0,y0,x1,y1=w['bbox']; pt=Point((x0+x1)*sx/2,(y0+y1)*sy/2)
                hits=[z for z in regions if z[2].contains(pt)]
                if len(hits)!=1: continue
                rid,role,_=hits[0]; assigned+=1; counts[rid]+=1; chars[rid]+=sum(c.isalpha() for c in w['text']); rolecounts[role]+=1
                block_words[l['block']][rid]+=1; reg_blocks[rid][l['block']]+=1; role_words[role]+=1
            significant=[rid for rid,n in counts.items() if n>=2 and chars[rid]>=6]
            if len(significant)>=2:
                significant_roles=sorted({role for rid,role,_ in regions if rid in significant})
                line_flags.append({'line':l['id'],'bbox':l['bbox'],'regions':significant,'significant_roles':significant_roles,'roles':dict(rolecounts),'text':l['text']})
        mixed_blocks={str(b):dict(c) for b,c in block_words.items() if sum(n>=3 for n in c.values())>=2}
        fragments={rid:dict(c) for rid,c in reg_blocks.items() if sum(n>=3 for n in c.values())>=2}
        details.append(dict(s,reference=ref['annotation'],page_type=ref['page_type'],image=ref['image'],hocr=r['path'],assigned_words=assigned,eligible_words=allwords,cross_region_lines=len(line_flags),cross_role_lines=sum(len(x['significant_roles'])>1 for x in line_flags),mixed_blocks=len(mixed_blocks),fragmented_regions=len(fragments),reference_regions=len(regions),role_words=dict(role_words),line_flags=line_flags,mixed_block_details=mixed_blocks,fragment_details=fragments))
    write(OUT/'page_diagnostics.json',stats); write(OUT/'region_diagnostics.json',details)
    with (OUT/'page_diagnostics.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(stats[0])); w.writeheader(); w.writerows(stats)
    summary={'scope':'Frozen 10 pages per 100 volumes; all pages retained. MDZ diagnostics only for 97 MDZ volumes. Region comparisons use approximate independent AI-silver polygons, not human gold. Counts are diagnostic flags, not error rates.','inventory':inv['summary'],'families':dict(Counter(fam.values())),'acquisition':dict(Counter(r['status'] for r in acq)),'pages':len(stats),'books':len({x['book'] for x in stats}),'totals':{k:sum(x[k] for x in stats) for k in ['lines','words','chars','blocks','empty_blocks','long_s','f','cyrillic_chars','greek_chars','medieval_abbreviation_chars']},'region_sample':{'pages':len(details),'lines':sum(x['lines'] for x in details),'cross_region_lines':sum(x['cross_region_lines'] for x in details),'pages_with_cross_region_lines':sum(x['cross_region_lines']>0 for x in details),'cross_role_lines':sum(x['cross_role_lines'] for x in details),'mixed_blocks':sum(x['mixed_blocks'] for x in details),'pages_with_mixed_blocks':sum(x['mixed_blocks']>0 for x in details),'fragmented_regions':sum(x['fragmented_regions'] for x in details),'reference_regions':sum(x['reference_regions'] for x in details)},'by_family':{}}
    for f in sorted(set(fam.values())):
        a=[x for x in stats if x['family']==f]; d=[x for x in details if x['family']==f]
        summary['by_family'][f]={'pages':len(a),'books':len({x['book'] for x in a}),'lines':sum(x['lines'] for x in a),'words':sum(x['words'] for x in a),'pages_with_cyrillic':sum(x['cyrillic_chars']>0 for x in a),'books_with_long_s':len({x['book'] for x in a if x['long_s']>0}),'reference_pages':len(d),'reference_lines':sum(x['lines'] for x in d),'cross_region_lines':sum(x['cross_region_lines'] for x in d),'pages_with_cross_region_lines':sum(x['cross_region_lines']>0 for x in d),'mixed_blocks':sum(x['mixed_blocks'] for x in d),'fragmented_regions':sum(x['fragmented_regions'] for x in d),'reference_regions':sum(x['reference_regions'] for x in d)}
    books=[]
    for b in inv['books']:
        a=[s for s in stats if s['book']==b['id']]; d=next((d for d in details if d['book']==b['id']),None)
        z={'book':b['id'],'family':fam[b['id']],'provider':b['provider'],'date':b.get('date_sort'),'work':b['work'],'law':b['law'],'sampled_pages':10,'mdz_pages_acquired':len(a) if b['provider']=='mdz' else None,'ocr_rows':sum(s['lines'] for s in a) if a else None,'ocr_words':sum(s['words'] for s in a) if a else None,'pages_with_cyrillic':sum(s['cyrillic_chars']>0 for s in a) if a else None,'reference_scan':d['scan'] if d else None,'reference_ocr_rows':d['lines'] if d else None,'cross_region_row_flags':d['cross_region_lines'] if d else None,'mixed_block_flags':d['mixed_blocks'] if d else None,'scope':'MDZ OCR diagnostic; no CER' if a else 'Other provider; MDZ OCR not applicable'}
        books.append(z)
    with (OUT/'book_diagnostics.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(books[0])); w.writeheader(); w.writerows(books)
    write(OUT/'summary.json',summary); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('mode',choices=['fetch','analyze']); args=p.parse_args(); globals()[args.mode]()

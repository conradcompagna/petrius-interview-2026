"""Validate detector exports and summarize counts, without claiming accuracy."""
import math
from collections import Counter
from datetime import datetime, timezone
from .common import ROOT, OUT, MANIFEST, SYSTEMS, read, sha, write


def main():
    manifest = read(MANIFEST)
    assert len(manifest['pages']) == 100
    assert len({p['key'] for p in manifest['pages']}) == 100
    report = dict(verified_utc=datetime.now(timezone.utc).isoformat(), manifest_sha256=sha(MANIFEST),
                  interpretation='Counts and integrity only. No independently annotated segmentation gold; these are not accuracy scores.',
                  systems={})
    for name in SYSTEMS:
        folder = (OUT if (OUT/name).exists() else ROOT/'results/segmentation_bakeoff')/name
        rows, missing, errors, outside = [], [], [], []
        config = read(folder/'run_config.json') if (folder/'run_config.json').exists() else None
        for p in manifest['pages']:
            path = folder/p['book']/f"{p['scan']:05d}.json"
            if not path.exists():
                missing.append(p['key'])
                continue
            try:
                data = read(path)
                raw = read(folder/'raw'/p['book']/f"{p['scan']:05d}.json")
                assert data['signature'] == config
                assert data['signature']['manifest_sha256'] == sha(MANIFEST)
                assert data['signature']['device'] == 'cuda:0'
                assert data['image']['sha256'] == sha(ROOT/p['image'])
                baseline = read(ROOT/f"data/segmentation_bakeoff/baseline/{p['book']}/{p['scan']:05d}.json")
                assert data['image'] == baseline['image']
                units = data['lines'] + data['regions']
                assert len({u['id'] for u in units}) == len(units)
                expected = raw['bboxes'] if name == 'surya' else raw['boxes']
                assert len(units) == len(expected)
                assert not data['semantic_labels_assigned'] and not data['human_gold']
                assert not data['signature']['custom_layout_rules'] and not data['signature']['fine_tuned']
                for i,u in enumerate(units):
                    assert len(u['polygon']) >= 3
                    assert all(math.isfinite(c) for point in u['polygon'] for c in point)
                    if name == 'surya':
                        assert u['polygon'] == raw['bboxes'][i]['polygon']
                    elif name == 'ppocr':
                        assert u['polygon'] == raw['boxes'][i]
                    elif raw['polygon_points'][i] is not None and len(raw['polygon_points'][i]) >= 3:
                        assert u['polygon'] == raw['polygon_points'][i]
                    x0,y0,x1,y1 = u['bbox']
                    if not (-1 <= x0 <= x1 <= data['image']['width']+1 and -1 <= y0 <= y1 <= data['image']['height']+1):
                        outside.append(dict(page=p['key'], id=u['id'], bbox=u['bbox']))
                rows.append(dict(key=p['key'], lines=len(data['lines']), blocks=len(data['regions']),
                                 seconds=data['timing_seconds'], gpu_peak_allocated_mib=data['gpu_peak_allocated_mib'],
                                 labels=dict(Counter(u['label'] for u in units))))
            except Exception as error:
                errors.append(dict(key=p['key'], error=repr(error)))
        report['systems'][name] = dict(completed=len(rows), expected=100, missing=missing, errors=errors,
                                      total_lines=sum(r['lines'] for r in rows), total_blocks=sum(r['blocks'] for r in rows),
                                      empty_pages=[r['key'] for r in rows if not r['lines'] and not r['blocks']],
                                      outside_image=outside, seconds=sum(r['seconds'] for r in rows),
                                      gpu_peak_allocated_mib=max((r['gpu_peak_allocated_mib'] for r in rows),default=0), pages=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT/'report.json', report)
    print({n:{k:v for k,v in s.items() if k not in ['pages','missing','outside_image']} for n,s in report['systems'].items()})
    if any(s['errors'] or s['missing'] for s in report['systems'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

"""Layout families of the 100-book corpus: definition, classifier, evaluation.

    python -m experiments.layout_families.classify [--work outputs/layout_families]

Families (level 1) are defined by attributes one can check on the page: script of the primary text, whether a
gloss surrounds it, and the number of text columns. Labels for all 100 books were assigned by Claude from
contact sheets (AI-silver, `labels.json`).
The classifier sees page descriptors (extract.py) and a typeface embedding (embed.py).
Evaluation is leave-one-book-out: the book being classified is never in training. The 20 formerly sealed
books were first assigned blind (18 of 20 right, `sealed_blind_check.json`) and then labelled.
"""
import argparse, json, collections
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .common import ROOT, PKG

F = PKG; W = F / 'work'
TONE = {'saturation', 'value', 'ink'}
NAMES = {'GG': 'Gothic type, gloss surrounding a two-column text', 'RG': 'Roman type, gloss surrounding a two-column text',
         'RU': 'Roman type, no surrounding gloss, single text column', 'RN': 'Roman type, two columns with notes at the foot, no surrounding gloss',
         'MX': 'Roman text with Gothic gloss, small format', 'GU': 'Gothic type, two columns, no gloss'}


def load():
    keys = json.loads((W / 'feature_keys.json').read_text(encoding="utf-8")); z = np.load(W / 'embeddings.npz'); names = [n[:-4] for n in z['names']]
    feat = {}
    for f in (W / 'pages').glob('*.json'):
        for r in json.loads(f.read_text(encoding="utf-8")): feat[f"{r['book']}_{r['scan']:05d}"] = [r['features'][k] for k in keys]
    H = np.array([feat[n] for n in names]); book = np.array([n.rsplit('_', 1)[0] for n in names])
    keep = [i for i, k in enumerate(keys) if k not in TONE]     # scan tone is a property of the digitisation, not of the layout
    return names, book, np.hstack([H[:, keep], z['patch']]), [keys[i] for i in keep]


def model():
    return make_pipeline(StandardScaler(), LogisticRegression(C=.3, max_iter=4000))


def main():
    (ROOT / "outputs/layout_families").mkdir(parents=True, exist_ok=True)
    names, book, X, keys = load()
    inv = {b['id']: b for b in json.loads((ROOT / 'data/corpus/books.json').read_text(encoding="utf-8"))['books']}
    L = json.loads((F / 'labels.json').read_text(encoding="utf-8"))
    dev = sorted(L); yb = np.array([L.get(b, '') for b in book]); isdev = yb != ''
    pred = np.empty(len(book), object); conf = np.zeros(len(book))
    for b in dev:
        tr = isdev & (book != b); te = book == b
        m = model().fit(X[tr], yb[tr]); P = m.predict_proba(X[te]); pred[te] = m.classes_[P.argmax(1)]; conf[te] = P.max(1)
    rep = dict(families={k: dict(name=NAMES[k], development_books=sum(v == k for v in L.values())) for k in NAMES}, evaluation={})
    big = [k for k in NAMES if rep['families'][k]['development_books'] >= 5]
    def acc(mask): return dict(pages=int(mask.sum()), correct=int((pred[mask] == yb[mask]).sum()), accuracy=round(float((pred[mask] == yb[mask]).mean()), 4))
    rep['evaluation']['page_level_all_development_books'] = acc(isdev)
    rep['evaluation']['page_level_families_with_5_or_more_books'] = acc(isdev & np.isin(yb, big))
    sure = isdev & np.isin(yb, big) & (conf >= .8)
    rep['evaluation']['page_level_same_confidence_at_least_0.8'] = dict(acc(sure), coverage=round(float(sure.sum() / (isdev & np.isin(yb, big)).sum()), 4))
    votes = {}
    for b in dev:
        te = book == b; score = collections.Counter()
        for p, cf in zip(pred[te], conf[te]): score[p] += cf
        votes[b] = score.most_common(1)[0][0]
    rep['evaluation']['book_level_vote_all'] = dict(books=len(dev), correct=sum(votes[b] == L[b] for b in dev))
    rep['evaluation']['book_level_vote_families_with_5_or_more_books'] = dict(books=sum(L[b] in big for b in dev), correct=sum(votes[b] == L[b] for b in dev if L[b] in big))
    rep['evaluation']['book_errors'] = [dict(book=b, family=L[b], predicted=votes[b]) for b in dev if votes[b] != L[b]]
    rep['evaluation']['confusion_pages'] = {t: dict(collections.Counter(pred[isdev & (yb == t)])) for t in NAMES if (yb == t).any()}
    rep['evaluation']['wrong_pages'] = [dict(page=names[i], family=yb[i], predicted=pred[i], confidence=round(float(conf[i]), 2)) for i in np.flatnonzero(isdev) if pred[i] != yb[i] and yb[i] in big]
    # catalogue date alone
    rep['evaluation']['catalogue_date_rule'] = dict(rule='year <= 1525 -> Gothic glossed, else Roman', correct=sum((inv[b]['date_sort'] <= 1525) == L[b].startswith('GG') for b in dev), books=len(dev), exceptions=[b for b in dev if (inv[b]['date_sort'] <= 1525) != L[b].startswith('GG')])
    # final model on all development pages; assign every book
    m = model().fit(X[isdev], yb[isdev]); P = m.predict_proba(X); out = {}
    for b in sorted(inv):
        te = book == b; s = P[te].sum(0) / te.sum(); k = int(s.argmax())
        out[b] = dict(family=m.classes_[k], share=round(float(s[k]), 3), date=inv[b]['date_sort'], work=inv[b]['work'], place=inv[b]['place'],
                      status='labelled',
                      label=L.get(b), page_votes=dict(collections.Counter(m.classes_[P[te].argmax(1)])))
    rep['assignment_counts'] = dict(collections.Counter(v['family'] for v in out.values()))
    rep['sealed_assignment_counts'] = dict(collections.Counter(v['family'] for v in out.values() if v['label'] is None))
    (ROOT / 'outputs/layout_families/assignments.json').write_text(json.dumps(out, indent=1)); (ROOT / 'outputs/layout_families/report.json').write_text(json.dumps(rep, indent=1, default=str))
    import joblib; joblib.dump(dict(model=m, feature_keys=keys), ROOT / 'outputs/layout_families/family_classifier.joblib')
    e = rep['evaluation']; print(json.dumps({k: e[k] for k in e if k not in ('wrong_pages',)}, indent=1, default=str)); print(rep['assignment_counts'], rep['sealed_assignment_counts'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, default=W)
    W = parser.parse_args().work
    main()

"""Train and test end to end. Run from the repository root.
  python -m training.neural.run train  NAME   open-ended: train both taggers on the 100 training pages, one epoch each per round,
                                         score the 20 evaluation pages after every round, save models/NAME.pt whenever a tagger
                                         improves. Press Ctrl+C once to stop; the best weights are then scored and reported.
  python -m training.neural.run frozen NAME   train on the 100 training pages; the 20 evaluation pages are scored during training
                                         and the best-scoring epoch of each tagger is kept; saves models/NAME.pt
  python -m training.neural.run lobo   NAME   leave-one-book-out over the 100 training pages (resumes after an interruption)
Options: epochs=40 repochs=60 seed=0 only=book,book (load a subset; for code checks)
Annotated duplicate regions are left out of training and scoring. Score: every other line of the test pages, five classes
(four roles + outside), macro-F1 over the four roles. Log and results go to outputs/training/neural/features/."""
import sys, os, json, time, collections, numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from .train import *
mode, name = sys.argv[1], sys.argv[2]; kw = dict(a.split("=") for a in sys.argv[3:])
epochs, repochs, seed = int(kw.get("epochs", 40)), int(kw.get("repochs", 60)), int(kw.get("seed", 0))
W = str(WORK); os.makedirs(W, exist_ok=True); logf = open(os.path.join(W, "%s_%s.log" % (mode, name)), "a", encoding="utf-8")
def log(s):
    print(s, flush=True); logf.write(s + "\n"); logf.flush()
log("=== %s %s  %s  device %s%s  torch %s" % (mode, name, time.strftime("%Y-%m-%d %H:%M"), DEV, " (" + torch.cuda.get_device_name(0) + ")" if DEV.type == "cuda" else "", torch.__version__))
d = load(kw["only"].split(",") if "only" in kw else None)
y5 = d["y"]; yrole = y5.copy(); yrole[y5 == 4] = -1; ytr = yrole.copy(); ytr[d["review"] != "webgpt_reviewed"] = -1
ridx = {(k, r): i for i, (k, r) in enumerate(zip(d["R_key"], d["R_rid"]))}
lreg = np.array([ridx[(k, r)] for k, r in zip(d["key"], d["rid"])])                  # region index of every line
rkeep = ~d["R_golddup"].astype(bool)
pages_r = collections.defaultdict(list); lines_of = collections.defaultdict(list)
for i in np.where(rkeep)[0]: pages_r[d["R_key"][i]].append(int(i))
for i, r in enumerate(lreg): lines_of[int(r)].append(i)
part = {k: p for k, p in zip(d["R_key"], d["R_part"])}; keys = sorted(pages_r); books = sorted(set(k.split("/")[0] for k in keys))
folds = [([k for k in keys if part[k] == "training" and not k.startswith(b)], [k for k in keys if part[k] == "training" and k.startswith(b)], b) for b in books] if mode == "lobo" \
    else [([k for k in keys if part[k] == "training"], [k for k in keys if part[k] == "evaluation"], "frozen")]
log("lines %d  regions %d (annotated duplicates left out: %d)  pages %d%s" % (len(y5), int(rkeep.sum()), int((~rkeep).sum()), len(keys), "" if mode == "train" else "  epochs %d/%d" % (repochs, epochs)))


def central(page_regions, flag):
    """line indices of the regions of one page for which flag(region index) is true"""
    return [i for r in page_regions if flag(r) for i in lines_of[r]]


pred5 = np.full(len(y5), -1); pred_gs = np.full(len(y5), -1); conf = np.zeros(len(y5), np.float32); rprob = np.full(len(d["R_y"]), -1.0); t0 = time.time()
for trk, tek, tag in folds:
    ck = os.path.join(W, "fold_%s_%s_%s.npz" % (mode, name, tag)); te_r = np.array([r for k in tek for r in pages_r[k]]); te_l = np.array([i for r in te_r for i in lines_of[r]])
    if mode == "lobo" and os.path.exists(ck):
        z = np.load(ck); pred5[te_l] = z["p5"]; pred_gs[te_l] = z["pg"]; rprob[te_r] = z["rp"]; conf[te_l] = z["cf"]
    else:
        log("--- %s: training on %d pages, evaluating on %d" % ("evaluation split" if tag == "frozen" else "held out " + tag, len(trk), len(tek)))
        tr_l = np.array([i for k in trk for r in pages_r[k] for i in lines_of[r]]); voc = vocab(d["text"][tr_l])
        gs = [s for s in (central(pages_r[k], lambda r: d["R_y"][r] == 1) for k in tek) if s]          # annotated scope
        watch = mode == "frozen"            # the evaluation pages are scored during training and the best epoch is kept
        if mode == "train":
            R = Regions(d, voc, seed); L = Lines(d, voc, seed); mp = os.path.join(ROOT, "outputs/training/neural/models", "%s.pt" % name); os.makedirs(os.path.dirname(mp), exist_ok=True)
            def reval():
                q = R.predict([pages_r[k] for k in tek]); return float(np.mean([(q[r] >= 0.5) == (d["R_y"][r] == 1) for r in te_r]))
            def leval():
                q = L.predict(gs); ii = np.array([i for i in q if yrole[i] >= 0]); return float(np.mean(f1s(yrole[ii], np.array([q[i].argmax() for i in ii]))))
            snap = lambda m: {k: v.detach().cpu().clone() for k, v in m.state_dict().items()}
            R.start([pages_r[k] for k in trk]); L.start([s for s in (central(pages_r[k], lambda r: d["R_y"][r] == 1) for k in trk) if s], ytr)
            best = {"r": -1.0, "l": -1.0, "rs": snap(R.model), "ls": snap(L.model), "re": 0, "le": 0}; rnd = 0
            log("Open-ended training. Press Ctrl+C ONCE to stop; the best weights are saved at every improvement.")
            try:
                while True:
                    rnd += 1; t1 = time.time(); rl = R.epoch(); ll = L.epoch(); ra = reval(); lf = leval(); new = ""
                    if ra > best["r"]: best.update(r=ra, rs=snap(R.model), re=rnd); new += " regions"
                    if lf > best["l"]: best.update(l=lf, ls=snap(L.model), le=rnd); new += " lines"
                    R.stalled(ra); lr_ = L.stalled(lf)
                    if new:
                        torch.save({"regions": best["rs"], "lines": best["ls"], "vocab": voc}, mp + ".tmp"); os.replace(mp + ".tmp", mp)
                    log("round %3d | regions loss %.4f accuracy %.4f (best %.4f @%d) | lines loss %.4f macro-F1 %.4f (best %.4f @%d) lr %.0e | %.1fs%s" % (
                        rnd, rl, ra, best["r"], best["re"], ll, lf, best["l"], best["le"], lr_, time.time() - t1, "   <- new best:" + new if new else ""))
            except KeyboardInterrupt:
                log("Stopped after %d rounds. Scoring the best weights (regions from round %d, lines from round %d)." % (rnd, best["re"], best["le"]))
            R.model.load_state_dict(best["rs"]); L.model.load_state_dict(best["ls"])
        if mode == "train": pass
        else: R = Regions(d, voc, seed)
        def reval():
            q = R.predict([pages_r[k] for k in tek]); return float(np.mean([(q[r] >= 0.5) == (d["R_y"][r] == 1) for r in te_r]))
        if mode != "train": R.fit([pages_r[k] for k in trk], epochs=repochs, log=log, evalfn=reval if watch else None)
        rp = R.predict([pages_r[k] for k in tek]); rprob[te_r] = [rp[r] for r in te_r]
        if mode != "train": L = Lines(d, voc, seed)
        tr = [central(pages_r[k], lambda r: d["R_y"][r] == 1) for k in trk]
        def leval():
            q = L.predict(gs); ii = np.array([i for i in q if yrole[i] >= 0]); return float(np.mean(f1s(yrole[ii], np.array([q[i].argmax() for i in ii]))))
        if mode != "train": L.fit([s for s in tr if s], ytr, epochs=epochs, log=log, evalfn=leval if watch else None)
        ps = [s for s in (central(pages_r[k], lambda r: rp[r] >= 0.5) for k in tek) if s]              # predicted scope
        for i, q in L.predict(gs).items(): pred_gs[i] = int(q.argmax())
        pred5[te_l] = 4
        for i, q in L.predict(ps).items(): pred5[i] = int(q.argmax()); conf[i] = float(q.max())
        if mode == "lobo": np.savez(ck, p5=pred5[te_l], pg=pred_gs[te_l], rp=rprob[te_r], cf=conf[te_l])
        else:
            os.makedirs(os.path.join(ROOT, "outputs/training/neural/models"), exist_ok=True)
            torch.save({"regions": R.model.state_dict(), "lines": L.model.state_dict(), "vocab": voc}, os.path.join(ROOT, "outputs/training/neural/models", "%s.pt" % name))
    f = f1s(y5[te_l], pred5[te_l]); g = d["R_y"][te_r] == 1; p = rprob[te_r] >= 0.5
    log("%-12s end-to-end macro-F1 %.3f | text %.2f summ %.2f insc %.2f other %.2f | regions wrong %d of %d  (%.0fs)" % (tag, np.mean(f), *f, (g != p).sum(), len(g), time.time() - t0))
m = pred5 >= 0; f = f1s(y5[m], pred5[m], 5); cm = np.zeros((5, 5), int)
for g, p in zip(y5[m], pred5[m]): cm[g, p] += 1
rm = rprob >= 0; g = d["R_y"][rm] == 1; p = rprob[rm] >= 0.5
nin = np.array([int((y5[lines_of[r]] != 4).sum()) for r in np.where(rm)[0]]); nl = np.array([len(lines_of[r]) for r in np.where(rm)[0]])
log("== REGIONS %d  accuracy %.4f  missed central %d  false central %d | central lines lost %d of %d, outside lines admitted %d of %d" % (
    rm.sum(), (g == p).mean(), (g & ~p).sum(), (~g & p).sum(), nin[~p].sum(), nin.sum(), (nl - nin)[p].sum(), (nl - nin).sum()))
log("== END-TO-END lines %d  macro-F1 (4 roles) %.4f | text %.3f summ %.3f insc %.3f other %.3f | outside %.3f" % (m.sum(), np.mean(f[:4]), *f))
log("confusion, rows reference / cols predicted (text summ insc other outside)\n" + str(cm))
g = (pred_gs >= 0) & (yrole >= 0); f = f1s(yrole[g], pred_gs[g])
log("== ANNOTATED SCOPE lines %d  accuracy %.4f  macro-F1 %.4f | text %.3f summ %.3f insc %.3f other %.3f" % (g.sum(), (yrole[g] == pred_gs[g]).mean(), np.mean(f), *f))
json.dump({"lines": {d["key"][i] + "|" + d["lid"][i]: [int(y5[i]), int(pred5[i]), round(float(conf[i]), 3)] for i in np.where(m)[0]},
           "regions": {d["R_key"][i] + "|" + d["R_rid"][i]: [int(d["R_y"][i]), round(float(rprob[i]), 4)] for i in np.where(rm)[0]}},
          open(os.path.join(W, "result_%s_%s.json" % (mode, name)), "w"))
log("=== done in %.0f s" % (time.time() - t0))

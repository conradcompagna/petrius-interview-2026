# Historical Latin Document Analysis

Early printed Latin legal books place central text inside surrounding gloss, with summaries, inscriptions, headings and initials marking different textual functions. Library OCR often joins these layers into single rows. Separating their boundaries and roles permits analysis of the legal text and its commentary.

The pipeline combines **fine-tuned D-FINE Large region detection**, **PERO line detection and OCR**, and **V3: two custom multimodal transformers trained from scratch**. A two-layer region transformer selects central text regions. A four-layer line transformer assigns `text`, `summarium`, `inscriptio` or `other`; surrounding material is `outside`. Both combine image features, recognized characters and page coordinates.

**[Annotation and prediction viewer](https://conradcompagna.github.io/historical-latin-document-analysis/)** · [Model and source-image downloads](https://github.com/conradcompagna/historical-latin-document-analysis/releases/tag/research-models-v1)

## Code and data

| Folder | Contents |
|---|---|
| [`inference/`](inference/) | Complete image-to-labelled-text pipeline and V3 architecture. |
| [`training/`](training/) | D-FINE fine-tuning; V3 input construction, training and evaluation; annotation export and validation. |
| [`data/`](data/) | Full detector and classifier annotations, frozen splits, OCR inputs, source identities and character-model training text. |
| [`models/`](models/) | Model specifications and configurations; weights installed from the release. |
| [`results/`](results/) | Retained training histories, predictions and experiment results. |
| [`experiments/`](experiments/) | Character language models, OCR diagnostics, layout-family classification and the segmentation bakeoff. |
| [`site/`](site/) | Source-image inspection, reference/prediction comparison and OCR heatmaps. |

The detector dataset contains **100 training pages from 20 books and 20 evaluation pages from 20 other books**, with 1,428 regions. V3 uses **100 training pages and 20 evaluation pages from ten matching-layout books**, with 32,018 detected lines. Git contains the annotations, OCR and frozen splits; release assets contain the exact source images and weights.

D-FINE epoch 14 has pooled region F1 of 0.862 at IoU 0.50 and 0.745 at IoU 0.75. V3 has four-role macro-F1 of 0.945 on its 20 model-selection pages, excluding annotated duplicate regions.

Region and line annotations were generated with language models and manually reviewed and corrected by Conrad Compagna, who also personally verified the original two example pages. Layout-family labels were model-assigned. Code was developed with Claude and Codex under Conrad Compagna's direction.

## Experiments

- **Character language models:** sixth-order interpolated Kneser–Ney models and three treatments of abbreviation marks. Changing the reference corpus with normalization held constant reduces pooled surprise from 3.563 to 3.445 bits/character on 50 Gothic OCR pages. Training text and row scores are included.
- **OCR audit:** lexical diagnostics and OCR rows crossing textual boundaries; 119 acquired pages and 1,535 flagged rows in the accepted-region sample.
- **Layout families:** page measurements and frozen visual embeddings classify 100 books, with complete books held out during evaluation.
- **Segmentation bakeoff:** stock Surya, PP-OCRv5 and PP-DocLayoutV3 on 100 scans; all 300 outputs and native records retained, with line counts and block counts recorded separately.

## Execution

Python 3.12; commands run from the repository root. Training and bakeoff dependencies are in `requirements/`. D-FINE training requires CUDA with BF16 support; the bakeoff requires CUDA.

```sh
python -m pip install -r requirements/inference-cpu.txt
python tools/get_assets.py --group core
python -m inference.run page.jpg --device cpu
```

`outputs/inference/` contains geometry, OCR, predictions, overlays and extracted central text. `--device cuda` selects CUDA.

Training images are installed with `python tools/get_assets.py --group training`. D-FINE training uses the separate `requirements/training-dfine.txt` environment and runs `python -m training.dfine.train --mode pilot`, `python -m training.dfine.verify_export`, then `python -m training.dfine.train --mode full`. The pilot comparison images are reviewed before recording `passed` and its `checkpoint_sha256` in `outputs/training/dfine/pilot/visual_review.json`. V3 uses `requirements/training-neural.txt`: `python -m training.neural.extract`, then `python -m training.neural.run train reproduction`. Ctrl+C retains its best selected weights.

Experiment entry points are `python -m experiments.charlm.run`, `python -m experiments.ocr_audit.audit analyze`, `python -m experiments.layout_families.classify`, and `python -m experiments.segmentation_bakeoff.run --system surya`. Asset groups `experiments` and `bakeoff` supply their inputs and weights. New reports are written to `outputs/`; retained results are in `results/`.

Checks: `python tools/verify_repository.py` and `python tools/validate_static_site.py site`. [`source_map.json`](source_map.json) records source provenance. Library image rights and upstream model sources accompany the data and models.

# Presentation evidence

Prepared 7 October 2026 for the interview on 20 October 2026. The deck contains three five-minute presentations and three appendix slides.

## Assignment and source images

- Requirements: `PetrIUS Interview Tasks for the Postdoc 4 Position.docx`, Tasks I, III and IV.
- The supplied Task III images are `D. 1.1.1. 1490.jpg` and `D. 1.1.1. 1627.jpg`. Complete originals are retained in `assets/source_1490.jpg` and `assets/source_1627.jpg`.
- `assets/divisio_1490.png`: source-image rectangle `(135, 2205, 863, 2430)`.
- `assets/divisio_1627.png`: source-image rectangle `(180, 1962, 895, 2198)`.
- The Task III authority contrast comes from the assignment and these image crops: `Jac. de arena` and `Bar.` in 1490; `B.` in 1627.

## Task I: minimal program

- Program: `task1_min/task1.py`.
- Reference and source overlays: `task1_min/reference.csv`, `task1_min/labels_00040.jpg`, `task1_min/labels_00041.jpg`.
- Matrix: text 60; summarium 16; inscriptio 7; other 6; outside 42; all 131 references classified correctly.
- The completed program additionally identifies six gutter line numbers and the woodcut initial and rejects the two junk OCR fragments identified during review.
- The user personally inspected the two task-page outputs and personally checks the submission materials.
- MDZ image endpoint: `https://api.digitale-sammlungen.de/iiif/image/v2/bsb10144443_00040/full/full/0/default.jpg`, repeated with `00041`.
- MDZ hOCR endpoint: `https://api.digitale-sammlungen.de/ocr/bsb10144443/40`, repeated with `/41`.

## D-FINE region detector

- Checkpoint: `out/dfine_region_training_v1/full/best_instances.safetensors`, epoch 14, step 1400.
- Dataset: `out/dfine_region_training_v1/data_manifest.json`, 100 training pages from 20 books and 20 evaluation pages from 20 other books.
- Metrics: epoch-14 record in `out/dfine_region_training_v1/full/epoch_metrics.jsonl`.
- At IoU 0.50: 206 true-positive regions, 32 extra detections, 34 misses; pooled F1 = `412 / 478 = 0.8619246862`.
- At IoU 0.75: 178 true-positive regions, 60 extra detections, 62 misses; pooled F1 = `356 / 478 = 0.7447698745`.
- The slide uses **pooled region F1**, not mean per-page F1 or COCO average precision.

## PERO and neural v3

- PERO provenance: `out/dfine_pero_interview_v1/provenance.json`, ParseNet_296000 and OCR_350000, with language-model decoding off.
- Neural model: `line_nn_v3/models/full.pt`; architecture: `line_nn_v3/model.py`.
- Dataset: `out/central_block_annotations_v1/manifest.json`, 100 training and 20 evaluation pages from ten Roman-glossed books.
- Evaluation: `line_nn_v3/work/result_train_full.json` and `line_nn_v3/work/train_full.log`.
- Role result: 5,051 correct of 5,065 supplied lines; 14 errors. Four-role macro-F1 0.9450109126. F1 values: text 0.9938725490; summarium 0.9896193772; inscriptio 0.8965517241; other 0.9000000000.
- All 384 supplied region candidates receive the correct central/outside classification in this evaluation.
- Main-slide neural overlay derives from `out/line_nn_v3/task_predictions/bsb10144443/00040.json`. A second overlay, from scan 41, is also retained in `assets/`.
- D-FINE region detection and v3 role classification are distinct evaluations. The neural line scores use the supplied region and line geometries.
- `metrics.json` records the exact confusion matrix and chart inputs.

## Development scope and LLM use

- `FINDINGS.md`, section 12, describes the acquisition, annotation, experiment, training and viewer implementation and the six-day timeline.
- `out/webgpt_ocr_fullpage100_20261006/timeline_evidence.json` records dated milestones from 1–6 October 2026.
- The slides use the rounded source inventory: 26,000+ lines across 200+ source files, excluding virtual environments, third-party repositories, data and model outputs.
- Claude and Codex were used for implementation, debugging and experiments; ChatGPT generated annotation drafts under the user's direction. The user reviewed the annotations and checks the submission.

## Task III method documentation

- [RapidFuzz, official documentation](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html): fuzzy matching for candidate retrieval. Consulted 7 October 2026.
- [CollateX, official documentation](https://collatex.net/doc/): multiple-witness text alignment. Consulted 7 October 2026.
- Character n-grams, explicit abbreviation alternatives, a jurist authority list and named-content fields are components of the proposed research design. Names, citations, negation, conditions and exceptions are retained as comparison targets.
- The comparison-desk image on slide 10 is an editable design sketch for the proposed workflow.

## Task IV pilot edition identifiers

Edition metadata and source-rights fields come from `corpus/benchmark_inventory.json`.

| Edition | Library identifier | Proposed pages |
|---|---|---:|
| Digestum vetus, Venice 1490 | `bsb00051759` | 60 |
| Digestum vetus, Lyon 1569 | `bsb11396145` | 60 |
| Digest / Pandects, Venice 1606 | `bsb10520013` | 60 |
| Digestum vetus, Lyon 1627 | `heidelberg_justinian1627bd1` | 60 |
| Decretals, Venice 1494 | `bsb00082927` | 60 |
| Decretals, Rome 1582 | `bsb10144443` | 60 |

The 240/60/60 page split, matched-locus sample, six-month schedule and success targets are the proposed December 2026–May 2027 pilot. Current model results appear in Task I; pilot targets appear in Task IV. The release design records terms separately for every library item and uses library links and retrieval scripts for image access.

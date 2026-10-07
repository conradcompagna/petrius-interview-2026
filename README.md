# PetrIUS interview submission

Conrad Compagna · October 2026

This package contains the reproducible solution for scans 40 and 41 of the 1582 Decretals, the page viewer, two annotated datasets, the trained D-FINE and neural classification models, and the interview presentation.

The advance written Task I handoff is **`Task_I_written_submission.zip`** in the repository release: the program, reference, overlays, evaluation and two-page note in one small archive. The full package supplies the viewer, models and presentation as supporting material. Task II is a separate document.

## Start here

1. **Inspect the results:** double-click `RUN_VIEWER.bat`. The viewer runs with Python's standard library and opens in your browser.
2. **Reproduce Task I:** double-click `task1_min/run.bat`. It installs OpenCV and NumPy, downloads both page images and their MDZ OCR, and produces the labelled pages and evaluation.
3. **Run the trained models:** double-click `inference/run.bat`. It downloads the selected weights when needed, installs the tested CPU environment and processes the two interview pages. See [the inference instructions](inference/README.md) for your own images.
4. **Read the two-page note:** [PDF](docs/task1_note.pdf) · [editable Word document](docs/task1_note.docx).
5. **Present the results:** the `presentation/` directory contains the fifteen-minute slide deck and speaking material for Tasks I, III and IV.

Install **Python 3.12** with the Windows Python launcher. GitHub's source ZIP includes the complete browser viewer: all 67 collections, 4,093 page records and their annotations. Page images load directly from the libraries. Extract the source ZIP and run `RUN_VIEWER.bat`; no model download is needed to inspect the work.

The trained models are in the release's **`assets-models-01.zip`** (490 MB). `inference/run.bat` retrieves them automatically, or run `GET_ASSETS.bat` to install them separately. The downloader verifies the archive and every extracted file. It uses a direct HTTPS download for a public release and authenticated GitHub CLI access while the repository is private. You can also extract the model ZIP into this folder so `models/` sits beside this README.

The author's full offline copy includes six additional `assets-viewer_data-*.zip` archives, retained locally. Extract all six into this folder to use saved library images without an internet connection. Their file inventory and hashes are in [the offline manifest](docs/offline_assets.json); these optional archives are separate from the GitHub release.

## The task solution

The small Task I program measures red ink, slant and relative type size on the image, uses the library's OCR lines and words, and identifies the two decretal blocks. It reproduces **131 of 131 reference decisions**. I checked the labels against both page images personally. The source, coloured overlays, per-line records and confusion matrix are in `task1_min/`.

## The viewer

The default collections show the completed work:

- D-FINE region annotations: 120 pages, comprising 100 training pages and 20 evaluation pages.
- Neural classifier annotations: 120 pages, comprising 100 training pages and 20 evaluation pages.
- D-FINE results on its 20 evaluation pages.
- Neural classifier results on its 20 evaluation pages.
- The two interview pages processed with D-FINE, PERO and the neural classifier.
- The two interview pages processed with the small Task I program.

Select a page, toggle the overlay layers, inspect individual regions and lines, and compare outputs. Earlier systems and unsuccessful experiments are inside a separate collapsed section. Each page retains its source identity and image coordinates.

The browser-only version in `site/` is prepared for GitHub Pages. [The publication instructions](docs/GITHUB_PAGES.md) explain how to preview it locally and publish it when this repository is made public. The repository and viewer remain private now.

## Models and datasets

The larger pipeline detects text regions with the fine-tuned D-FINE model, detects and recognises lines with PERO, then classifies regions and lines with the v3 neural model. Model weights, configuration, inference code and commands accompany the package. No LLM account or API key is required to run it.

The two 120-page datasets serve different tasks. The detector dataset contains 100 training pages from 20 books and 20 evaluation pages from 20 additional books. The semantic dataset contains 100 training and 20 evaluation pages from ten books. Both datasets are available in the viewer with the corresponding source images and labels.

## Written and oral deliverables

| Task | Material |
|---|---|
| I | `task1_min/`, `docs/task1_note.pdf`, viewer and model package |
| II | The literature comment is being prepared separately by the author |
| III | Paratext retrieval, variant comparison and attribution changes in `presentation/` |
| IV | Six-month plan from December 2026 to May 2027 in `presentation/` |

The written submission is due 12 October 2026. The confirmed interview is 20 October 2026 at 08:00 CEST.

## Tools and authorship

I used Claude and Codex to write and revise code, run experiments and investigate failures under my direction. ChatGPT generated region and line annotations from the images. I reviewed the annotations and personally verify the submission. I chose the research objectives, experiments and final systems. The work developed over 1–6 October into more than 26,000 lines of project code across more than 200 files, with multiple competing models tested and three neural classifier versions developed.

## Sources and rights

[MDZ interfaces and source acknowledgements](docs/SOURCES.md) give the exact image, OCR and manifest addresses. [Third-party notices](docs/THIRD_PARTY_NOTICES.md) identify the upstream software and model sources. The library images retain their source rights statements. This repository is private; the confidential project description and correspondence are not included.

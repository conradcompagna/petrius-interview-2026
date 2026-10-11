# PetrIUS interview submission

I first completed Task I with a gradient-boosted tree classifier, which I thought had the best chance of generalizing to the wider project without training a neural network. It did not, so I have submitted two things: a simpler parser for the two assigned pages and a fully functional neural pipeline for the task book and other MDZ books with the same layout of central legal text, summaries and inscriptions. The pipeline combines a fine-tuned D-FINE region detector, PERO line detection and OCR, and a multistage, multimodal transformer model that encodes image and text inputs, identifies the central regions and classifies their lines according to the task taxonomy. Both models used annotation datasets covering 120 pages, synthetically generated and then manually reviewed and corrected. The pipeline resembles what I would use in the research project, though smaller and targeted to this layout. This repository contains the code, [trained weights](https://github.com/conradcompagna/petrius-interview-2026/releases/download/interview-2026-10-07/assets-models-01.zip), and a [viewer](https://conradcompagna.github.io/petrius-interview-2026/) for inspecting the datasets discussed in [my note](docs/Notenew.docx).

| Folder | Contents |
|---|---|
| `task1_min/` | Task I parser, reference labels and evaluation results |
| `inference/` | Neural pipeline, random-page sampler and dependencies |
| `models/` (downloaded separately) | D-FINE, PERO and neural-tagger weights |
| `site/` | Viewer and datasets |
| `tools/` | Model downloader and site validator |
| `docs/` | Submission note, model manifest, image sources and verification records |
| `.github/workflows/` | Viewer deployment |

## [Open the viewer](https://conradcompagna.github.io/petrius-interview-2026/)

- **1 · Task I:** Algorithm-based parser results on scans 40–41.
- **2a · First parser, same book:** The 102-page review sample from the 1582 Decretals.
- **2b · First parser, other books:** Parser results on 132 pages from eleven other editions.
- **3a · MDZ OCR, region crossings:** Fifty sample pages showing OCR rows crossing region boundaries.
- **3b · MDZ OCR, dictionary scores:** Fifty sample pages with the lowest dictionary-match scores.
- **4 · Stock models:** Layout and OCR comparisons on fourteen sample pages.
- **5a · Region annotations:** Annotated regions on 100 training pages and 20 evaluation pages.
- **5b · D-FINE evaluation:** Predicted regions on the 20 held-out pages.
- **6a · Line annotations:** Line labels, OCR and mixed-line spans on 100 training pages and 20 evaluation pages.
- **6b · Neural-tagger evaluation:** Predicted region and line labels on the 20 held-out pages.
- **6c · Full pipeline:** D-FINE, PERO and neural-tagger results on the two task pages.
- **7 · Full pipeline, fresh pages:** Results on ten random legal-text pages from ten matching-layout books.

## Run the Task I parser and evaluation

1. **Code → Download ZIP**; extract and open `petrius-interview-2026-main`.
2. [Install Python 3.12 for Windows](https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe) with **Add python.exe to PATH** enabled.
3. Open `task1_min` and double-click `run.bat`.

Results in `task1_min`: labelled JPGs, `lines.csv` and `evaluation.json` (comparison with `reference.csv`).

## Run the neural pipeline on fresh random pages

Download the repository and install Python as above.

1. In the repository folder, double-click `GET_ASSETS.bat` to download the weights (490 MB).
2. Double-click `RUN_RANDOM_PAGES.bat`.

Processes three random pages from ten matching-layout books, excluding training, evaluation and viewer pages.

Results in the newest `inference/outputs/random_*` folder: `overlays` (images), `text` (text), `predictions` (labels).

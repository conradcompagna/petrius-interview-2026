# Historical Latin Document Analysis interview submission

Conrad Compagna · October 2026

[Open the results viewer](https://conradcompagna.github.io/historical-latin-document-analysis/) · [Task I note](docs/task1_note.pdf) · [Download model weights (490 MB)](https://github.com/conradcompagna/historical-latin-document-analysis/releases/download/interview-2026-10-07/assets-models-01.zip)

## Repository

| Path | Contents |
|---|---|
| `task1_min/` | Task I program for scans 40–41 of the 1582 Decretals, labelled images, line table, reference labels and confusion matrix |
| `inference/` | D-FINE regions → PERO lines and OCR → trained region and line taggers, with a pinned CPU environment |
| `site/` | The results viewer, used both locally and on GitHub Pages; 11 collections and 632 page records |
| `tools/` | Model archive creation, download and verification; static site validation |
| `docs/` | The two-page Task I note, verification records, model download manifest and image-rights inventory |
| `inference/licenses/` | Third-party licences |

## Run inference on your own pages

Requires Python 3.12 on Windows. Download or clone this repository, then run from its root:

```powershell
.\inference\run.bat "C:\pages\page1.jpg" "C:\pages\page2.jpg"
```

The launcher downloads the weights, creates the inference environment and processes the supplied images. With no image arguments it processes the two interview pages. CPU inference is supported; no API key is required. Results are written to `inference/outputs/`: detected regions, OCR, semantic labels, selected text and labelled page images.

To install the weights separately, run `GET_ASSETS.bat`, or download [assets-models-01.zip](https://github.com/conradcompagna/historical-latin-document-analysis/releases/download/interview-2026-10-07/assets-models-01.zip) and extract it beside this README. This creates `models/` with the fine-tuned D-FINE checkpoint, `neural_v3.pt` containing both trained taggers, and PERO's line and OCR models, including their CPU checkpoints. Downloads and extracted files are checked against the hashes in [docs/release_assets.json](docs/release_assets.json).

## Run Task I and the viewer

- **Task I:** double-click `task1_min/run.bat`. It downloads both pages and their MDZ OCR and writes labelled images, the line table and evaluation. The two original task pages were personally verified by Conrad Compagna.
- **Viewer:** [open it on the web](https://conradcompagna.github.io/historical-latin-document-analysis/), or double-click `RUN_VIEWER.bat`. Both use the same `site/` files. To serve it manually, run `python -m http.server 8880 --directory site` and open `http://localhost:8880/`.

## MDZ interfaces

| Resource | Address |
|---|---|
| Manifest | https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb10144443/manifest |
| Scan 40 image | https://api.digitale-sammlungen.de/iiif/image/v2/bsb10144443_00040/full/full/0/default.jpg |
| Scan 41 image | https://api.digitale-sammlungen.de/iiif/image/v2/bsb10144443_00041/full/full/0/default.jpg |
| Scan 40 OCR | https://api.digitale-sammlungen.de/ocr/bsb10144443/40 |
| Scan 41 OCR | https://api.digitale-sammlungen.de/ocr/bsb10144443/41 |

## Third-party components and image credit

- D-FINE through [dfine-kraken](https://pypi.org/project/dfine-kraken/0.4.3/) 0.4.3, Apache-2.0; initial LADaS weights by Benjamin Kiessling, [Zenodo 18715364](https://zenodo.org/records/18715364), Apache-2.0.
- [PERO OCR](https://github.com/DCGM/pero-ocr), BSD 3-Clause; models `pero_eu_cz_print_newspapers_2022-09-26`.
- OpenCV, NumPy, PyTorch.
- Page images: München, Bayerische Staatsbibliothek ([NoC-NC 1.0](https://rightsstatements.org/vocab/NoC-NC/1.0/)). Other libraries' sources and rights are recorded in [site/SOURCES.html](site/SOURCES.html) and [docs/library_rights_inventory.json](docs/library_rights_inventory.json).

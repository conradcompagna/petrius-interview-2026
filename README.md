# PetrIUS interview submission

Conrad Compagna · October 2026

## Repository

| Path | Contents |
|---|---|
| `task1_min/` | Task I program for scans 40–41 of the 1582 Decretals (`task1.py`), with its outputs: `labels_00040.jpg`, `labels_00041.jpg`, `evaluation.json` (confusion matrix), `lines.csv` |
| `inference/` | Trained pipeline: D-FINE regions → PERO lines and OCR → neural tagger (`neural/`) |
| `site/` | Static results viewer, for GitHub Pages |
| `annotation_viewer/` | The same viewer served locally by Python |
| `tools/` | Packaging, asset download and viewer-export scripts |
| `docs/` | Verification records and the image-rights inventory |
| `legal/`, `inference/licenses/` | Third-party licences |

## Run

Requires Python 3.12 on Windows.

- **Task I:** `task1_min/run.bat`. Downloads both pages and their OCR from MDZ and writes the overlays, line table and evaluation.
- **Trained pipeline:** `inference/run.bat [image ...]`. With no arguments it processes the two task pages. Model weights (`assets-models-01.zip`, release asset) download automatically, or run `GET_ASSETS.bat`.
- **Viewer:** `RUN_VIEWER.bat`, or `python -m http.server 8880 --directory site` and open `http://localhost:8880/`.

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
- Page images: München, Bayerische Staatsbibliothek ([NoC-NC 1.0](https://rightsstatements.org/vocab/NoC-NC/1.0/)). Other libraries' rights fields are in `docs/library_rights_inventory.json`.

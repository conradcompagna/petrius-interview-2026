# PetrIUS interview submission

Requires Python 3.12 on Windows for the programs and local reader.

| Folder | Contents |
|---|---|
| `task1_min/` | Task I code, reference labels, labelled page images, line records and confusion matrix |
| `inference/` | D-FINE → PERO → neural taggers; setup, dependencies and third-party licences |
| `site/` | Reader and its page annotations |
| `tools/` | Model download, archive creation and site validation scripts |
| `docs/` | `Notenew.docx`, model download manifest, image sources and verification records |
| `.github/workflows/` | GitHub Pages deployment |

## Run Task I and evaluate

```powershell
.\task1_min\run.bat
```

Downloads scans 40–41 and their MDZ OCR, runs the task program and evaluates its labels against `reference.csv`. Outputs are in `task1_min/`: `labels_00040.jpg`, `labels_00041.jpg`, `lines.csv`, `page_00040.json`, `page_00041.json` and `evaluation.json`.

## Open the reader

[Open the web reader](https://conradcompagna.github.io/petrius-interview-2026/).

To open it locally, double-click `RUN_VIEWER.bat`. It serves `site/` at http://localhost:8880/.

The reader contains Task I results, parser comparisons, MDZ OCR samples, stock-model comparisons, D-FINE training annotations and held-out results, neural-tagger training annotations and held-out results, and full-pipeline results on the two task pages. Select a collection and page to inspect its regions, lines, labels and OCR.

## Download weights and run inference

[Download the model archive (490 MB)](https://github.com/conradcompagna/petrius-interview-2026/releases/download/interview-2026-10-07/assets-models-01.zip) and extract it beside this README. This creates `models/` with D-FINE, both neural taggers and PERO's line/OCR models. Alternatively, double-click `GET_ASSETS.bat` to download, extract and verify them.

Run inference on your own page images:

```powershell
.\inference\run.bat "C:\pages\page1.jpg" "C:\pages\page2.jpg"
```

The launcher installs the inference environment if needed. With no image arguments it processes scans 40–41. Outputs are in `inference/outputs/`: regions, OCR, semantic labels, labelled images, selected text and a run report.

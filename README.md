# PetrIUS interview submission

| Folder | Contents |
|---|---|
| `task1_min/` | Task I parser, reference labels and evaluation results |
| `inference/` | Neural pipeline, random-page sampler and dependencies |
| `models/` (downloaded separately) | D-FINE, PERO and neural-tagger weights |
| `site/` | Viewer and datasets |
| `tools/` | Model downloader and site validator |
| `docs/` | Submission note, model manifest, image sources and verification records |
| `.github/workflows/` | Viewer deployment |

The Task I submission includes the requested algorithm-based parser and its evaluation. The neural pipeline runs D-FINE region detection, PERO line detection and OCR, and neural classification on other pages with the same layout. [Trained weights](https://github.com/conradcompagna/petrius-interview-2026/releases/download/interview-2026-10-07/assets-models-01.zip) are provided separately. The viewer shows the datasets behind [Notenew.docx](docs/Notenew.docx).

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

## Run the Task I parser and evaluation

Windows 10 or 11:

1. Click **Code → Download ZIP** on this GitHub page, then right-click the ZIP and choose **Extract All**.
2. Open the extracted `petrius-interview-2026-main` folder containing this README; this is the repository folder.
3. [Install Python 3.12](https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe): tick **Add python.exe to PATH**, keep the default options, then click **Install Now**.
4. In the repository folder, open `task1_min` and double-click `run.bat`; wait for it to finish, then press any key when prompted.

The first run installs dependencies and downloads scans 40–41 and their MDZ OCR. Results stay in `task1_min`: `labels_00040.jpg` and `labels_00041.jpg` show the labels, `lines.csv` records them, and `evaluation.json` compares them with `reference.csv`.

## Run the neural pipeline on fresh random pages

Complete steps 1–3 above first.

1. In the repository folder, double-click `GET_ASSETS.bat` to download and install the 490 MB model weights; wait for **Model weights are ready**, then press any key.
2. Double-click `RUN_RANDOM_PAGES.bat`; the first run installs dependencies, then runs the pipeline; wait for the results message.

Each run selects three random pages from ten books with the task layout, excluding the training, evaluation and viewer pages.

Open `inference/outputs`, then the newest `random_` folder: `overlays` contains labelled images, `text` contains extracted text, and `predictions` contains labels and coordinates.

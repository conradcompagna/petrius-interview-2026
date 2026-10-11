# Historical Latin Document Analysis interview submission

## Open the reader

[Open the reader in your browser](https://conradcompagna.github.io/historical-latin-document-analysis/). No download or installation is needed to view it.

Choose a collection from the menu, then a page from the list. Click an outlined region or line to see its label and OCR. The collections contain Task I results, parser comparisons, MDZ OCR samples, stock-model comparisons, D-FINE annotations and held-out results, neural-tagger annotations and held-out results, and full-pipeline results on the two task pages.

## Download and prepare the programs

These steps are for Windows 10 or 11. You do not need to type commands.

1. At the top of this GitHub page, click the green **Code** button, then **Download ZIP**.
2. In your Downloads folder, right-click the downloaded ZIP and select **Extract All**, then **Extract**.
3. Open the extracted folder, then open `historical-latin-document-analysis-main`. You should see this README, `GET_ASSETS.bat`, `RUN_RANDOM_PAGES.bat`, and the folders listed below. This is the main repository folder; run the programs from this extracted copy.
4. [Download the Python 3.12 Windows installer](https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe). Open it, tick **Add python.exe to PATH**, then click **Install Now**. Keep the default options, including the Python launcher. Close the installer when it finishes.

| Folder | Contents |
|---|---|
| `task1_min/` | Task I program, reference labels, labelled page images, line records and confusion matrix |
| `inference/` | Full pipeline, random-page sampler, matching-book list, setup and dependencies; third-party licences are in `licenses/` |
| `site/` | The web reader and its page annotations |
| `tools/` | Model download and site validation scripts |
| `docs/` | [Notenew.docx](docs/Notenew.docx), model download manifest, image sources and verification records |
| `.github/workflows/` | GitHub Pages deployment |

## Run Task I and its evaluation

1. In the main repository folder, open `task1_min`.
2. Double-click `run.bat` (Windows may display the filename as `run`). A console window opens and installs the required software on the first run. Leave it open until the program finishes.
3. The program downloads scans 40–41 and their MDZ OCR, labels the pages, and compares the labels with `reference.csv`. The console displays the confusion matrix and the number of correct labels. Press any key when prompted.
4. Open `labels_00040.jpg` and `labels_00041.jpg` in the same folder to inspect the coloured labels. `evaluation.json` saves the confusion matrix; `lines.csv` saves the line labels and coordinates. `page_00040.json` and `page_00041.json` save the structured page results.

## Download the model weights

1. Return to the main repository folder and double-click `GET_ASSETS.bat`.
2. It downloads the 490 MB model archive, checks it, and extracts it into `models`. Wait until the window says **Model weights are ready**, then press any key to close it.

The archive contains the fine-tuned D-FINE region detector, both neural taggers, and PERO's line and OCR models. To download it manually, [download assets-models-01.zip](https://github.com/conradcompagna/historical-latin-document-analysis/releases/download/interview-2026-10-07/assets-models-01.zip), right-click it and select **Extract All**. Copy the extracted `models` folder into the main repository folder, beside this README.

## Test random pages

1. In the main repository folder, double-click `RUN_RANDOM_PAGES.bat`.
2. The first run installs the inference software. Leave the console window open while it installs and processes the pages.
3. It selects three random pages from the ten matching-layout editions, downloads their original images, and runs D-FINE, PERO and the neural taggers. The known training, evaluation and reader pages are excluded. Each run selects a fresh sample.
4. Open `inference`, then `outputs`, then the newest folder beginning `random_`. Open `overlays` to inspect the labelled images and `text` to read the selected text. `predictions` contains the labels and coordinates; `pagexml` contains the OCR. `random_sample.json` records the books, scans, source links and random seed; `run_report.json` records the results.

## Test your own page images

1. Save your page images as JPG or PNG files.
2. Open `inference` in the main repository folder and locate `run.bat`.
3. In another File Explorer window, select your page images and drag them onto that `run.bat` file. This runs the full pipeline on those images. Double-clicking `run.bat` without dragging images onto it processes the two assigned task pages.
4. Wait for the results message, then open `inference/outputs`. Labelled images are in `overlays`, selected text in `text`, and structured results in `predictions`.

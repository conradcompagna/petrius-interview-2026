# PetrIUS interview package

**For the advance written submission, download `Task_I_written_submission.zip`.** It contains the completed small program, reference labels, coloured overlays, confusion matrix, detailed outputs, MDZ addresses and two-page note. Task II is a separate document.

The source archive contains the complete viewer, Task I program, model inference code, two-page note, fifteen-minute slide deck and speaking script. The viewer includes all 67 collections and 4,093 page records; it loads page images directly from the libraries. Earlier experiments sit in a collapsed menu.

**Inspect the work:** extract the source archive, install Python 3.12 and open `RUN_VIEWER.bat`. The viewer requires no model download. Open `task1_min/run.bat` to reproduce the assigned two-page solution.

**Run the trained pipeline:** open `inference/run.bat`. It downloads the selected weights, installs the tested CPU environment and processes the two interview pages. The only large release asset is **`assets-models-01.zip`** (490 MB). You can also extract this ZIP into the source folder so `models/` sits beside `README.md`, or run `GET_ASSETS.bat` separately. The downloader uses direct HTTPS for public releases and authenticated GitHub CLI access while this repository is private.

The Task I program reproduces all 131 reference decisions and includes the gutter numbers and woodcut initial. The viewer opens on the finished datasets and results, with earlier experiments in a collapsed menu. The fifteen-minute presentation covers Tasks I, III and IV; Task II is being prepared separately by the author.

`SHA256SUMS.txt` records the release archive hashes. `docs/release_assets.json` records every model-file hash. The author's six optional offline viewer-image ZIPs remain local, with their separate inventory in `docs/offline_assets.json`. All seven locally built archives passed CRC checks and every archived file was verified against its source.

The repository and release remain private. The GitHub Pages viewer is prepared for the author's later public release.

# Task I: the two assigned pages

Install Python 3.12, then double-click **run.bat**. It creates a local environment, installs NumPy and OpenCV, retrieves both images and both hOCR files from MDZ, and writes the coloured overlays, line table, page JSON and confusion matrix. Internet access is needed for the first download; subsequent runs use `cache/`.

The supplied reference contains 131 checks: 60 text, 16 summarium, 7 inscriptio, 6 other and 42 outside the central blocks. The program matches all 131. Conrad personally inspected the two original overlays and verified their labels.

`task1.py` is the submission runner. `task1_baseline.py` preserves the original 162-line stripped version. The completed runner also labels six gutter line numbers and the scan-40 woodcut initial as **other**, excludes two tiny OCR fragments, and saves structured JSON. These seven added objects are listed separately in `evaluation.json`; the original 131-check matrix is unchanged.

Green = text; blue = summarium; purple = inscriptio; red = other. Black rectangles show the central blocks. Gloss remains uncoloured.

## MDZ interfaces

- Image: `https://api.digitale-sammlungen.de/iiif/image/v2/bsb10144443_00040/full/full/0/default.jpg`
- Image: `https://api.digitale-sammlungen.de/iiif/image/v2/bsb10144443_00041/full/full/0/default.jpg`
- hOCR: `https://api.digitale-sammlungen.de/ocr/bsb10144443/40`
- hOCR: `https://api.digitale-sammlungen.de/ocr/bsb10144443/41`

The program uses OCR geometry plus image colour, slant and letter height. It uses no training model and no external reference text. `reference.csv` is read only by the evaluator after predictions have been produced. The woodcut frame and the one gutter number absent from hOCR are recovered from connected ink components.

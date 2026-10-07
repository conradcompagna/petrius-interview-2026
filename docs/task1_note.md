# Task I page layout method and development

Conrad Compagna · PetrIUS Postdoc 4 · 7 October 2026

## The two interview pages

The submitted program retrieves scans 40 and 41 of the 1582 Roman Decretals, MDZ object bsb10144443, together with their hOCR. It separates the decretal blocks from the surrounding gloss and labels their lines as text, summarium, inscriptio or other. The core program reproduces all 131 reference decisions correctly. I checked both labelled page images personally. The package contains the source, colour overlays, line records and a reproducible confusion matrix.

The method is deliberately small. OpenCV and NumPy measure the share of red ink, the slant of the letters and their height relative to the commonest type on the page. Large black lines locate the block in each half of the page; the block is extended over neighbouring chapter openings. Inside it, red material is other, slanted type is summarium, large type is text and the remaining small roman type is inscriptio. OCR lines crossing the gutter are split by column. Recognition supplies the words and coordinates; the labels come from the image. No training, reference-text alignment or language-model call is needed.

| Reference / program | text | summarium | inscriptio | other | outside |
|---|---:|---:|---:|---:|---:|
| text | 60 | 0 | 0 | 0 | 0 |
| summarium | 0 | 16 | 0 | 0 | 0 |
| inscriptio | 0 | 0 | 7 | 0 | 0 |
| other | 0 | 0 | 0 | 6 | 0 |
| outside | 0 | 0 | 0 | 0 | 42 |

Outside means a line correctly excluded from the decretal block. The completed overlay also marks six gutter line numbers and the woodcut initial as other; the two junk OCR fragments are excluded. These objects are recorded separately from the 131-line matrix.

## Errors and the reason for changing architecture

On these two pages the main decisions are correct. The small program exposes specific dependencies: it takes line geometry from MDZ, measures type size from connected ink components and uses the edition's red and italic type as cues. Removing adaptive binarisation caused 23 errors; removing block extension caused 13; admitting lines extending beyond the block caused 22. These experiments identify the image processing that matters and remove machinery that does not improve the answer.

Hand-written layout rules are not a viable corpus-wide solution. Other editions move the gloss, interrupt the body with commentary, lose red ink in reproduction and distinguish textual roles without italic type. A rule that works because a summarium is slanted cannot identify the equivalent passage in Gothic type. Neural region detection and contextual line classification are the correct architecture for this larger task. I have built and tested those components, with their training data, weights and inference code included in the accompanying software.

<!-- PAGEBREAK -->

## Scaling the working models

The extended pipeline runs D-FINE to find text regions, PERO to detect and recognise their lines, and a neural classifier to identify central regions and label lines in page context. The region detector has a 120-page dataset: 100 training pages from 20 books and 20 evaluation pages from 20 other books. It identifies 206 of 240 reference regions at an intersection-over-union threshold of 0.50, with 32 extra detections, giving region F1 0.862. The line-classification dataset contains 100 training and 20 evaluation pages from ten books. Its v3 model combines colour line images, OCR characters, coordinates and a page-level transformer, achieving four-role macro-F1 0.945 on the 20 evaluation pages. The viewer exposes these results page by page.

The remaining work is concrete: tighten region boundaries, recover missed small marginal regions, resolve short inscriptiones, and represent lines that contain more than one textual role. A wrong region boundary can join two arguments before classification begins. The viewer therefore keeps the image, region, line and text together, so each error can be corrected at its source and reused in training.

For thousands of pages I would acquire and cache images and OCR with stable library identifiers, process them in resumable batches, and export coordinates, text and labels with source links. Training and evaluation would be separated by book and layout family. Historians would define the paratext categories and correct selected complete pages; repeated errors would determine the next annotation batch. The existing acquisition layer already inventories 100 volumes and supports a frozen 1,000-page sample.

## Gothic Roman and Greek type

Gothic and earlier Roman editions need examples of their own type, abbreviation and layout systems. I would extend both datasets with complete pages from those editions, including chapter openings, mixed layouts and small marginal matter. Recognition would be trained or adapted on line images paired with transcriptions; the line classifier would continue to use visual appearance and page context as well as OCR. Greek passages require Greek transcription examples and a recogniser character inventory that retains Greek letters. The task is to preserve the passage, its reading order and its relationship to the legal text, then classify its function.

## Tools and how the work was built

I used Claude and Codex as coding agents to write and revise code, run experiments, investigate failures and draft documentation. ChatGPT generated synthetic region and line annotations from the page images; I reviewed the annotations and personally verify the submission. I directed the research, chose the experiments, rejected failed approaches and selected the resulting systems. The delivered inference uses OpenCV, NumPy, PyTorch, D-FINE and PERO; it requires no LLM service or API key.

Between 1 and 6 October, this produced more than 26,000 lines of project code across more than 200 files, a 100-volume acquisition layer, annotation and comparison software, two 120-page datasets, a trained region detector and three successive neural line classifiers. Kraken, Surya, PaddleOCR, Eynollah and other alternatives were tested and displaced where they failed the page-level requirements. LLM agents made that experimental breadth possible for one researcher in six days. Skilled use of these tools is a major practical advantage in research speed and scope.

## MDZ interfaces

Images: https://api.digitale-sammlungen.de/iiif/image/v2/bsb10144443_00040/full/full/0/default.jpg and the corresponding 00041 address. OCR: https://api.digitale-sammlungen.de/ocr/bsb10144443/40 and /41. The complete manifest, exact addresses, source acknowledgements and commands are in docs/SOURCES.md and the package README.

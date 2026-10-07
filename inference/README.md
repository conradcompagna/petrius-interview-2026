# Run the trained pipeline

Install **Python 3.12** and double-click **run.bat**. It downloads the selected model weights when needed, installs the tested CPU runtime, downloads the two assigned MDZ pages and runs D-FINE → PERO → neural v3. While the repository is private, automatic model downloads use GitHub CLI signed into an account with repository access. After public release, the download works directly over HTTPS. No API keys or paid services are used for inference.

The pipeline writes its results to `outputs/`:

- `predictions/`: regions, OCR lines, text, semantic labels and confidence in JSON;
- `overlays/`: coloured page images;
- `pagexml/`: PERO text and geometry in PAGE XML;
- `text/`: selected central-block text;
- `regions/`, `ocr/`, `raw_labels/`: the output of each individual stage;
- `run_report.json`: completion and processing time for each page.

The viewer in the submission already contains the completed interview pages and both sets of evaluation results. Running inference creates a separate result folder.

## Process another image

From this folder, run:

```bat
run.bat "C:\path\page.jpg"
run.bat "C:\path\page1.jpg" "C:\path\page2.jpg"
```

Or use Python directly:

```bat
.venv\Scripts\python.exe run.py --device cpu --out outputs_custom "C:\path\page.jpg"
```

The default run uses the CPU and works without a graphics card. For a machine with a supported NVIDIA graphics card, install the matching CUDA-enabled PyTorch build in the same environment and use `--device cuda`. `--device auto` selects CUDA when available and otherwise selects the CPU.

## What is running

1. **D-FINE Large, epoch 14 / step 1400**, fine-tuned on the project's region annotations, finds text regions directly from the page image.
2. **PERO ParseNet** finds lines inside those predicted regions; **PERO OCR** reads a crop masked to each parent region.
3. **Neural v3** removes duplicate region detections, selects the central text blocks, and labels their lines as text, summarium, inscriptio or other.

The classifier receives colour image strips, raw OCR characters and page-relative coordinates. Its two transformers use the included `neural_v3.pt` checkpoint. The inference code does not train a model and does not use reference labels. The saved evaluation collection reproduces the scored experiment with annotated duplicates removed; inference on new pages applies the automatic duplicate-region rule in `neural/extract.py`.

`requirements.txt` pins the principal packages; `setup.bat` installs the complete tested CPU environment from `requirements-lock-cpu.txt`. All model hashes are checked before inference. Source code for the project's neural architecture, image preparation and prediction is in `neural/`.

The fresh CPU run processed scan 40 in 43 seconds and scan 41 in 28 seconds on the development laptop. `verification.json` records the successful run and its output checks.

## Attribution

- D-FINE document-layout integration: [dfine-kraken](https://pypi.org/project/dfine-kraken/0.4.3/), Apache 2.0.
- Initial D-FINE Large LADaS weights: [Benjamin Kiessling, Zenodo 18715364](https://zenodo.org/records/18715364), Apache 2.0.
- PERO: [DCGM/pero-ocr](https://github.com/DCGM/pero-ocr), BSD 3-Clause code; pretrained ParseNet and OCR files from the [authors' model distribution](https://nextcloud.fit.vutbr.cz/s/NtAbHTNkZFpapdJ).

The bundled licence texts are in `licenses/`; selected model files, sizes and SHA-256 hashes are in `../models/manifest.json`.

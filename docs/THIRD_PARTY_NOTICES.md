# Third party software and model notices

The submission combines project code written for this application with the following upstream systems. Their licence texts and model provenance remain with the relevant components.

| Component | Source | Role |
|---|---|---|
| OpenCV | https://github.com/opencv/opencv | Image processing in the small task solution |
| NumPy | https://github.com/numpy/numpy | Numerical arrays and measurements |
| PyTorch | https://github.com/pytorch/pytorch | Neural inference and training |
| D-FINE | https://github.com/Peterande/D-FINE | Neural object detector architecture |
| D-FINE Kraken integration | https://pypi.org/project/dfine-kraken/ | Historical-document region detector integration |
| PERO OCR | https://github.com/DCGM/pero-ocr | Line detection and recognition |

PERO source commit used during development: `4301bdffe9205dff11579dae27b3f80458c27e89`. The initial PERO model bundle is `pero_eu_cz_print_newspapers_2022-09-26`, containing `ParseNet_296000.pt` and `OCR_350000.pt`. The project D-FINE weights are the selected epoch-14 checkpoint; the neural region and line classifiers are the project's v3 models. Exact file hashes accompany the packaged weights.

The original PERO BSD 3-Clause licence is reproduced in `legal/PERO_LICENSE.txt`; the D-FINE Kraken integration is Apache-2.0, reproduced in `legal/DFINE_KRAKEN_LICENSE.txt`. Additional package-specific notices are supplied with the inference code. Image sources and their rights statements are documented separately in [SOURCES.md](SOURCES.md).

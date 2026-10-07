# Interview task checklist

## Written submission due 12 October 2026

| Requirement | File or entry point |
|---|---|
| Retrieve images and OCR for scans 40 and 41 | `task1_min/task1.py` |
| Separate decretal blocks and classify their lines | `task1_min/task1.py` |
| Supply the exact MDZ interfaces | `docs/SOURCES.md` |
| Supply two colour overlays | `task1_min/labels_00040.jpg`, `task1_min/labels_00041.jpg` |
| Evaluate the labels | Matrix and evaluation outputs in `task1_min/` |
| Explain errors, scaling, Gothic, Roman and Greek | Two-page `docs/task1_note.pdf` |
| Disclose tools and language models | Note and root README |
| Provide a literature comment of at most two pages | Task II supplied separately by the author |

## Oral presentation on 20 October 2026

Three five-minute sections are in `presentation/`: Task I results; Task III workflow for variants and changed attributions; Task IV pilot, historian annotation, methods, measures and publication plan for December 2026 to May 2027.

## Supporting software

- `RUN_VIEWER.bat`: inspect training data and final outputs.
- `task1_min/run.bat`: reproduce the small task solution.
- `inference/setup.bat` and `inference/run.bat`: install and run the larger trained pipeline.
- `models/`: selected trained weights and provenance.

The author personally verifies the submission before it is sent. Task II remains a separate author-supplied document.

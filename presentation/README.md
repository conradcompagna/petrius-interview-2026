# PetrIUS interview presentation

Open **PetrIUS_Interview_15min.pptx** in PowerPoint. The PDF contains the same slides.

- Slides 1–5: **Task I**, five minutes.
- Slides 6–10: **Task III**, five minutes.
- Slides 11–15: **Task IV**, five minutes.
- Slides 16–18: supporting material for questions.

Each main slide has its complete script in the PowerPoint speaker notes. `SPEAKER_SCRIPT.md` provides the same text with a minute-by-minute schedule. The speaking allocation is 60 seconds per slide, including time to point to the evidence. The 15 main slides total 15 minutes.

Text, diagrams, tables, bars and the schedule are editable PowerPoint objects. The historic page images and their evidence crops are embedded. `rendered/` contains images of every slide and three contact sheets from the PowerPoint PDF export.

## Rebuild

Install Node.js, then run these commands in this folder:

```text
npm install
node build_presentation.js
```

The builder uses `assets/`, `asset_sizes.json` and `metrics.json`. It writes the PPTX, speaker script and slide manifest. PowerPoint can export the PPTX as PDF; `render_and_verify.py` automates that export on Windows and checks the resulting file:

```text
python -m pip install pymupdf pillow reportlab
python render_and_verify.py
```

`SOURCES.md` identifies the evidence behind each result and the source images. The Task III workflow and Task IV pilot are presented as proposed research designs. The two-page minimal task result, D-FINE evaluation and neural v3 evaluation are shown separately.

# PetrIUS interview — 15-minute speaker script

Conrad Compagna · Prepared 7 October 2026 · Interview 20 October 2026

Three separate five-minute presentations. Slides 1–5: Task I; slides 6–10: Task III; slides 11–15: Task IV. Each slide has a 60-second speaking allocation, including a short pause to point to its visual. Appendix slides are for questions and do not enter the 15 minutes.

## 00:00–01:00 · Task I · Slide 1

**The two-page task: 131 / 131 correct**

My starting point is the assignment itself: these two pages of the Roman Decretals. The submitted minimal program retrieves both images and both hOCR files directly from MDZ, finds the central text blocks, assigns the four requested roles, and produces these colour overlays together with the evaluation. It scores 131 out of 131 against the reference, and I personally inspected both page overlays. The colours separate legal text, summaria, inscriptiones and other material. The surrounding gloss remains outside the selected blocks. The implementation needs only OpenCV and NumPy. I have included this small program because the committee should be able to run and inspect the actual task solution immediately.

## 01:00–02:00 · Task I · Slide 2

**A small rule system is sufficient for this edition**

There are three measurements: red ink, slant, and letter height relative to the page's usual type. Large black lines establish the central blocks. The program extends each block upwards and downwards to include its chapter heads, and rejects lines extending into the gloss. Red material becomes other; slanted type becomes summarium; large type becomes text; the remaining small type becomes inscriptio. It uses the library's word and line geometry, splitting the five OCR lines that cross the gutter. The matrix contains sixty text labels, sixteen summaria, seven inscriptiones, six other labels, and forty-two outside controls. All are correct. The completed program also labels six gutter numbers and the woodcut initial, and rejects two junk OCR fragments. This solves the specified pages with a compact, inspectable implementation.

## 02:00–03:00 · Task I · Slide 3

**Across editions, use learned page and line models**

The cross-edition solution is a neural pipeline. Fixed rules depend on the relationship between text size, gloss size, spacing and position in one edition. Those relationships change between printers and typefaces. I therefore trained D-FINE to find the regions, constrained PERO to find and recognise lines within those regions, and trained a neural model to select the central blocks and assign line roles. The line model combines colour image strips, OCR characters, coordinates and the other lines on the page. The two training collections each contain one hundred training pages and twenty evaluation pages. This image shows the combined pipeline on an original interview page. The package contains its model weights, inference code and a viewer for inspecting the results.

## 03:00–04:00 · Task I · Slide 4

**The trained systems have measurable results**

These results identify what each stage accomplishes and what to improve next. The region detector reaches an F1 score of 0.862 at fifty percent overlap on twenty pages from twenty books outside its training books. That represents 206 matched regions, thirty-two extra detections and thirty-four missed regions. The neural role model reaches macro-F1 of 0.945 on its twenty evaluation pages. Its text and summarium F1 scores are approximately ninety-nine percent; inscriptio and other are approximately ninety percent. There are fourteen label errors among 5,065 supplied lines. The practical next steps are clear: improve small source labels, chapter apparatus and region boundaries, then extend the labelled examples to Gothic and mixed-script material.

## 04:00–05:00 · Task I · Slide 5

**Six days: a complete experimental environment**

I used LLM agents extensively, and that is central to how this work was done. In six days I developed an acquisition layer for a hundred volumes, more than twenty-six thousand source lines across more than two hundred files, a review viewer, labelled training collections, a trained region detector and three generations of neural classifiers. Multiple candidate systems were tested and rejected. Claude and Codex implemented code, ran experiments and investigated failures under my direction. ChatGPT generated the training annotations, which I reviewed. I set the questions, judged the results and personally check the submission. This is a modern research workflow: it gives one researcher the implementation capacity and experimental breadth that previously demanded a much larger effort.

## 05:00–06:00 · Task III · Slide 6

**The same divisio; a different attribution**

The supplied example makes the historical objective concrete. These are crops of the complete divisio in the left column of each image. In 1490 the text names Jacobus de Arena and ends with Bartolus. In 1627 it retains only Bartolus. We need a system that retrieves these two units, recognises them as versions of the same paratext, and records the loss of an attribution. The abbreviation Bar and the abbreviation B should resolve to the same person. Jac de arena must remain a separate attribution that can disappear. This is why a single fuzzy text similarity score is insufficient. The workflow must distinguish variation in written form from changes in the information communicated by the paratext.

## 06:00–07:00 · Task III · Slide 7

**Retrieve the legal locus, then recover its paratext**

I begin with an edition-independent legal identifier, here D.1.1.1pr. I retrieve the corresponding passage using the OCR, book and title headings, incipits, and RapidFuzz for character-level fuzzy matching. This gives a local search area even when spelling and abbreviations differ. Within that area, the page model identifies the text streams. A unit classifier uses the lemma, position and neighbouring material to attach the divisio to the fragment. It assembles a complete unit across lines and, where needed, across page breaks. Each result receives a stable key combining edition, legal locus, paratext type and occurrence. The record retains the original image coordinates and raw OCR, so every later comparison can be checked against the actual witness.

## 07:00–08:00 · Task III · Slide 8

**Compare wording and historical content separately**

I keep a diplomatic layer and derive two representations from it. The matching layer handles spelling variation, long s, u and v, and alternative abbreviation expansions. Character n-grams retrieve candidates; CollateX then exposes correspondences in a multiple-witness alignment. The content layer records named authorities, citations, negation, conditions and exceptions. A controlled authority list resolves Bar and B to Bartolus, while retaining the printed forms and locations. Candidate units are grouped through aligned similarity and shared legal locus, then checked for conflicting content fields before they become a variant group. Crucially, normalisation never deletes an author or a qualification. A name disappearing is therefore an event to inspect, rather than noise that a high similarity score silently removes.

## 08:00–09:00 · Task III · Slide 9

**Make the change an explicit, inspectable record**

This is the structured result I want. The 1490 authority set contains Jacobus de Arena and Bartolus; the 1627 set contains Bartolus. Alignment links the shared division of the passage, so the remaining difference becomes an attribution-removal event with an edition, a locus and a paratext type. The record stores both excerpts, the exact source spans and the reason for the flag. The same mechanism can flag a lost exception, a changed negation or an added legal reference. It does not equate every textual difference with a doctrinal difference. Historians assign the interpretation in the review interface. The computer's contribution is systematic detection and comparison of these events across thousands of corresponding units.

## 09:00–10:00 · Task III · Slide 10

**Return evidence to historians—and patterns to research**

Historians see the two images, aligned diplomatic text, the resolved names and the proposed event side by side. They can confirm, correct and export a citable evidence record. The main risk is precise: a name missed by OCR can masquerade as a historical deletion. A missing-name flag therefore triggers inspection of the complete source unit, with targeted re-recognition or transcription of the disputed span. The unit boundary is checked too, because an attribution may sit on another line. Once events are confirmed, the analysis asks where, when and in which editorial families attribution disappears. That produces a corpus-wide history of editorial selection, while allowing every aggregate pattern to be traced back to its printed evidence.

## 10:00–11:00 · Task IV · Slide 11

**A 360-page pilot across six editions**

I would start with three hundred and sixty complete pages: sixty from each of these six editions. The four Digest witnesses give a sequence from Gothic print in 1490 through Roman editions to 1627, including a witness with Greek notes. The two Decretals editions connect the task's successful Roman example to an earlier Gothic edition. I would select forty matched Digest loci across four witnesses and twenty Decretals loci across two, giving two hundred paratext witness units for direct comparison. The remaining page coverage supplies difficult layouts and continuation cases. The split is two hundred and forty training pages, sixty development pages and sixty sealed test pages. Adjacent pages of one sampled passage stay together in the same split.

## 11:00–12:00 · Task IV · Slide 12

**Historians define the units and the distinctions**

I need three kinds of historian input. First, page structure: the text streams, their reading order and where they continue. Second, unit identity: the legal locus, the paratext type and the exact boundaries of the unit. Third, text and meaning: difficult abbreviation readings, names, citations and whether a difference changes an attribution, condition or exception. We begin with a twelve-page calibration workshop covering all six editions. I prefill annotations with the existing models; historians correct them in the viewer and discuss disagreements in a short weekly clinic. Their decisions become examples in a living annotation guide. Sixty focal paratext units receive two independent readings and an adjudication, creating a focused reference for the historical event detection.

## 12:00–13:00 · Task IV · Slide 13

**Six months, with a usable result at each stage**

December fixes the corpus, source terms and annotation guide. January produces a checked pilot dataset and a first retrained region and role pipeline. OCR work begins alongside it, concentrating on the Gothic and Greek examples and the fields needed for historical comparison. February and March develop legal-locus alignment and complete paratext assembly, including continuations. By the end of March, a historian can move from a locus to its corresponding units in the pilot editions. April adds variant grouping and attribution-change detection, reviewed in the comparison desk. May runs the sealed evaluation, packages the reproducible release and produces the first matched-locus study. Each stage ends in an inspectable artifact, so progress is measured by usable data and demonstrated operations.

## 13:00–14:00 · Task IV · Slide 14

**Success means recovering the historical evidence**

I would measure success at the points where errors affect the research. The pilot targets are region F1 of at least point nine and role macro-F1 of at least point nine five. For OCR, the key test is recovery of the names and citations used in comparisons, with ninety-five percent exact recovery as the target. Legal-locus linking and variant grouping receive their own reference sets. Attribution and qualification events are judged for both precision and recall: we need to know which changes were invented and which were missed. Results are broken down by edition, typeface and class. Finally, I compare timed manual work with assisted correction of comparable units, targeting a reduction of at least half in median correction time.

## 14:00–15:00 · Task IV · Slide 15

**Publish a reusable corpus and an answerable question**

The release separates code, models, annotations and library images. GitHub carries the implementation, launch scripts, annotation guide and evaluation protocol. A versioned model and dataset release carries weights and the annotations we can distribute. Every item retains its library identifier, source address and terms. Retrieval scripts reproduce image acquisition; image redistribution follows the recorded terms of each holding institution. The first historical output is a matched-locus study of attribution: which names survive, disappear or move between paratextual layers across the pilot editions. Scaling that design reveals patterns that individual reading cannot assemble systematically. The deliverable is therefore both a reusable research instrument and a concrete investigation, with each computational result linked back to the witnesses.


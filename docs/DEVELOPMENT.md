# Development scope and LLM use

The core research and engineering programme was built during **1–6 October 2026**. The interview packaging was assembled on 7 October.

| Date | Development milestone |
|---|---|
| 1 October | Initial parser and package for the 1582 Decretals |
| 2 October | 100-volume inventory, cross-book inference and annotation infrastructure |
| 3 October | Cross-edition parser revision and layout-family comparison |
| 4 October | Kraken failure investigation and D-FINE region training |
| 5 October | Annotation datasets and neural line-classifier development |
| 6 October | Further neural training, repository audit and library OCR investigation |

The project source inventory records more than **26,000 lines across more than 200 Python files**. The exact current count and file list are in `development_source_inventory.json`. It counts the project's own source directories and excludes environments, cloned dependencies, model weights, page images, generated outputs and working caches. The browser viewer also contains JavaScript, HTML and CSS.

The work covers library acquisition, metadata and page sampling, image processing, region segmentation, line detection, OCR, annotation preparation, annotation review, model training, inference, evaluation, visualization and research design. Several competing document-analysis models were tested. Three versions of the neural classifier were implemented and compared. Two 120-page datasets support region detection and semantic line classification.

I used Claude and Codex as coding agents under my direction. They wrote and revised code, ran experiments, investigated faults and drafted documentation. ChatGPT generated region and line annotations from historical page images. Those generated annotations are the synthetic training resource: the source pages themselves are library scans. I reviewed the annotations and personally verify the submission. I set the research objectives, chose the experiments, interpreted the results and selected the systems to retain.

The practical result is an experimental breadth that one researcher could not produce manually in six days. LLM agents make it feasible to build competing implementations, compare them on the actual sources and discard unsuccessful approaches quickly. Their value is visible in the completed software, datasets, model weights and experiments in this package.

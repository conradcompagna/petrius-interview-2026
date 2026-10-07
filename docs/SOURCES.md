# Source interfaces and acknowledgements

## Interview pages

Decretales D Gregorii Papae IX, Rome 1582. Bayerische Staatsbibliothek, digital object **bsb10144443**, scans **40** and **41**.

| Resource | Address |
|---|---|
| IIIF presentation manifest | https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb10144443/manifest |
| Scan 40 image | https://api.digitale-sammlungen.de/iiif/image/v2/bsb10144443_00040/full/full/0/default.jpg |
| Scan 41 image | https://api.digitale-sammlungen.de/iiif/image/v2/bsb10144443_00041/full/full/0/default.jpg |
| Scan 40 OCR | https://api.digitale-sammlungen.de/ocr/bsb10144443/40 |
| Scan 41 OCR | https://api.digitale-sammlungen.de/ocr/bsb10144443/41 |
| Library object | https://www.digitale-sammlungen.de/en/view/bsb10144443 |

The hOCR contains words, line groupings and bounding boxes. The program retrieves it directly and caches the original files beside the images. The original task-page images and outputs retain the scan identifiers throughout.

## Image credit and rights metadata

Credit: **München, Bayerische Staatsbibliothek**. The saved IIIF manifest for bsb10144443 declares https://rightsstatements.org/vocab/NoC-NC/1.0/ as its rights statement. The page and collection manifests retain the source URLs and identifiers for the other books.

`library_rights_inventory.json` records the rights and attribution fields from 184 acquisition manifests, with their source URLs and file hashes. It distinguishes library metadata from the locally prepared LMU acquisition record.

The software licence does not replace any library's image terms. A public corpus release will distribute code, annotations, model documentation and source manifests, with image redistribution decided from each library's terms. Source links and download scripts preserve reproducibility when images are distributed by the library itself.

## Source records in this package

The viewer's page records identify the book, scan, source image and annotation or model output. The model package records the selected weights and configuration. The evaluation folders contain page-level predictions and scores, so individual cases can be inspected in the viewer.

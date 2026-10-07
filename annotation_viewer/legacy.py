"""Read the original PetrIUS outputs without importing or running its classifier."""
import json


def review_index(path):
    # The original HTML embeds JSON; parse only that value, never execute its JS.
    source = path.read_text(encoding='utf-8')
    pages, _ = json.JSONDecoder().raw_decode(source.split('const P=', 1)[1])
    return pages


def original_point(affine, x, y):
    (a, b, c), (d, e, f) = affine
    determinant = a * e - b * d
    if abs(determinant) < 1e-12:
        raise ValueError('Singular original-book page transform')
    return [(e * (x-c) - b * (y-f)) / determinant,
            (-d * (x-c) + a * (y-f)) / determinant]


def geometry(affine, box):
    x0, y0, x1, y1 = box
    polygon = [original_point(affine, x, y) for x, y in [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]]
    return dict(polygon=polygon, bbox=[min(p[0] for p in polygon), min(p[1] for p in polygon),
                                     max(p[0] for p in polygon), max(p[1] for p in polygon)])


def candidates(record):
    for column in ('L', 'R'):
        rows = sorted((r for r in record['lines'] if r['column'] == column), key=lambda r: r['baseline'])
        for index, row in enumerate(rows, 1):
            yield f'{column}{index}', row


def adapt(record, review=None):
    """Undo the stored deskew/shear on every geometry, retaining saved labels/text."""
    affine = record['affine']
    regions, lines, objects, warnings = [], [], [], []
    for index, block in enumerate(record['blocks'], 1):
        regions.append(dict(id=f'block_{block["column"]}_{index}', label='main_text',
            **geometry(affine, block['bbox']), review_status='automatic_original_parser_block',
            geometry_review_status='original_parser_box_mapped_to_source_scan',
            counts_as_task_unit=False, note='Original parser block outline, provided as context for the line labels.'))
    if review is None:
        selected = list(candidates(record))
    else:
        selected = [(r['id'], r) for r in review['lines']]
        for addition in review.get('added', []):
            warnings.append(f'Review records a missed {addition["label"]} line in column {addition["column"]}, '
                            f'after {addition.get("after", "unspecified")}; no boundary was saved, so no overlay is invented.')
    for uid, row in selected:
        label = row['label'] if review is not None or row.get('in_block') else 'outside'
        reviewed = review is not None and review.get('reviewed', False)
        note = ('Saved original review label; parser-derived and AI-reviewed, not independent human gold.' if reviewed else
                'Saved original review draft; this page has no recorded review.' if review is not None else
                'Saved original classifier output. Outside means excluded from its primary-text block, not an exhaustive gloss annotation.')
        if review is not None and 'draft' in row and row['draft'] != row['label']:
            note += f' Review changed the draft label from {row.get("draft", "unknown")} to {row["label"]}.'
        note += ' OCR is the original MDZ text attached by the original parser; it was not rerun.'
        x0, _, x1, _ = row['bbox']
        lines.append(dict(id=uid, label=label, text=row.get('text', ''), **geometry(affine, row['bbox']),
            baseline=[original_point(affine, x0, row['baseline']), original_point(affine, x1, row['baseline'])],
            review_status='ai_reviewed_silver' if reviewed else 'unreviewed_review_draft' if review is not None else 'unreviewed_prediction',
            geometry_review_status='original_parser_box_mapped_to_source_scan',
            classification_score=row.get('conf') if review is None and row.get('in_block') else None,
            note=note))
    # These elements were drawn in the original review images, but their types
    # were not part of the review's editable line-label table.
    for index, element in enumerate(record['elements'], 1):
        objects.append(dict(id=f'element_{index}', label='other', **geometry(affine, element['bbox']),
            review_status='unreviewed_structural_prediction', geometry_review_status='original_parser_box_mapped_to_source_scan',
            note=f'Original automatically detected {element["kind"]} in column {element["column"]}; not a reviewed line label.'))
    return dict(regions=regions, lines=lines, structural_units=objects, warnings=warnings,
                semantic_labels_assigned=True)

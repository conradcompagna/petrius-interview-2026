"""Display canonical region JSON and saved PAGE baselines without running a model."""
import xml.etree.ElementTree as ET

NS = {'p': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15'}


def points(element):
    if element is None:
        return []
    return [[float(n) for n in pair.split(',')] for pair in element.attrib['points'].split()]


def adapt(record, xml_path):
    page = ET.parse(xml_path).getroot().find('p:Page', NS)
    image = record['image']
    if (int(page.attrib['imageWidth']), int(page.attrib['imageHeight'])) != (image['width'], image['height']):
        raise ValueError('PAGE dimensions differ from annotation image')
    overrides = {o.get('id') or o.get('source_id'): o for o in record['line_overrides']}
    regions = [dict(r, label='text_region', review_status='model_assisted_not_human_adjudicated',
                    geometry_review_status='imported_original_image_pixels') for r in record['regions']]
    by_id = {r['id']: r for r in regions}
    lines, warnings = [], []
    for region in page.findall('p:TextRegion', NS):
        rid = region.attrib['id']
        unassigned = 'type:Unassigned;' in region.get('custom', '')
        if not unassigned and (rid not in by_id or points(region.find('p:Coords', NS)) != by_id[rid]['polygon']):
            raise ValueError('PAGE region differs from canonical JSON')
        # Unassigned is a serialization wrapper, not an annotated region.
        for line in region.findall('p:TextLine', NS):
            uid = line.attrib['id']
            original_id = uid.removeprefix('L_')
            override = overrides.get(original_id)
            if override and override['action'] == 'delete':
                raise ValueError('Deleted line remains in PAGE export')
            note = override['reason'] if override else 'Retained original Kraken line geometry; not independently corrected.'
            if unassigned:
                note += ' The PAGE export leaves this baseline unassigned to an annotated region.'
            lines.append(dict(id=uid, label='unassigned' if unassigned else 'text_line',
                polygon=points(line.find('p:Coords', NS)), baseline=points(line.find('p:Baseline', NS)),
                region_ids=[] if unassigned else [rid], note=note + ' No OCR transcription is included in this export.',
                review_status='model_assisted_line_override' if override else 'unreviewed_kraken_baseline',
                geometry_review_status='imported_PAGE_geometry',
                subtype=override['action'] if override else 'retained'))
    for region in regions:
        region['line_ids'] = [line['id'] for line in lines if region['id'] in line['region_ids']]
    unassigned_count = sum(line['label'] == 'unassigned' for line in lines)
    if unassigned_count:
        warnings.append(f'{unassigned_count} exported baseline(s) are unassigned to a region; the staging wrapper is not displayed as a text region.')
    if record['annotation_status'] == 'partial':
        warnings.append('Partial region annotation: ' + record.get('notes', ''))
    return dict(regions=regions, lines=lines, warnings=warnings, notes=record.get('notes', ''),
                annotation_status=record['annotation_status'], semantic_labels_assigned=False)

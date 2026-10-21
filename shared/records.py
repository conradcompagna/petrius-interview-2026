def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, 'detach'):
        return value.detach().cpu().tolist()
    if hasattr(value, 'tolist'):
        return value.tolist()
    return value

def unit(index, polygon, score, label, order):
    polygon = [[float(x), float(y)] for x, y in polygon]
    return dict(id=f'detection_{index:04d}', polygon=polygon,
                bbox=[min(p[0] for p in polygon), min(p[1] for p in polygon),
                      max(p[0] for p in polygon), max(p[1] for p in polygon)],
                label=label, detector_label=label, detection_score=float(score) if score is not None else None,
                reading_order=order, text='', review_status='unreviewed_prediction',
                geometry_review_status='stock_pretrained_detector',
                note='Detection only. No transcription or summarium/inscriptio/text/other task label has been assigned.')

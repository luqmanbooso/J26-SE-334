"""Small, truthful presentation model shared by C3 inspection views."""
from vision_oracle.contracts.v2 import VerdictEnvelopeV2


def _seconds(ms):
    return f"{ms / 1000:.1f}s" if isinstance(ms, (int, float)) else None


def model_lines(metadata, timings):
    """What the model scored and read, stated without overclaiming."""
    lines = []
    p = metadata.get('defect_probability')
    threshold = metadata.get('decision_threshold')
    if isinstance(p, (int, float)):
        line = f'Model defect score: {p:.0%}'
        if isinstance(threshold, (int, float)):
            line += f' (flagged at {threshold:.0%} or above)'
        lines.append(line + '. This is the model\'s own score, not a calibrated probability.')
    model_input = metadata.get('model_input')
    if model_input:
        if metadata.get('hierarchy_used_by_model'):
            lines.append('Model input: screenshot and layout file.')
        elif metadata.get('hierarchy_status') == 'available':
            lines.append('Model input: screenshot only. The layout file is not read by this model; it is used to name the '
                         'affected element and is saved with the evidence.')
        else:
            lines.append('Model input: screenshot only.')
    verdict, localization = _seconds(timings.get('verdict_ms')), _seconds(timings.get('localization_ms'))
    if verdict:
        lines.append(f'Time: decision {verdict}' + (f', defect type and region {localization}' if localization else ''))
    return lines


def present_result(result):
    verdict = VerdictEnvelopeV2.model_validate(result['verdict_v2'])
    data = verdict.model_dump(mode='json')
    handover = verdict.to_c4_verdict().model_dump(mode='json')
    labels = {
        'defect_detected': 'Potential defect detected',
        'no_defect_detected': 'No defect detected',
        'inconclusive': 'Inconclusive',
    }
    decision = data['decision']
    lines = [labels[decision], f"Analysis: {data['analysis_status']}"]
    if decision == 'no_defect_detected':
        lines.append('No finding in the inspected views. This does not certify a defect-free screen.')
    elif decision == 'inconclusive':
        lines.append('The available evidence is insufficient. Review the errors below and retry.')
    lines.extend(model_lines(data['metadata'], data['timings_ms']))
    for index, finding in enumerate(data['findings'], 1):
        lines.extend(['', f"{index}. {finding['type'].replace('_', ' ')}", finding['explanation']])
        confidence = finding.get('confidence')
        method = finding.get('confidence_method', 'unavailable')
        if confidence is None or method == 'unavailable':
            lines.append('Confidence: not calibrated')
        else:
            lines.append(f'Model score: {confidence:.0%} (method: {method})')
        if finding.get('bbox_xyxy'):
            lines.append(f"Region (pixels): {finding['bbox_xyxy']}")
        ref = (data['metadata'].get('element_refs') or {}).get(finding.get('finding_id'))
        if finding.get('element_ref') and ref:
            lines.append(f"Element (matched from layout file, overlap {ref['iou']:.0%}): {finding['element_ref']}")
        elif finding.get('element_ref'):
            lines.append(f"Element: {finding['element_ref']}")
    issues = list(dict.fromkeys(data['errors'] + data['coverage']['warnings']))
    if issues:
        lines += ['', 'Analysis notes:'] + [str(x) for x in issues]
    outcome = handover.get('evidence', {}).get('handover_outcome', 'evidence_only')
    verdict_time = _seconds(data['timings_ms'].get('verdict_ms'))
    localization_time = _seconds(data['timings_ms'].get('localization_ms'))
    return {
        'verdict': data, 'handover': handover, 'title': labels[decision],
        'summary': '\n'.join(lines), 'outcome': outcome,
        'coverage': f"{verdict.coverage.completed_views}/{verdict.coverage.planned_views} views completed",
        'total_ms': verdict.timings_ms.get('total_pipeline_ms'),
        'verdict_time': f'decision {verdict_time}' if verdict_time else None,
        'localization_time': f'type and region {localization_time}' if localization_time else None,
    }

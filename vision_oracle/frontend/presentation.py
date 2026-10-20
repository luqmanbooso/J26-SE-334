"""Small, truthful presentation model shared by C3 inspection views."""
from vision_oracle.contracts.v2 import VerdictEnvelopeV2


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
    for index, finding in enumerate(data['findings'], 1):
        lines.extend(['', f"{index}. {finding['type'].replace('_', ' ')}", finding['explanation']])
        confidence = finding.get('confidence')
        method = finding.get('confidence_method', 'unavailable')
        if confidence is None or method == 'unavailable':
            lines.append('Confidence: not calibrated')
        else:
            lines.append(f'Confidence score: {confidence:.1%} (method: {method})')
        if finding.get('bbox_xyxy'):
            lines.append(f"Region (pixels): {finding['bbox_xyxy']}")
    issues = list(dict.fromkeys(data['errors'] + data['coverage']['warnings']))
    if issues:
        lines += ['', 'Analysis notes:'] + [str(x) for x in issues]
    outcome = handover.get('evidence', {}).get('handover_outcome', 'evidence_only')
    return {
        'verdict': data, 'handover': handover, 'title': labels[decision],
        'summary': '\n'.join(lines), 'outcome': outcome,
        'coverage': f"{verdict.coverage.completed_views}/{verdict.coverage.planned_views} views completed",
        'total_ms': verdict.timings_ms.get('total_pipeline_ms'),
    }

"""CPU-only, strict evidence readers and metrics for the PP1 notebooks."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

RUNS = ['base_v2prompt', 'v1_step246', 'v2_checkpoint-173', 'v2_epoch2']


def load_bundle(folder):
    folder = Path(folder)
    raw = (folder / 'evidence_bundle.json').read_bytes()
    expected = (folder / 'evidence_bundle.sha256').read_text().strip()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Evidence bundle checksum mismatch; rebuild from sources.')
    return json.loads(raw)


def identity(record):
    # Keep the whole path: basenames can collide across sources.
    return record.get('image', record.get('img', '')).replace('\\', '/').casefold()


def aligned(reference, other):
    def index(records):
        ids = [identity(r) for r in records]
        if not all(ids) or len(set(ids)) != len(ids):
            raise ValueError('Missing or duplicate image identity')
        return dict(zip(ids, records))
    a, b = index(reference), index(other)
    if a.keys() != b.keys():
        raise ValueError('Compared runs have different image identities')
    for k in a:
        if (a[k]['gold_has'], a[k]['gold_type']) != (b[k]['gold_has'], b[k]['gold_type']):
            raise ValueError('Gold labels differ between paired runs')
    return [b[k] for k in a]


def binary_metrics(gold, predictions):
    gold, predictions = list(gold), list(predictions)
    if len(gold) != len(predictions) or not gold:
        raise ValueError('Empty or mismatched observations')
    if any(type(x) is not bool for x in gold):
        raise ValueError('Gold labels must be boolean')
    valid = np.array([type(x) is bool for x in predictions])
    y = np.array(gold)
    p = np.array([x if type(x) is bool else False for x in predictions])
    tp, fp = int(sum(valid & y & p)), int(sum(valid & ~y & p))
    fn, tn = int(sum(valid & y & ~p)), int(sum(valid & ~y & ~p))
    # Invalid/abstained outputs stay visible; they never become clean predictions.
    missing_positive = int(sum(~valid & y))
    precision = tp / (tp + fp) if tp + fp else 0.
    recall = tp / (tp + fn + missing_positive) if sum(y) else 0.
    return dict(n=len(y), tp=tp, fp=fp, fn=fn, tn=tn,
                invalid=int(sum(~valid)), coverage=float(valid.mean()),
                accuracy=(tp + tn) / len(y), precision=precision, recall=recall,
                f1=2*precision*recall/(precision+recall) if precision+recall else 0.)


def curves(records):
    if any(type(r['gold_has']) is not bool for r in records):
        raise ValueError('Invalid gold labels')
    y = np.array([r['gold_has'] for r in records])
    s = np.array([r['p_defect'] for r in records], dtype=float)
    if not np.isfinite(s).all() or np.any((s < 0) | (s > 1)) or len(set(y)) != 2:
        raise ValueError('ROC requires finite scores in [0,1] and both classes')
    order = np.argsort(-s, kind='stable')
    y, s = y[order], s[order]
    # Aggregate ties before computing ROC; do not rank tied labels arbitrarily.
    ends = np.r_[np.flatnonzero(np.diff(s)), len(s)-1]
    tp = np.r_[0, np.cumsum(y)[ends]]
    fp = np.r_[0, np.cumsum(~y)[ends]]
    recall, fpr = tp / sum(y), fp / sum(~y)
    precision = np.divide(tp, tp+fp, out=np.ones(len(tp)), where=tp+fp != 0)
    return fpr, recall, precision, float(np.trapezoid(recall, fpr))


def score_table(bundle):
    rows = []
    reference = bundle['benchmarks'][RUNS[0]+'_test316_scores']['records']
    for name in RUNS:
        val = bundle['benchmarks'][name+'_val291_scores']
        test = bundle['benchmarks'][name+'_test316_scores']
        records = aligned(reference, test['records'])
        threshold = val['best_threshold']['threshold']
        curves(records)  # Validate scores before thresholding.
        row = binary_metrics([r['gold_has'] for r in records],
                             [r['p_defect'] >= threshold for r in records])
        row.update(run=name, threshold=threshold, val_auc=curves(val['records'])[3],
                   test_auc=curves(records)[3])
        rows.append(row)
    return pd.DataFrame(rows).set_index('run')


def source(record):
    path = identity(record)
    return 'OwlEye' if 'owleye' in path else ('Rico mutation' if 'mutated' in path else 'Rico clean')


def confusion_plot(ax, metrics, title):
    matrix = np.array([[metrics['tn'], metrics['fp']], [metrics['fn'], metrics['tp']]])
    ax.imshow(matrix, cmap='Blues', vmin=0, vmax=158)
    for (i, j), n in np.ndenumerate(matrix):
        ax.text(j, i, str(n), ha='center', va='center', fontsize=13)
    ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=['clean', 'defect'],
           yticklabels=['clean', 'defect'], xlabel='Prediction', ylabel='Gold', title=title)


def provenance(bundle):
    return pd.DataFrame(bundle['provenance'])[['role', 'source', 'sha256', 'bytes']]

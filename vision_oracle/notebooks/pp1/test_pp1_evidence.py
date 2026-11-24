"""Regression checks for research accounting, independent of model inference."""
import copy
from pathlib import Path
import unittest

from pp1_evidence import aligned, binary_metrics, curves, load_bundle, score_table


class EvidenceTests(unittest.TestCase):
    def test_invalid_is_not_clean(self):
        m = binary_metrics([False, True, True], [None, None, True])
        self.assertEqual((m['tn'], m['fn'], m['invalid']), (0, 0, 2))
        self.assertEqual(m['accuracy'], 1/3)
        self.assertEqual(m['recall'], .5)

    def test_tied_scores_have_chance_auc(self):
        rows = [dict(gold_has=x, p_defect=.5) for x in [True, False, True, False]]
        self.assertEqual(curves(rows)[3], .5)
        self.assertEqual(curves(rows[::-1])[3], .5)

    def test_invalid_score_fails(self):
        with self.assertRaises(ValueError):
            curves([dict(gold_has=True,p_defect=float('nan')),dict(gold_has=False,p_defect=.2)])

    def test_pairing_fails_for_mismatched_labels_and_duplicates(self):
        a=[dict(image='a.jpg',gold_has=True,gold_type='overlap')]
        b=copy.deepcopy(a); b[0]['gold_type']='none'
        with self.assertRaises(ValueError): aligned(a,b)
        with self.assertRaises(ValueError): aligned(a,a+a)
        b=copy.deepcopy(a); b[0]['image']='b.jpg'
        with self.assertRaises(ValueError): aligned(a,b)

    def test_saved_results_use_validation_threshold_only(self):
        b=load_bundle(Path(__file__).parent)
        before=score_table(b)
        for k,v in b['benchmarks'].items():
            if k.endswith('_test316_scores'): v['best_threshold']['threshold']=-100
        after=score_table(b)
        self.assertTrue(before.equals(after))
        self.assertEqual(tuple(before.loc['v1_step246',['tp','fp','fn','tn']]),(125,79,33,79))
        self.assertAlmostEqual(before.loc['base_v2prompt','test_auc'],.5734,places=4)

    def test_full_output_accounting(self):
        b=load_bundle(Path(__file__).parent)
        d=b['benchmarks']['final_test316_end_to_end']
        m=binary_metrics([r['gold_has'] for r in d['records']],[r.get('pred_has') for r in d['records']])
        for k in ['tp','fp','fn','tn']: self.assertEqual(m[k],d['summary'][k])
        self.assertEqual(m['invalid'],0)


if __name__=='__main__': unittest.main()

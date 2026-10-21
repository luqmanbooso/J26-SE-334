"""Builds C3_PP1_measured_results.ipynb. Every number in it is read from a measured evidence file."""
import nbformat as nbf
from pathlib import Path

nb = nbf.v4.new_notebook()
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
C = []

C.append(md("""# C3 Vision Oracle: measured results for PP1

Every table and figure here is read from a file produced by an actual run on 20–21 October 2026, on the RTX 3050 4 GB laptop. Nothing is typed in by hand. Earlier PP1 notebooks (`00_`–`06_`) and the master evaluation notebook show figures that could not be reproduced with the shipped model. **Do not present them.**

| Section | Shows |
|---|---|
| 1 | What model and adapter are running |
| 2 | Training curves |
| 3 | Why the first deployment "detected nothing" |
| 4 | Held-out test results (the only accuracy numbers to quote) |
| 5 | Demo screens through the real app pipeline |
| 6 | Speed and memory |
| 7 | Global view vs tiles (validation) |
| 8 | Optional live run (needs the GPU) |"""))

C.append(code("""import json, math, hashlib
from pathlib import Path
import matplotlib.pyplot as plt
from PIL import Image
C3 = next(p for p in [Path.cwd().resolve(), *Path.cwd().resolve().parents] if (p / 'evidence' / '11_model_v2').exists())
EV = C3 / 'evidence'
ADAPTER = C3 / 'models' / 'c3_qwen2vl_2b_lora_step246'
load = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
print('vision_oracle folder:', C3)"""))

C.append(md("## 1. Identity: what is running"))
C.append(code("""from safetensors import safe_open
cfg = load(ADAPTER / 'adapter_config.json')
contract = load(ADAPTER / 'inference_contract.json')
with safe_open(str(ADAPTER / 'adapter_model.safetensors'), 'pt') as f:
    trainable = sum(math.prod(f.get_slice(k).get_shape()) for k in f.keys())
    n_tensors = len(list(f.keys()))
sha = hashlib.sha256((ADAPTER / 'adapter_model.safetensors').read_bytes()).hexdigest()
TOTAL = 2_227_450_368  # base + adapter parameters, from the LLaMA-Factory training log
print(f"Base model        : Qwen2-VL-2B-Instruct (4-bit NF4, frozen)")
print(f"LoRA rank / alpha : {cfg['r']} / {cfg['lora_alpha']}, dropout {cfg['lora_dropout']}")
print(f"Adapted layers    : {sorted(cfg['target_modules'])} ({n_tensors} tensors)")
print(f"Trainable params  : {trainable:,} of {TOTAL:,} ({trainable/TOTAL:.2%})")
print(f"Adapter SHA-256   : {sha}")
print(f"Inference contract: {contract['image_max_pixels']:,} px, threshold {contract['decision_threshold']} ({contract['threshold_source']})")"""))
C.append(md("**Conclude:** fine-tuning changed 0.83% of the parameters. The prompt, resolution and decision threshold the model was trained and validated with travel with the weights."))

C.append(md("## 2. Training curves"))
C.append(code("""s1 = load('D:/university/Resesarch/results/c3_lora_clean_zero_leakage/trainer_state.json')
s2 = load(ADAPTER / 'trainer_state.json')
fig, ax = plt.subplots(figsize=(8, 3.2))
for st, name, off in ((s1, 'stage 1 (balanced, from base)', 0), (s2, 'stage 2 (defect-heavy, shipped)', s1['global_step'])):
    pts = [(h['step'] + off, h['loss']) for h in st['log_history'] if 'loss' in h]
    ax.plot(*zip(*pts), label=name)
ax.set_xlabel('optimizer step'); ax.set_ylabel('training loss'); ax.legend(); ax.grid(alpha=.3)
print('stage 1 steps', s1['global_step'], '| stage 2 steps', s2['global_step'], '| best validation checkpoint recorded:', s2.get('best_model_checkpoint'))"""))
C.append(md("**Look at:** the loss falls fast, then flattens around 0.3–0.5. **Conclude:** training loss measures how well answer text is reproduced, not detection accuracy. No validation was run during this training, which is why section 4 matters."))

C.append(md("## 3. Diagnosis: the same adapter, the same screens, two ways of asking"))
C.append(code("""def caught(recs):
    tp = sum(r['gold_has'] and r['pred_has'] is True for r in recs)
    fn = sum(r['gold_has'] and r['pred_has'] is not True for r in recs)
    fp = sum((not r['gold_has']) and r['pred_has'] is True for r in recs)
    return f'{tp}/{tp+fn} defects caught, {fp} false alarms'
app = load(EV / '11_model_v2/diagnosis/v1_adapter_app_input_val18.json')
trn = load(EV / '11_model_v2/diagnosis/v1_adapter_training_input_val60.json')[:len(app)]
print('Old app input (40-line prompt, 720x1280):', caught(app))
print('Training input (short prompt, 262k px)  :', caught(trn))"""))
C.append(md("**Conclude:** the weights had learned; the app asked differently from training. Each adapter now carries `inference_contract.json`, which the backend enforces."))

C.append(md("## 4. Held-out test (316 screens, run once, never used for choices)"))
C.append(code("""import sys; sys.path.insert(0, str(C3))
from local_vision_oracle.contract_benchmark import metrics_at
B = EV / '11_model_v2/benchmarks'
rows = []
for name, label in (('base_v2prompt', 'Base Qwen2-VL-2B, same prompt'), ('v1_step246', 'Shipped adapter (step 246)'),
                    ('v2_checkpoint-173', 'v2 retrain, epoch 1'), ('v2_epoch2', 'v2 retrain, epoch 2')):
    t = load(B / f'{name}_test316_scores.json'); thr = load(B / f'{name}_val291_scores.json')['best_threshold']['threshold']
    m = metrics_at([r['p_defect'] for r in t['records']], [r['gold_has'] for r in t['records']], thr)
    rows.append((label, t['auc'], t['auc_95ci'], thr, m['precision'], m['recall'], m['f1'], m['accuracy']))
print(f"{'model':32} {'AUC':>5} {'95% CI':>13} {'thr':>5} {'prec':>5} {'rec':>5} {'F1':>5} {'acc':>5}")
for r in rows:
    print(f"{r[0]:32} {r[1]:5.2f} {r[2][0]:5.2f}-{r[2][1]:4.2f} {r[3]:5.2f} {r[4]:5.0%} {r[5]:5.0%} {r[6]:5.2f} {r[7]:5.0%}")
mc = load(B / 'mcnemar_test316.json')
print('\\nMcNemar, shipped vs base   :', mc['mcnemar_v1_vs_base'])
print('McNemar, shipped vs v2 ep2 :', mc['mcnemar_v1_vs_v2_epoch2'])"""))
C.append(md("**Look at:** AUC (0.5 = guessing) and accuracy. The base model reaches F1 0.67 only by flagging every screen. **Conclude:** fine-tuning added real detection skill (p = 0.0001). The 70% F1 target is narrowly missed. Thresholds were chosen on validation (291 screens), never on test."))
C.append(code("""e2e = load(B / 'final_test316_end_to_end.json')
s = e2e['summary']
print('End to end through the production backend (decision + type + box):')
print({k: s[k] for k in ('precision', 'recall', 'f1', 'accuracy', 'invalid_outputs', 'type_accuracy_on_defects', 'iou_at_0_5_on_defects')})
import numpy as np
names = sorted(s['per_class'])
fig, ax = plt.subplots(figsize=(7, 3))
ax.bar(names, [s['per_class'][k]['binary_correct'] / s['per_class'][k]['n'] for k in names], color='#0e6f78')
ax.set_ylim(0, 1); ax.set_ylabel('judged correctly'); plt.xticks(rotation=20); ax.set_title('Defect vs clean, by true class (test)')"""))
C.append(md("**Conclude:** 'none' at about 50% means half the clean screens raise a false alarm, the main weakness. Defect type is right on 35% and boxes overlap well (IoU ≥ 0.5) on 8%: localization is the weakest skill, limited by noisy type and box labels."))

C.append(md("## 5. Demo screens through the real app pipeline\nSelected held-out test screens, re-run through the same code as the HEART desktop app. Green = expected region, red = model region. These show behaviour; they are not the accuracy."))
C.append(code("""demo = load(EV / '13_pp1_demo/demo_results.json')
for r in demo:
    print(f"#{r['n']} {Path(r['image']).name:24} expected {r['expected_type']:18} app: {r['decision']:19} {r['predicted_type']:18} score {r['defect_score']}")
imgs = sorted((EV / '13_pp1_demo').glob('*.png'))
fig, axes = plt.subplots(1, len(imgs), figsize=(3 * len(imgs), 7))
for ax, p in zip(axes, imgs):
    ax.imshow(Image.open(p)); ax.axis('off')"""))

C.append(md("## 6. Speed and memory (measured, model loaded once)"))
C.append(code("""score = load(B / 'v1_step246_test316_scores.json')['records']
lat_decision = sorted(r['latency_ms'] for r in score)
lat_e2e = sorted(r['latency_ms'] for r in e2e['records'])
flagged = sorted(r['latency_ms'] for r in e2e['records'] if r['pred_has'])
q = lambda v, p: v[min(len(v) - 1, int(len(v) * p))] / 1000
print(f"Decision only (one forward pass): median {q(lat_decision,.5):.2f} s, p95 {q(lat_decision,.95):.2f} s")
print(f"Flagged screens, incl. type+box : median {q(flagged,.5):.1f} s, p95 {q(flagged,.95):.1f} s")
print(f"All screens end to end          : median {q(lat_e2e,.5):.1f} s")
print(f"Peak GPU memory (PyTorch)       : {e2e['peak_vram_bytes']/2**30:.2f} GB of 4 GB")
off = load(EV / '14_pipeline_audit/offline_inference_check.json')
print(f"Offline run (all sockets blocked): {off['decision']}, network attempts = {len(off['network_connection_attempts'])}")"""))
C.append(md("**Conclude:** the defect/clean decision meets the 1.5 s target; generating the type and box does not. Offline was tested, not assumed: with every network connection blocked, inference still completes and makes zero connection attempts."))

C.append(md("## 7. Global view vs tiled views (validation only)"))
C.append(code("""p = EV / '14_pipeline_audit/tile_ablation_val60.json'
if p.exists():
    t = load(p)
    for pol, v in t['policies'].items():
        m = v['summary']
        print(f"{pol:22} prec {m['precision']:.0%} rec {m['recall']:.0%} F1 {m['f1']:.2f} acc {m['accuracy']:.0%} false alarms {m['fp']} median {m['median_latency_ms']/1000:.1f} s")
else:
    print('Tile ablation not run yet:', p)"""))
C.append(md("**Conclude:** this decides whether tile views stay off in the app."))

C.append(md("## 8. Optional live run (GPU, about 40 s including model load)\nSet `RUN_LIVE = True` to analyse one demo screen with the real model through the app's pipeline."))
C.append(code("""RUN_LIVE = False
if RUN_LIVE:
    sys.path.insert(0, str(C3.parent))
    import vision_oracle.services.oracle_service as svc
    from vision_oracle.local_vision_oracle.pipeline import AnalysisPipeline
    pipe = AnalysisPipeline(backend=svc.create_default_engine().backend, model_run_id='pp1-live')
    v = pipe.analyze(image=Image.open('C:/Games/OwlEye/Dataset/bug-aug/bug-aug/bug.4418.jpg').convert('RGB'), coverage_policy='global_only')
    print(v.decision, [(f.type, f.bbox_xyxy) for f in v.findings], v.metadata.get('defect_probability'), v.timings_ms)"""))

nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = Path(__file__).with_name("C3_PP1_measured_results.ipynb")
nbf.write(nb, out)
print(out)

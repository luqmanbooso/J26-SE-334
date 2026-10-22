"""Build the two PP1 notebooks; --refresh snapshots local evidence, --execute verifies them.

Default rebuild needs only the portable JSON bundle, not checkpoints or a GPU.
"""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import struct

import nbformat as nbf

HERE = Path(__file__).resolve().parent
C3 = HERE.parents[2]
NAMES = ['01_model_training_and_experiments', '02_model_progress_and_evaluation']


def refresh():
    provenance = []

    def read(path, role, as_json=True):
        path = Path(path)
        raw = path.read_bytes()
        provenance.append(dict(role=role, source=str(path), bytes=len(raw),
                               sha256=hashlib.sha256(raw).hexdigest()))
        return json.loads(raw) if as_json else raw.decode('utf-8-sig')

    def header(path):
        with path.open('rb') as f:
            size = struct.unpack('<Q', f.read(8))[0]
            raw = f.read(size)
        provenance.append(dict(role='tensor header (not weight content)', source=str(path),
                               bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        return {k: v for k, v in json.loads(raw).items() if k != '__metadata__'}

    inventory = read(HERE / 'pp1_evidence_inventory.json', 'prior audit')
    base = C3 / 'models/Qwen2-VL-2B-Instruct'
    tensors = {}
    for f in sorted(base.glob('*.safetensors')):
        tensors.update(header(f))
    if not tensors:
        raise FileNotFoundError('Base model tensors are required for --refresh')
    bundle = dict(schema_version=1, base_config=read(base/'config.json', 'base architecture'),
                  base_parameters=sum(math.prod(t['shape']) for t in tensors.values()),
                  models=[], benchmarks={}, diagnosis={}, training_configs={})
    for model in inventory['models']:
        path = Path(model['path'])
        tensors = header(path/'adapter_model.safetensors')
        bundle['models'].append(dict(name=model['name'],
            config=read(path/'adapter_config.json', model['name']+' adapter config'),
            state=read(path/'trainer_state.json', model['name']+' training state'),
            tensors=tensors,
            parameters=sum(math.prod(t['shape']) for t in tensors.values())))
    evidence = C3/'evidence'
    for f in sorted((evidence/'11_model_v2/benchmarks').glob('*.json')):
        bundle['benchmarks'][f.stem] = read(f, 'benchmark '+f.stem)
    for f in sorted((evidence/'11_model_v2/training').glob('*.yaml')):
        bundle['training_configs'][f.name] = read(f, 'archived training config', False)
    for f in sorted((evidence/'11_model_v2/diagnosis').glob('v1_adapter*.json')):
        bundle['diagnosis'][f.stem] = read(f, 'input diagnosis')
    bundle['tiles'] = read(evidence/'14_pipeline_audit/tile_ablation_val60.json', 'validation tiles')
    bundle['v3'] = read(evidence/'12_dataset_v3/dataset_v3_report.json', 'v3 data report')
    bundle['offline'] = read(evidence/'14_pipeline_audit/offline_inference_check.json', 'offline check')
    # Preserve relevant log lines so the historical YAML conflict is independently visible.
    log = read(evidence/'11_model_v2/training/train_v2.log', 'original v2 training log', False)
    bundle['v2_log_excerpt'] = [line for line in log.splitlines() if any(
        key in line for key in ('Num Epochs', 'Total optimization steps', 'Num examples',
                               'trainable params', 'trainable parameters', 'out of memory'))]
    bundle['provenance'] = provenance
    raw = (json.dumps(bundle, indent=1, ensure_ascii=False)+'\n').encode()
    (HERE/'evidence_bundle.json').write_bytes(raw)
    (HERE/'evidence_bundle.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n')


SETUP = '''from pathlib import Path
import sys
# Works when launched from the repository root, vision_oracle, or this folder.
candidates = [p / suffix for p in [Path.cwd(), *Path.cwd().parents]
              for suffix in ('', 'notebooks/old/pp1', 'vision_oracle/notebooks/old/pp1')]
HERE = next((p.resolve() for p in candidates if (p/'pp1_evidence.py').exists()), None)
if HERE is None:
    raise FileNotFoundError('Open from the repository or the pp1 notebook folder')
sys.path.insert(0, str(HERE))
from pp1_evidence import *
from IPython.display import display, Markdown
B = load_bundle(HERE)
plt.rcParams.update({'figure.dpi': 110, 'axes.spines.top': False, 'axes.spines.right': False})
display(Markdown('**Mode: saved evidence / CPU only. No model downloads, training, or inference.**'))
print('Verified bundle checksum. Source files:', len(B['provenance']))
'''


def notebook(title, intro, sections):
    cells = [nbf.v4.new_markdown_cell('# '+title+'\n\n'+intro), nbf.v4.new_code_cell(SETUP)]
    for text, code in sections:
        cells.append(nbf.v4.new_markdown_cell(text))
        if code:
            cells.append(nbf.v4.new_code_cell(code))
    return nbf.v4.new_notebook(cells=cells, metadata={
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python'}, 'pp1_mode': 'saved_evidence'})


def training():
    return notebook('C3: model parameters, training and experiments',
    'PP1 notebook 1 of 2. Explain what was trained, inspect the actual runs, and separate measured '
    'results from experiments still needed. Continue with [evaluation](02_model_progress_and_evaluation.ipynb).', [
    ('## 1. Parameters versus hyperparameters\n'
     '**Parameters** are learned numbers: pretrained weights and trained adapter matrices. '
     '**Hyperparameters** are choices made before training: learning rate, rank, dropout, batch size and schedule. '
     '**Inference settings** include prompt, resolution and decision threshold; changing them can change results without training.',
     '''cfg = B['base_config']
display(pd.DataFrame([
    ['Language transformer', cfg['num_hidden_layers'], cfg['hidden_size'], cfg['num_attention_heads']],
    ['Vision transformer', cfg['vision_config']['depth'], cfg['vision_config']['embed_dim'], cfg['vision_config']['num_heads']]
], columns=['component','layers','hidden/embedding size','attention heads']))
fig, ax = plt.subplots(figsize=(11, 2.3))
for x, label in [(0.12,'Screenshot\\nvision encoder'), (.39,'Visual tokens + prompt'), (.67,'Language model\\nfrozen W + trained LoRA'), (.92,'Verdict / type / box')]:
    ax.text(x, .5, label, ha='center', va='center', transform=ax.transAxes,
            bbox=dict(boxstyle='round,pad=.7', facecolor='#e5eff8', edgecolor='#4d7392'))
for x in [.23,.51,.8]: ax.annotate('', xy=(x+.05,.5), xytext=(x,.5), xycoords='axes fraction', arrowprops=dict(arrowstyle='->'))
ax.axis('off'); plt.show()
print('Vocabulary:', cfg['vocab_size'], '| configured context:', cfg['max_position_embeddings'])
'''),
    ('## 2. What LoRA actually changes\n'
     r'$W_{effective}=W_0+(\alpha/r)BA$. The pretrained matrix $W_0$ stays frozen; $A$ and $B$ are trained. '
     r'For a matrix with dimensions $d_{out}\times d_{in}$, adapter capacity is $r(d_{in}+d_{out})$. '
     'QLoRA uses a quantized base during training. Stored adapter dtype and training compute dtype are different concepts.',
     '''models = B['models']
rows = []
for m in models:
    c, t = m['config'], m['tensors']
    rows.append(dict(run=m['name'], rank=c['r'], alpha=c['lora_alpha'], dropout=c['lora_dropout'],
        adapter_parameters=m['parameters'], tensors=len(t),
        vision_tensors=sum('visual' in k or 'vision' in k for k in t),
        stored_dtype=','.join(sorted({v['dtype'] for v in t.values()}))))
display(pd.DataFrame(rows).set_index('run'))
base, adapter = B['base_parameters'], models[0]['parameters']
display(Markdown(f'**{base:,} stored base parameters + {adapter:,} adapter parameters.** '
                 f'The adapter is {adapter/(base+adapter):.3%} of the combined count; this is added trainable capacity.'))
fig, ax = plt.subplots(figsize=(7,3))
ax.barh(['Frozen base','Trainable adapter'], [base,adapter], color=['#547aa5','#e39838'])
ax.set_xscale('log'); ax.set_xlabel('Parameter count (log scale)'); plt.show()
print('Adapted modules:', ', '.join(sorted(models[0]['config']['target_modules'])))
'''),
    ('## 3. Actual training recipes\n'
     '| Setting | Meaning and trade-off |\n|---|---|\n'
     '| Learning rate | Update size; too large can destabilize learning, too small may learn too slowly. |\n'
     '| Rank r | Number of low-rank directions; controls adapter capacity and parameter cost. |\n'
     '| Alpha | Scales the adapter update by alpha/r; it is not the learning rate. |\n'
     '| Dropout | Training-time regularization; larger values are not automatically better. |\n'
     '| Batch / accumulation | Microbatch times accumulation times device count gives effective batch. |\n'
     '| Epochs / steps | Dataset passes / optimizer updates; affect training exposure and cost. |\n'
     '| Warmup / scheduler | How learning rate rises initially and changes during the run. |\n'
     '| Cutoff / image pixels | Text and visual input budgets; can remove useful evidence if too small. |\n\n'
     'The saved YAML files record intended settings. Trainer state records completed steps. '
     'These runs change several factors together, so they are historical recipe comparisons, not controlled learning-rate experiments.',
     '''def yaml_scalar(text, key):
    for line in text.splitlines():
        if line.startswith(key+':'): return line.split(':',1)[1].split('#',1)[0].strip()
    return 'not recorded'
config_names = ['qwen2vl_lora_sft_c3.yaml','qwen2vl_lora_sft_c3_boosted.yaml',
                'qwen2vl_lora_c3_v2.yaml','qwen2vl_lora_c3_v2_epoch2.yaml']
keys = ['dataset','learning_rate','lora_dropout','per_device_train_batch_size',
        'gradient_accumulation_steps','cutoff_len','image_max_pixels','num_train_epochs',
        'warmup_steps','lr_scheduler_type','optim','adapter_name_or_path']
recipes = pd.DataFrame({m['name']: {k:yaml_scalar(B['training_configs'][f],k) for k in keys}
                       for m,f in zip(models,config_names)})
display(recipes)
display(pd.DataFrame([dict(run=m['name'], completed_steps=m['state']['global_step'],
                         completed_epoch=m['state']['epoch'], planned_steps=m['state'].get('max_steps'),
                         eval_loss_points=sum('eval_loss' in x for x in m['state']['log_history'])) for m in models]))
print('Original v2 log excerpts:')
print('\\n'.join(B['v2_log_excerpt']))
'''),
    ('### Provenance conflict and training lineage\n'
     'The archived v2 YAML says three epochs, while the actual run log/state describes a two-epoch plan. '
     'Do not present the YAML alone as the executed configuration. The saved v2 checkpoint ends at epoch one. '
     'The additional epoch loads that adapter into a new training run; a full optimizer-state resume is not demonstrated.\n\n'
     'Lineage: base → v1 stage 1 → v1 boosted stage 2; separately, base → v2 checkpoint 173 → v2 additional epoch. '
     'v2 changes filtered data membership, compact targets and dropout as well as training history.', None),
    ('## 4. Logged loss and learning rate\n'
     'Read each run separately. Lower token loss across different target formats/data is not evidence of higher defect accuracy. '
     'No validation-loss series is available in these trainer states; checkpoint evaluation comes later.',
     '''fig, axes = plt.subplots(2,4,figsize=(15,6))
for col,m in enumerate(models):
    history = pd.DataFrame(m['state']['log_history'])
    for row,metric in enumerate(['loss','learning_rate']):
        points = history.dropna(subset=[metric])
        axes[row,col].plot(points['step'],points[metric], marker='.', linewidth=1)
        axes[row,col].set(title=m['name'] if row==0 else '', xlabel='Local training step', ylabel=metric)
fig.tight_layout(); plt.show()
'''),
    ('## 5. Rank capacity: an explanation, not an accuracy result\n'
     'All four saved adapters use rank 16. The chart below scales parameter count for the same target modules; '
     'ranks 4/8/32/64 have not been trained or evaluated here. Increasing rank increases capacity and cost, not guaranteed quality.',
     '''ranks = np.array([4,8,16,32,64])
counts = adapter * ranks / models[0]['config']['r']
fig, ax = plt.subplots(figsize=(7,3))
ax.bar(ranks.astype(str), counts/1e6, color=['#b4c2ce','#b4c2ce','#e39838','#b4c2ce','#b4c2ce'])
ax.set(xlabel='LoRA rank', ylabel='Adapter parameters (millions)', title='Theoretical capacity; only r=16 observed')
plt.show()
'''),
    ('## 6. What training progress can we substantiate?\n'
     'Validation AUC measures ranking quality. The validation-selected threshold is used in notebook 2. '
     'v1 has a different prompt from base/v2; use the labels as complete recipes.',
     '''table = score_table(B)
display(table[['val_auc','threshold']].round(5))
table['val_auc'].plot.bar(figsize=(8,3), ylim=(0,1), ylabel='Validation ROC AUC', rot=15)
plt.axhline(.5, color='gray', linestyle='--'); plt.show()
display(pd.DataFrame([
 ['Base vs v2, same prompt', 'AVAILABLE', 'Other recipe factors still differ'],
 ['Base vs v1, identical input contract', 'NOT RUN', 'Run base using exact v1 contract on validation first'],
 ['Controlled learning-rate sweep', 'NOT RUN', 'Same initialization, split, rank, targets, steps and seeds'],
 ['LoRA rank sweep', 'NOT RUN', 'All historical adapters have rank 16'],
 ['v3 trained model evaluation', 'NOT RUN', 'Data preparation exists; trained checkpoint not found']
], columns=['comparison','status','interpretation / next step']))
'''),
    ('## 7. Panel explanation and source trail\n'
     '“I trained small adapters on a frozen pretrained model, investigated an input-contract failure, and evaluated multiple '
     'training recipes. The newest recipe did not outperform v1 on the saved validation/test ranking metric. '
     'A controlled learning-rate or rank experiment is still needed to explain individual causes.”\n\n'
     'The bundle contains original records/configurations and extracted tensor headers, with source hashes. '
     'Header hashes validate parameter metadata, not weight values. These are snapshots taken for this presentation; '
     'historical benchmark files do not establish a cryptographic link to the exact weights/code used at run time.',
     'display(provenance(B))')])


def evaluation():
    return notebook('C3: measured model progress and evaluation',
    'PP1 notebook 2 of 2. Recompute saved comparisons, explain the remaining failures, and connect them to the '
    '[separate bug demo](../C3_live_demo.ipynb). These historical test results are already exposed; '
    'they must not be described as a fresh untouched final test.', [
    ('## 1. Fair comparison checks\n'
     'Pair records by full image identity and verify gold labels. Thresholds come only from validation, never the test-optimal '
     'threshold stored in score files. Scores are normalized true/false token logits, not calibrated probabilities.',
     '''table = score_table(B)
contracts = []
for name in RUNS:
    d = B['benchmarks'][name+'_test316_scores']
    c = d['meta']['contract']
    contracts.append(dict(run=name, n=len(d['records']), user_prompt=c.get('user_prompt'),
                          system_prompt=c.get('system_prompt'), pixels=c.get('image_max_pixels')))
display(pd.DataFrame(contracts).set_index('run'))
reference = B['benchmarks'][RUNS[0]+'_test316_scores']['records']
display(pd.crosstab(pd.Series([source(r) for r in reference],name='source'),
                    pd.Series([r['gold_type'] for r in reference],name='gold class')))
print('All four runs have identical image identities and gold labels:', len(reference))
'''),
    ('## 2. Base versus fine-tuned recipes\n'
     'The base/v2 prompt is shared; v1 uses its own training prompt. The v1 comparison therefore includes both weights and '
     'input-contract differences. Report precision and recall together: detecting almost every defect can still flag many clean screens.',
     '''display(table[['val_auc','test_auc','threshold','accuracy','precision','recall','f1','tp','fp','fn','tn']].round(4))
fig, axes = plt.subplots(1,2,figsize=(12,3.5))
table[['test_auc','f1','accuracy']].plot.bar(ax=axes[0],ylim=(0,1),rot=20)
table[['precision','recall']].plot.bar(ax=axes[1],ylim=(0,1),rot=20)
axes[0].set_title('Saved test recipe comparisons'); axes[1].set_title('Detection trade-off')
plt.tight_layout(); plt.show()
'''),
    ('## 3. ROC and precision–recall curves\n'
     'ROC summarizes ranking across thresholds. Precision–recall exposes false alarms when seeking high recall. '
     'Curves are recomputed from rounded stored scores with tied scores grouped together; no test threshold is selected.',
     '''fig, axes = plt.subplots(1,2,figsize=(11,4))
for name in RUNS:
    records = B['benchmarks'][name+'_test316_scores']['records']
    fpr,tpr,precision,auc = curves(records)
    axes[0].plot(fpr,tpr,label=f'{name}: {auc:.3f}')
    axes[1].step(tpr,precision,where='post',label=name)
axes[0].plot([0,1],[0,1],'--',color='gray')
axes[0].set(xlabel='False positive rate',ylabel='Recall',title='ROC')
axes[1].set(xlabel='Recall',ylabel='Precision',title='Precision–recall',ylim=(0,1.02))
for ax in axes: ax.legend(fontsize=8)
plt.tight_layout(); plt.show()
'''),
    ('## 4. Confusions and paired progress\n'
     'Count which exact screens become correct and which regress. A paired bootstrap estimates uncertainty in accuracy change '
     'over these saved screens; correlated screens from the same app can make image-level intervals optimistic.',
     '''fig, axes = plt.subplots(1,4,figsize=(14,3))
for ax,name in zip(axes,RUNS): confusion_plot(ax,table.loc[name],name)
plt.tight_layout(); plt.show()
def correct(name):
    rr = aligned(reference,B['benchmarks'][name+'_test316_scores']['records'])
    return np.array([(r['p_defect'] >= table.loc[name,'threshold']) == r['gold_has'] for r in rr])
baseline = correct(RUNS[0]); rng = np.random.default_rng(42)
rows=[]
for name in RUNS[1:]:
    now=correct(name); delta=now.astype(int)-baseline.astype(int)
    boot=delta[rng.integers(0,len(delta),size=(2000,len(delta)))].mean(axis=1)
    lo,hi=np.quantile(boot,[.025,.975])
    rows.append(dict(recipe=name, repaired=int(sum(now & ~baseline)), regressed=int(sum(~now & baseline)),
                     accuracy_change=delta.mean(), ci95_low=lo, ci95_high=hi))
display(pd.DataFrame(rows).set_index('recipe').round(4))
'''),
    ('## 5. Actual full-output backend decisions\n'
     'Score-only results and generated verdict/type/box results are separate measurements. Two v1 decisions lie at the '
     'rounded threshold boundary; use the recorded full-output decisions for this section. Invalid results are kept explicit, never counted as clean.',
     '''end = B['benchmarks']['final_test316_end_to_end']
rr = end['records']
full = binary_metrics([r['gold_has'] for r in rr],[r.get('pred_has') for r in rr])
display(pd.DataFrame([full],index=['v1 full output']).round(4))
score_rr = aligned(rr,B['benchmarks']['v1_step246_test316_scores']['records'])
boundary = [dict(image=r['image'],stored_score=s['p_defect'],recorded_prediction=r.get('pred_has'))
            for r,s in zip(rr,score_rr) if (s['p_defect'] >= table.loc['v1_step246','threshold']) != r.get('pred_has')]
display(pd.DataFrame(boundary))
print(f"Clean-screen false positive rate: {full['fp']/(full['fp']+full['tn']):.1%}")
fig, ax=plt.subplots(figsize=(4,3)); confusion_plot(ax,full,'Full-output backend'); plt.show()
'''),
    ('## 6. Which bugs are recognized?\n'
     'Binary recall is not defect-type accuracy or localization quality. Report the number of examples per class. '
     'Type and box annotations have not been established as independently human-verified; treat these metrics as exploratory.',
     '''rows=[]
for kind in sorted({r['gold_type'] for r in rr}):
    group=[r for r in rr if r['gold_type']==kind]
    rows.append(dict(gold_type=kind,n=len(group),
        binary_accuracy=sum(r.get('pred_has')==r['gold_has'] for r in group)/len(group),
        type_accuracy=sum(r.get('pred_type')==r['gold_type'] for r in group)/len(group)))
classes=pd.DataFrame(rows).set_index('gold_type'); display(classes.round(4))
classes[['binary_accuracy','type_accuracy']].plot.bar(figsize=(9,3),ylim=(0,1),rot=20); plt.show()
display(pd.crosstab(pd.Series([r['gold_type'] for r in rr],name='Gold type'),
                    pd.Series([r.get('pred_type') or 'INVALID' for r in rr],name='Predicted type')))
defects=[r for r in rr if r['gold_has']]
valid_iou=[r['iou'] for r in defects if r.get('iou') is not None]
print('IoU >= 0.5 / ALL gold defects:', sum(r.get('iou') is not None and r['iou']>=.5 for r in defects), '/', len(defects))
print('Gold defects without a measured IoU:', len(defects)-len(valid_iou))
fig,ax=plt.subplots(figsize=(6,3)); ax.hist(valid_iou,bins=np.linspace(0,1,11))
ax.set(xlabel='IoU (available boxes only)',ylabel='Screens'); plt.show()
source_rows=[]
for name in sorted({source(r) for r in rr}):
    group=[r for r in rr if source(r)==name]
    source_rows.append(dict(source=name,**binary_metrics([r['gold_has'] for r in group],[r.get('pred_has') for r in group])))
display(pd.DataFrame(source_rows).set_index('source').round(4))
'''),
    ('## 7. Evidence that the inference contract mattered\n'
     'Pair the same diagnostic screens before/after the input repair. Prompt and image resolution changed together; '
     'this is a joint input-contract ablation, not evidence that only one setting caused the improvement. Small validation diagnostic, not final-test accuracy.',
     '''old=B['diagnosis']['v1_adapter_app_input_val18']
new=B['diagnosis']['v1_adapter_training_input_val60']
lookup={identity(r):r for r in new}
paired=aligned(old,[lookup[identity(r)] for r in old])
diagnosis=pd.DataFrame([dict(contract=label,**binary_metrics([r['gold_has'] for r in rows],[r.get('pred_has') for r in rows]))
                       for label,rows in [('old app input',old),('training input',paired)]]).set_index('contract')
display(diagnosis.round(4))
diagnosis[['tp','fn','fp','tn']].plot.bar(figsize=(7,3),rot=0); plt.show()
'''),
    ('## 8. Tiling and practical cost\n'
     'Validation tiling can increase recall while adding false alarms and latency. Backend latency includes generation but '
     'does not establish complete camera/UI/API latency. Score-only timing is not full inspection timing.',
     '''tile_rows=[]
for name,policy in B['tiles']['policies'].items():
    records=policy['records']
    tile_rows.append(dict(policy=name,**binary_metrics([r['gold_has'] for r in records],[r.get('pred_has') for r in records]),
                          median_seconds=np.median([r['latency_ms'] for r in records])/1000))
tiles=pd.DataFrame(tile_rows).set_index('policy'); display(tiles.round(4))
fig,axes=plt.subplots(1,2,figsize=(10,3))
tiles[['precision','recall','f1']].plot.bar(ax=axes[0],ylim=(0,1),rot=0)
tiles['median_seconds'].plot.bar(ax=axes[1],rot=0,ylabel='Median backend seconds')
plt.tight_layout(); plt.show()
lat=np.array([r['latency_ms'] for r in rr])/1000
display(pd.DataFrame([dict(n=len(lat),median_seconds=np.median(lat),p95_seconds=np.percentile(lat,95),
                          saved_peak_vram_GiB=end['peak_vram_bytes']/1024**3,
                          load_seconds=end['meta']['load_seconds'])]))
fig,ax=plt.subplots(figsize=(7,3)); ax.hist(lat,bins=25); ax.set(xlabel='Full-output backend seconds',ylabel='Screens'); plt.show()
'''),
    ('## 9. Honest case studies\n'
     'These are deterministic examples from the saved full-output run: first true positive, false positive, false negative and true negative. '
     'The table executes without external images. Use the live demo notebook for screenshot overlays and bug demonstrations; '
     'show a failure as well as a success.',
     '''examples=[]
for gold,pred,label in [(True,True,'TP'),(False,True,'FP'),(True,False,'FN'),(False,False,'TN')]:
    r=next((r for r in rr if r['gold_has'] is gold and r.get('pred_has') is pred),None)
    if r: examples.append(dict(outcome=label,image=r['image'],gold_type=r['gold_type'],
                              predicted_type=r['pred_type'],gold_box=r['gold_box'],predicted_box=r['pred_box'],iou=r['iou']))
display(pd.DataFrame(examples).set_index('outcome'))
'''),
    ('## 10. Dataset progress is separate from model progress\n'
     'The v3 report documents new data preparation and app grouping. It is not a v3 model evaluation. '
     'Human review of defect visibility/type/boxes and a new frozen app-disjoint holdout are needed before stronger generalization claims.',
     '''splits=pd.DataFrame(B['v3']['splits']).fillna(0).astype(int)
display(splits); display(splits.sum().rename('screens per split'))
splits.T.plot.bar(stacked=True,figsize=(10,4),rot=0,ylabel='Screens')
plt.legend(bbox_to_anchor=(1.02,1),loc='upper left',fontsize=8); plt.tight_layout(); plt.show()
print('Reported app groups:', B['v3']['app_groups'])
print('Unlabelled OwlEye bugs excluded:', B['v3']['owleye_bug_unlabelled_excluded'])
'''),
    ('## 11. Next experiments and panel conclusion\n'
     '1. Run base and v1 under the **same exact contract** on validation; save full-precision scores, raw output and explicit invalid/abstention status.\n'
     '2. For learning rate, hold initialization, dataset, split, rank, dropout, total steps and preprocessing fixed; compare 2e-5/5e-5/1e-4 on validation. Use a fixed stratified screening subset, then confirm finalists on full validation.\n'
     '3. Test rank separately with the same controls and multiple seeds; report adapter size, memory, time and quality.\n'
     '4. Human-review labels and freeze a fresh app-disjoint final holdout before the next model-selection cycle.\n'
     '5. Evaluate hierarchy fusion only after a trained v3 checkpoint exists, with screenshot-only versus screenshot-plus-hierarchy controls.\n\n'
     '**Defensible conclusion:** adapter training and input-contract repair produced measurable recipe-level progress. '
     'The saved newest model does not dominate the older v1 recipe. False positives, type prediction and localization remain substantial weaknesses. '
     'No new base inference or training was performed by these notebooks.',
     'display(provenance(B))')])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh',action='store_true',help='Snapshot original local evidence and tensor headers')
    parser.add_argument('--execute',action='store_true',help='Execute both notebooks in fresh CPU kernels')
    args=parser.parse_args()
    if args.refresh: refresh()
    if not (HERE/'evidence_bundle.json').exists():
        parser.error('Evidence bundle missing; run --refresh on the evidence workstation first')
    for name,nb in zip(NAMES,[training(),evaluation()]):
        if args.execute:
            from nbclient import NotebookClient
            NotebookClient(nb,timeout=180,kernel_name='python3',resources={'metadata':{'path':str(HERE)}}).execute()
        nbf.validate(nb)
        nbf.write(nb,HERE/(name+'.ipynb'))
        if args.execute:
            figures = [output['data']['image/png'] for cell in nb.cells if cell.cell_type=='code'
                       for output in cell.outputs if 'image/png' in output.get('data',{})]
            if figures:
                (HERE/(name+'_preview.png')).write_bytes(base64.b64decode(figures[0]))
        print('Wrote',name,'(executed)' if args.execute else '(unexecuted)',flush=True)


if __name__=='__main__':
    main()

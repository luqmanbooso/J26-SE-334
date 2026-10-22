"""Builds Base_vs_FineTuned_Speed.ipynb: one screenshot through the base model and a fine-tuned adapter, with timing."""
from pathlib import Path
import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = [
    md("""# Base vs fine-tuned: speed on one screen

One screenshot, three ways:

| Arm | Weights | How the screen is fed and read |
|---|---|---|
| **A** base, default path | Qwen2-VL-2B, 4-bit | image shrunk to fit 720x1280, free-text answer (up to 256 tokens) |
| **B** base, contract path | same base weights | image cut to the adapter's pixel budget, one-token verdict, stops after the box |
| **C** fine-tuned | base + LoRA adapter | the contract path, as in the app |

**A to B** shows what the input handling changes (speed). **B to C** shows what fine-tuning changes (the answer; the adapter adds computation, so it is not a speed gain). Load time is shown separately because a cold start is much slower than later screens.

This is **one screen on one computer**: an illustration, not the accuracy result (see `Full_Statistics.ipynb`: AUC 0.594 to 0.814 on 425 screens).

Close the HEART app and other notebooks holding the model first (4 GB GPU). About 2 minutes."""),
    code("""import sys, json, time, gc
from pathlib import Path
C3 = next(p for p in [Path.cwd().resolve(), *Path.cwd().resolve().parents] if (p / 'demo_inputs').exists())
sys.path.insert(0, str(C3.parent))
import vision_oracle.services.oracle_service   # must be imported first (path guard for the local package)
import matplotlib.pyplot as plt
from PIL import Image
import torch
from local_vision_oracle.engine import TransformersInferenceBackend, load_inference_contract, contract_messages
from local_vision_oracle import model_compare as mc

# ---- Choose what to compare (edit these) --------------------------------------------------------------------
IMAGE   = C3 / 'demo_inputs' / '03_null_text.jpg'            # any screenshot; try a saved phone screen too
GOLD    = 'data_binding_null'                                 # the true defect type if you know it, else None
ADAPTER = C3 / 'models' / 'c3_v3_vision_1ep'                  # also: c3_v3_fusion_1ep, c3_qwen2vl_2b_lora_step246
BASE    = C3 / 'models' / 'Qwen2-VL-2B-Instruct'
REPEATS = 3                                                    # timed runs per arm (median is reported)
# --------------------------------------------------------------------------------------------------------------
contract = load_inference_contract(str(ADAPTER))
messages = contract_messages(contract)
image = Image.open(IMAGE).convert('RGB')
free = torch.cuda.mem_get_info()[0] / 2**20
print(f'Screen : {IMAGE.name}  {image.width}x{image.height}  ({image.width*image.height/1e6:.2f} megapixels)')
print(f'Adapter: {ADAPTER.name}   alert level {contract.get("decision_threshold")}')
print(f'GPU    : {torch.cuda.get_device_name(0)}, {free:.0f} MiB free (needs about 2000)')
assert free > 2000, 'Not enough free GPU memory: close the HEART app and other notebooks, then restart this kernel.'
plt.figure(figsize=(3, 5.3)); plt.imshow(image); plt.axis('off'); plt.title('input screen'); plt.show()"""),
    md("## Arms A and B: the base model (no fine-tuning)\nThe base model is loaded once. Arm A uses its default path, then arm B feeds the **same weights** the way the adapter is fed."),
    code("""results, load_s = {}, {}
t = time.perf_counter()
base = TransformersInferenceBackend(model_name_or_path=str(BASE), adapter_dir=None, quantization_bit=4, device='cuda', lazy_load=False)
load_s['base'] = time.perf_counter() - t
print(f'Base model loaded in {load_s["base"]:.0f} s')

base.inference_contract = None                                     # arm A: default path
results['A  base, default path'] = mc.measure(base, image, messages, repeats=REPEATS)
print('A done')
base.inference_contract = contract                                 # arm B: same weights, contract path
results['B  base, contract path'] = mc.measure(base, image, messages, repeats=REPEATS)
print('B done')
base.unload(); del base; gc.collect(); torch.cuda.empty_cache()
print(f'GPU memory after unloading the base model: {torch.cuda.memory_allocated()/2**20:.0f} MiB')"""),
    md("## Arm C: the fine-tuned model\nThe base weights are unloaded first, so only one model is ever in memory."),
    code("""t = time.perf_counter()
tuned = TransformersInferenceBackend(model_name_or_path=str(BASE), adapter_dir=str(ADAPTER), quantization_bit=4, device='cuda', lazy_load=False)
load_s['tuned'] = time.perf_counter() - t
print(f'Base + adapter loaded in {load_s["tuned"]:.0f} s')
results['C  fine-tuned'] = mc.measure(tuned, image, messages, repeats=REPEATS)
print('C done')
tuned.unload(); del tuned; gc.collect(); torch.cuda.empty_cache()"""),
    md("## Results"),
    code("""def parse(out):
    try: return json.loads(out[out.index('{'): out.rindex('}') + 1])
    except Exception: return None

print(f'{"arm":<26}{"total":>10}{"verdict":>10}{"box":>9}{"image px":>11}{"img tokens":>12}{"peak VRAM":>11}')
for name, r in results.items():
    v = f'{r["verdict_ms"]:.0f} ms' if r['verdict_ms'] is not None else '-'
    b = f'{r["box_ms"]:.0f} ms' if r['box_ms'] is not None else '-'
    print(f'{name:<26}{r["total_ms"]/1000:>8.2f} s{v:>10}{b:>9}{r["image_px"]:>11,}{r["visual_tokens"]:>12,}{r["peak_vram_mib"]:>9.0f} MiB')
print(f'\\nModel load (cold start): base {load_s["base"]:.0f} s, base + adapter {load_s["tuned"]:.0f} s')
print('\\nWhat each model answered')
for name, r in results.items():
    obj = parse(r['output'])
    kind = (obj or {}).get('defect_type', 'unparseable answer') if obj else 'unparseable answer'
    ok = '' if GOLD is None else ('  <- correct type' if kind == GOLD else '  <- not the true type')
    print(f'  {name}: {kind}{ok}')
    print('     ' + r['output'].replace(chr(10), ' ')[:200])"""),
    code("""names = list(results)
colors = ['#94a3b8', '#64748b', '#f97316']
fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
for a, key, title, scale in ((ax[0], 'total_ms', 'Time to answer one screen (s)', 1000), (ax[1], 'visual_tokens', 'Image tokens the model reads', 1),
                             (ax[2], 'peak_vram_mib', 'Peak GPU memory (MiB)', 1)):
    vals = [results[n][key] / scale for n in names]
    bars = a.bar([n.split('  ')[0] for n in names], vals, color=colors)
    a.set_title(title, fontsize=10); a.bar_label(bars, fmt='%.1f' if key == 'total_ms' else '%.0f', fontsize=9)
    a.spines[['top', 'right']].set_visible(False)
plt.tight_layout(); plt.show()"""),
    md("## What these numbers say"),
    code("""A, B, C = (results[n] for n in names)
print(f'* Input size: the contract path feeds {B["visual_tokens"]:,} image tokens instead of {A["visual_tokens"]:,} '
      f'({A["visual_tokens"]/B["visual_tokens"]:.1f}x fewer).')
def versus(a, b):
    r = a / b
    return f'{r:.1f}x faster' if r >= 1.05 else (f'{1/r:.1f}x slower' if r <= 0.95 else 'about the same')
print(f'* Same weights, different path: arm A {A["total_ms"]/1000:.1f} s, arm B {B["total_ms"]/1000:.1f} s (B is {versus(A["total_ms"], B["total_ms"])}). '
      'Any gap here comes from the inference design, not from training.')
print(f'* Base vs fine-tuned on the same path: B {B["total_ms"]/1000:.1f} s, C {C["total_ms"]/1000:.1f} s (C is {versus(B["total_ms"], C["total_ms"])}). '
      'Fine-tuning is not a speed gain; the adapter adds computation.')
print(f'* Fine-tuned vs the default base path: C is {versus(A["total_ms"], C["total_ms"])} per screen. '
      'Do not present the fine-tuned model as faster unless this line says so.')
print(f'* Cold start: loading the model takes about {load_s["tuned"]:.0f} s once (base {load_s["base"]:.0f} s); after that each screen takes {C["total_ms"]/1000:.1f} s.')
print('* One screen on one computer: quote it as an illustration, not as the accuracy result.')"""),
    code("""out = C3 / 'results' / 'model_compare'; out.mkdir(parents=True, exist_ok=True)
stamp = time.strftime('%Y%m%d_%H%M%S')
(out / f'{stamp}_{IMAGE.stem}.json').write_text(json.dumps({'image': str(IMAGE), 'adapter': str(ADAPTER), 'gold': GOLD, 'load_s': load_s, 'arms': results}, indent=1, default=str), encoding='utf-8')
print('saved', out / f'{stamp}_{IMAGE.stem}.json')"""),
]
nb = nbf.v4.new_notebook(); nb.cells = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = Path(__file__).resolve().parents[1] / "Base_vs_FineTuned_Speed.ipynb"
with open(out, "w", encoding="utf-8", newline="\n") as fh:
    nbf.write(nb, fh)
print(out)

"""Builds C3_live_demo.ipynb: runs each demo screen through the real app service and shows it."""
from pathlib import Path
import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = [
    md("""# C3 Vision Oracle: live demo

Each screen below is analysed **live** by the shipped model, through the same service the HEART app's *Inspect screenshot* button uses (global view, retrained adapter `c3_v3_vision_1ep`, decision threshold 0.30 read from the adapter's own contract). All nine screens are in the held-out test split of the retrained dataset, so the model never trained on them.

**Red box** = the region the model flagged (approximate). **Green box** = where the defect really is.

These are selected screens that show behaviour. For accuracy, quote the held-out test only: AUC 0.81, F1 0.78, precision 68%, recall 90% on 425 screens. At this threshold about half of clean screens are also flagged, so a clean screen shown as flagged below is expected behaviour, not a surprise.

Run the cells from top to bottom. The first cell loads the model (about 20–40 s). Each screen then takes about 1 s if clean, or 8–10 s if a defect is found."""),
    code("""import sys, time
from pathlib import Path
C3 = next(p for p in [Path.cwd().resolve(), *Path.cwd().resolve().parents] if (p / 'demo_inputs').exists())
sys.path.insert(0, str(C3.parent))
import os, json
os.environ['C3_ADAPTER'] = str(C3 / 'models' / 'c3_v3_vision_1ep')   # the retrained adapter
THRESH = json.loads((Path(os.environ['C3_ADAPTER']) / 'inference_contract.json').read_text(encoding='utf-8'))['decision_threshold']
import vision_oracle.services.oracle_service as svc_mod   # must be imported first (path guard)
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image

t = time.perf_counter()
service = svc_mod.get_oracle_service()
print(f'Model loaded in {time.perf_counter() - t:.0f} s')
DEMO = C3 / 'demo_inputs'

# Expected answers and true defect regions [ymin, xmin, ymax, xmax] in 0-1000 (relabelled by eye).
EXPECTED = {
    '01_overlap_team_names.jpg': ('component_overlap', [200, 0, 340, 1000]),
    '02_overlap_title.jpg': ('component_overlap', [240, 150, 300, 560]),
    '03_null_text.jpg': ('data_binding_null', [262, 450, 295, 560]),
    '04_missing_icons.jpg': ('missing_component', [294, 80, 380, 250]),
    '05_missing_widget_synthetic.jpg': ('missing_component', None),
    '06_overlap_synthetic.jpg': ('component_overlap', None),
    '07_clean_owleye.jpg': ('none', None),
    '08_clean_rico.jpg': ('none', None),
    '09_known_miss_truncation.jpg': ('text_truncation', [190, 0, 215, 350]),
}

def inspect(name, layout=None):
    path = DEMO / name
    hierarchy = (DEMO / layout).read_text(encoding='utf-8') if layout else None
    t = time.perf_counter()
    res = service.evaluate(image_input=str(path), raw_hierarchy=hierarchy, session_id='notebook_demo', enable_sahi=False)
    secs = time.perf_counter() - t
    v = res['verdict_v2']
    decision = getattr(v['decision'], 'value', v['decision'])
    f = v['findings'][0] if v['findings'] else {}
    got = f.get('type', 'none')
    expected, gold = EXPECTED[name]
    img = Image.open(path).convert('RGB'); W, H = img.size
    fig, ax = plt.subplots(figsize=(4.5, 8)); ax.imshow(img); ax.axis('off')
    if gold:
        y1, x1, y2, x2 = gold
        ax.add_patch(Rectangle((x1*W/1000, y1*H/1000), (x2-x1)*W/1000, (y2-y1)*H/1000, fill=False, ec='lime', lw=3))
    if f.get('bbox_xyxy'):
        x1, y1, x2, y2 = f['bbox_xyxy']
        ax.add_patch(Rectangle((x1, y1), x2-x1, y2-y1, fill=False, ec='red', lw=3))
    ok = got == expected
    ax.set_title(('CORRECT' if ok else 'MISSED') + f'\\nexpected {expected}\\nmodel {got}', color='green' if ok else 'red', fontsize=10)
    plt.show()
    score = v['metadata'].get('defect_probability')
    print(f"Decision : {decision}")
    print(f"Type     : model said '{got}', expected '{expected}' -> {'CORRECT' if ok else 'MISSED'}")
    print(f"Score    : {score:.2f} (flagged at {THRESH:.2f} or above)" if score is not None else 'Score: -')
    if f.get('element_ref'):
        print(f"Element  : {f['element_ref']} (matched from the layout file)")
    print(f"Time     : {secs:.1f} s")"""),
]
screens = [
    ("Real bug: overlapping text", "01_overlap_team_names.jpg", None),
    ("Real bug: title drawn over the description", "02_overlap_title.jpg", None),
    ("Real bug: the word 'null' shown to the user", "03_null_text.jpg", None),
    ("Real bug: icons not rendered", "04_missing_icons.jpg", None),
    ("Synthetic bug: grey placeholder replaces a widget", "05_missing_widget_synthetic.jpg", None),
    ("Synthetic bug with layout file: the result names the real element", "06_overlap_synthetic.jpg", "06_overlap_synthetic_layout.json"),
    ("Clean screen: should not be flagged", "07_clean_owleye.jpg", None),
    ("Clean screen: should not be flagged", "08_clean_rico.jpg", None),
    ("Known limitation: thin clipped text is missed", "09_known_miss_truncation.jpg", None),
]
for i, (title, name, layout) in enumerate(screens, 1):
    cells.append(md(f"## {i}. {title}"))
    cells.append(code(f"inspect({name!r}" + (f", layout={layout!r})" if layout else ")")))
cells.append(md("## Try your own screenshot\nPut any screenshot path below and run the cell (expected answer unknown, so no green box)."))
cells.append(code("""MY_SCREEN = r''   # e.g. r'C:\\\\Users\\\\you\\\\Desktop\\\\screen.png'
if MY_SCREEN:
    r = service.evaluate(image_input=MY_SCREEN, session_id='notebook_demo', enable_sahi=False)['verdict_v2']
    img = Image.open(MY_SCREEN).convert('RGB'); fig, ax = plt.subplots(figsize=(4.5, 8)); ax.imshow(img); ax.axis('off')
    for f in r['findings']:
        x1, y1, x2, y2 = f['bbox_xyxy']; ax.add_patch(Rectangle((x1, y1), x2-x1, y2-y1, fill=False, ec='red', lw=3))
    ax.set_title(f"{getattr(r['decision'], 'value', r['decision'])}: {[f['type'] for f in r['findings']]}"); plt.show()
    print('score', r['metadata'].get('defect_probability'))"""))
nb = nbf.v4.new_notebook(); nb.cells = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = Path(__file__).with_name("C3_live_demo.ipynb"); nbf.write(nb, out); print(out)

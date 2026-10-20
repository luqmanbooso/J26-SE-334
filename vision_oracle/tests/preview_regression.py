"""Run manually with a display: python vision_oracle/tests/preview_regression.py."""
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).resolve().parents[1])]
import tkinter as tk
from PIL import Image
from tempfile import TemporaryDirectory
from vision_oracle.frontend.workspace import C3Workspace

root=tk.Tk();root.withdraw()
other=tk.Tk();other.withdraw()
class PreviewHarness:
    draw_preview=C3Workspace.draw_preview
    clear_preview=C3Workspace.clear_preview
h=PreviewHarness();h.preview=tk.Label(other)
with TemporaryDirectory() as folder:
    path=Path(folder)/'screen.png';Image.new('RGB',(100,200),'white').save(path)
    for _ in range(20):
        h.draw_preview(path,[])
        assert h.preview_image.tk is h.preview.tk
        assert h.preview.tk.call('image','width',str(h.preview_image))==100
    # Reproduce the missing-image state seen in the reported traceback.
    h.preview.tk.call('image','delete',str(h.preview_image))
    h.clear_preview('Capturing phone')
    assert h.preview.cget('image')==''
    h.draw_preview(path,[])
    h.draw_preview(Path(folder)/'missing.png',[])
    assert h.preview.cget('image')==''
    assert 'Preview unavailable' in h.preview.cget('text')
    h.draw_preview(path,[])
    assert h.preview.cget('image')
other.destroy();root.destroy()
print('PASS: repeated replacements, explicit interpreter, deleted image recovery, missing file, retry')

# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_all, collect_submodules

block_cipher = None

# Base repository root
repo_root = os.path.abspath(SPECPATH)
c4_src = os.path.join(repo_root, 'component4', 'src')
if c4_src not in sys.path:
    sys.path.insert(0, c4_src)

datas = []
binaries = []
hiddenimports = [
    'customtkinter',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'PIL.ImageDraw',
    'yaml',
    'psutil',
    'requests',
    'fastapi',
    'uvicorn',
    'pydantic',
    'pydantic_core',
    'libcst',
    'numpy',
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'math',
    'shutil',
    'queue',
    'webbrowser',
    'threading',
    'subprocess',
    'json',
    're',
]

# Collect essential packages completely (data + submodules + binaries)
for pkg in ['customtkinter', 'libcst', 'pydantic', 'pydantic_core', 'fastapi', 'uvicorn', 'starlette']:
    try:
        p_datas, p_binaries, p_hidden = collect_all(pkg)
        datas += p_datas
        binaries += p_binaries
        hiddenimports += p_hidden
    except Exception as e:
        print(f"[WARN] Failed to collect_all for {pkg}: {e}")

# Collect all c4 component modules
try:
    hiddenimports += collect_submodules('c4')
except Exception as e:
    print(f"[WARN] Failed to collect_submodules for c4: {e}")

# Include required internal folders
for d in ['env testing', 'vision_oracle', 'biometry', 'common', 'component4', 'results']:
    full_p = os.path.join(repo_root, d)
    if os.path.exists(full_p):
        datas.append((full_p, d))

# Include static assets and icons
for asset in ['heart_app.ico', 'favicon.png', 'favicon_cropped.png', 'logo.png', 'logo_cropped.png', 'LICENSE']:
    full_p = os.path.join(repo_root, asset)
    if os.path.exists(full_p):
        datas.append((full_p, '.'))

# Explicitly exclude huge deep-learning runtimes to keep standalone installer lightweight (~50-80MB)
heavy_excludes = [
    'torch',
    'torchaudio',
    'torchvision',
    'tensorflow',
    'scipy',
    'transformers',
    'tokenizers',
    'huggingface_hub',
    'safetensors',
    'triton',
    'sympy',
    'pytest',
    'IPython',
    'notebook',
    'nbformat',
]

pathex_dirs = [
    repo_root,
    c4_src,
    os.path.join(repo_root, 'env testing'),
    os.path.join(repo_root, 'vision_oracle'),
    os.path.join(repo_root, 'biometry'),
    os.path.join(repo_root, 'common'),
    os.path.join(repo_root, 'results'),
]

a = Analysis(
    ['heart_desktop_app.py'],
    pathex=pathex_dirs,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=heavy_excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Strip out any lingering CUDA or torch dynamic libraries
a.binaries = [
    b for b in a.binaries 
    if not any(k in b[0].lower() for k in ['torch', 'cuda', 'cublas', 'cudnn', 'c10', 'nvrtc', 'curand', 'cusolver', 'cusparse'])
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HEART_Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(repo_root, 'heart_app.ico') if os.path.exists(os.path.join(repo_root, 'heart_app.ico')) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='HEART_Studio',
)

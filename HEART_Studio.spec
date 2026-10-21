# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Base repository root
repo_root = os.path.abspath(SPECPATH)

datas = []
# Collect customtkinter themes and fonts
datas += collect_data_files('customtkinter')

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

# Explicitly exclude huge deep-learning runtimes to keep standalone installer lightweight (~50MB)
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

a = Analysis(
    ['heart_desktop_app.py'],
    pathex=[repo_root],
    binaries=[],
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

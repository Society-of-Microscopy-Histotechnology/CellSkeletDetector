# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


python_root = Path(sys.executable).parent
runtime_dlls = []
for dll_name in (
    "concrt140.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "vcomp140.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
):
    dll_path = python_root / dll_name
    if dll_path.is_file():
        runtime_dlls.append((str(dll_path), "."))

for binary_path in (
    python_root / "DLLs" / "_tkinter.pyd",
    python_root / "DLLs" / "tcl86t.dll",
    python_root / "DLLs" / "tk86t.dll",
):
    if binary_path.is_file():
        runtime_dlls.append((str(binary_path), "."))

hidden_imports = [
    module
    for module in collect_submodules("skimage")
    if ".tests" not in module
]
hidden_imports += collect_submodules("imageio.plugins")
hidden_imports += collect_submodules("tkinter")

data_files = collect_data_files("skimage", excludes=["**/tests/**"])
tkinter_package = python_root / "Lib" / "tkinter"
if tkinter_package.is_dir():
    data_files.append((str(tkinter_package), "tkinter"))
for source, destination in (
    (python_root / "tcl" / "tcl8.6", "_tcl_data"),
    (python_root / "tcl" / "tk8.6", "_tk_data"),
):
    if source.is_dir():
        data_files.append((str(source), destination))

analysis = Analysis(
    ["app.py"],
    pathex=[str(python_root / "Lib")],
    binaries=runtime_dlls,
    datas=data_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["pyi_rth_tkinter_manual.py"],
    excludes=[
        "cv2",
        "IPython",
        "ipywidgets",
        "jupyter",
        "matplotlib",
        "pandas",
        "pytest",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="CellSkeletDetector",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller — Application MK_A.A 2026 (exe onefile).

Construit un EXE autonome nommé "MK_AA_2026" avec l'icône assets/icon.ico.
valve_database.json est embarqué en binaire ET copié à côté de l'exe (modifiable).
"""

import os

ROOT = os.path.abspath(SPECPATH)

a = Analysis(
    ['main.py'],
    pathex=[ROOT],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('valve_database.json', '.'),
    ],
    hiddenimports=[
        'customtkinter',
        'PIL._tkinter_finder',
        'openpyxl',
        'docx',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MK_AA_2026',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=['assets/icon.ico'],
)
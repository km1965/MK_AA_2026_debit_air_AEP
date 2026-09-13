# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller — Application MK_A.A 2026 — VARIANTE V01 PRO.

Variante PRO (profil complet) — EXE onefile autonome nommé "MK_AA_2026_V01_Pro".
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
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MK_AA_2026_V01_Pro',
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
    icon=['assets/icon.ico'],
)
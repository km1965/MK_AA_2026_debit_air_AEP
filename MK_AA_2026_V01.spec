# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller — Application MK_A.A 2026 — VARIANTE V01 (compilée).

Variante de travail construite sur la version actuelle (modifiée) du code.
Produit un EXE onefile autonome nommé "MK_AA_2026_V01".
L'EXE de référence initial reste MK_AA_2026.exe.
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
    name='MK_AA_2026_V01',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=['assets/icon.ico'],
)
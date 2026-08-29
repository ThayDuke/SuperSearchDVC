# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files

SPEC_DIR = os.path.dirname(os.path.abspath('SuperSearch.spec'))
MAGIKA_DATAS = collect_data_files('magika')

a = Analysis(
    ['app.py'],
    pathex=[SPEC_DIR],
    binaries=[],
    datas=MAGIKA_DATAS,
    hiddenimports=[
        'xml.dom', 'xml.dom.minidom', 'xml.sax', 'xml.sax.expatreader', 'xml.parsers.expat',
        'html.parser', 'html.entities', 'http.client', 'http.cookiejar',
        'urllib.request', 'urllib.parse', 'urllib.error', 'urllib.response',
        'decimal', 'csv', 'uuid', 'logging', 'zoneinfo', 'mimetypes',
        'index_store', 'sqlite3'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'markitdown_ocr', 'openai', 'azure', 'google', 'msal', 'tkinter', 'unittest',
        'pydub', 'speech_recognition', 'matplotlib'
    ],
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
    name='SuperSearch',
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
    icon=[os.path.join(SPEC_DIR, 'LogoSS256.ico')],
)

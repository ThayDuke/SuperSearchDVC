# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'xml.dom', 'xml.dom.minidom', 'xml.sax', 'xml.sax.expatreader', 'xml.parsers.expat',
        'html.parser', 'html.entities', 'http.client', 'http.cookiejar',
        'urllib.request', 'urllib.parse', 'urllib.error', 'urllib.response',
        'decimal', 'csv', 'uuid', 'logging', 'zoneinfo', 'mimetypes'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'markitdown', 'markitdown_ocr', 'openai', 'magika', 'pdfplumber', 'pdfminer', 
        'pytesseract', 'PIL', 'numpy', 'pandas', 'openpyxl', 'docx', 'pptx', 'matplotlib',
        'jinja2', 'sqlite3', 'tkinter', 'unittest', 'pydub', 'speech_recognition'
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
    icon=['LogoSS256.ico'],
)

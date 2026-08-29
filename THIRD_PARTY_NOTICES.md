# Third-party notices

SuperSearch bundles or installs the following direct dependencies. Versions are
pinned in `requirements.txt`; each package remains subject to its upstream
license and notice requirements.

| Component | Version | License / notice |
|---|---:|---|
| MarkItDown | 0.1.6 | MIT |
| Magika | 0.6.2 | Apache-2.0 |
| ONNX Runtime | 1.27.0 | MIT |
| pdfplumber | 0.11.10 | MIT |
| pytesseract | 0.3.13 | Apache-2.0 |
| Pillow | 12.2.0 | HPND/PIL license |
| olefile | 0.47 | BSD-3-Clause |
| xlrd | 2.0.2 | BSD-3-Clause |
| pandas | 3.0.3 | BSD-3-Clause |
| openpyxl | 3.1.5 | MIT |
| python-pptx | 1.0.2 | MIT |
| pywebview | 6.2.1 | BSD-3-Clause |
| PyInstaller | 6.21.0 | GPL-2.0 with bootloader exception |

The bundled Tesseract-OCR runtime is used locally for Vietnamese and English
OCR. Its upstream Apache-2.0 license and the licenses of its Leptonica and
image-format components must remain with the portable distribution.

This file is a distribution index, not a replacement for the full upstream
license texts. Preserve upstream `LICENSE`/`NOTICE` files when assembling a
release package.

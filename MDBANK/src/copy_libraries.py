import os
import shutil
import sys

# Script to offline-copy installed dependencies to Lib folder for portable packaging

src_dir = os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming', 'Python', 'Python314', 'site-packages')
dest_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Lib')

if not os.path.exists(src_dir):
    # Try global site-packages
    src_dir = r"C:\Python314\Lib\site-packages"

if not os.path.exists(src_dir):
    print("Error: Could not find Python site-packages directory.")
    sys.exit(1)

os.makedirs(dest_dir, exist_ok=True)

folders = [
    'aiohappyeyeballs', 'aiohttp', 'aiosignal', 'annotated_types', 'anyio', 'attr', 'attrs',
    'azure', 'blinker', 'bs4', 'certifi', 'cffi', 'charset_normalizer',
    'click', 'cobble', 'colorama', 'cryptography', 'dateutil', 'defusedxml', 'distro',
    'docx', 'dotenv', 'fitz', 'flatbuffers', 'frozenlist', 'google', 'h11',
    'httpcore', 'httpx', 'idna', 'isodate', 'itsdangerous', 'jinja2', 'jiter', 'jwt',
    'lxml', 'magika', 'mammoth', 'markdownify', 'markitdown', 'markitdown_ocr', 'markupsafe',
    'msal', 'msal_extensions', 'multidict', 'numpy', 'numpy.libs', 'olefile', 'onnxruntime',
    'openai', 'openpyxl', 'packaging', 'pandas', 'pandas.libs', 'pathvalidate', 'pdfminer',
    'pdfplumber', 'PIL', 'pptx', 'propcache', 'pydantic', 'pydantic_core', 'pymupdf',
    'pypdfium2', 'pypdfium2_cfg', 'pypdfium2_cli', 'pypdfium2_raw', 'pytesseract', 'requests',
    'sniffio', 'soupsieve', 'tqdm', 'typing_extensions', 'typing_inspection', 'tzdata',
    'urllib3', 'xlsxwriter', 'yarl'
]

# Scan for files to copy in root
files = ['six.py', 'typing_extensions.py']
for item in os.listdir(src_dir):
    if item.endswith('.pyd'):
        files.append(item)

print(f"Source: {src_dir}")
print(f"Destination: {dest_dir}")

force_copy = "--force" in sys.argv or "-f" in sys.argv

for folder in folders:
    src_folder = os.path.join(src_dir, folder)
    dest_folder = os.path.join(dest_dir, folder)
    if os.path.exists(src_folder):
        if os.path.exists(dest_folder) and not force_copy:
            continue
        print(f"Copying folder: {folder}")
        if os.path.exists(dest_folder):
            shutil.rmtree(dest_folder)
        shutil.copytree(src_folder, dest_folder)

for file in files:
    src_file = os.path.join(src_dir, file)
    dest_file = os.path.join(dest_dir, file)
    if os.path.exists(src_file):
        if os.path.exists(dest_file) and not force_copy:
            continue
        print(f"Copying file: {file}")
        shutil.copy2(src_file, dest_file)

print("Copy completed successfully!")


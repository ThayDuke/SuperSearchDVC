"""Create a deterministic portable ZIP from a validated build artifact."""

import os
import hashlib
import json
import shutil
import tempfile
import time
import zipfile


def _ignore_runtime_junk(_directory, names):
    return {name for name in names if name == "__pycache__" or name.endswith((".pyc", ".pyo"))}


def _ignore_tesseract_tools(_directory, names):
    ignored = _ignore_runtime_junk(_directory, names)
    for name in names:
        lower_name = name.lower()
        if lower_name.endswith((".1.html", ".5.html")):
            ignored.add(name)
        elif lower_name.endswith(".exe") and lower_name != "tesseract.exe":
            ignored.add(name)
    return ignored


def _copy_required_file(source, destination):
    if not os.path.isfile(source):
        raise FileNotFoundError(f"Required artifact is missing: {source}")
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copy2(source, destination)


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    zip_path = os.path.join(base_dir, "SuperSearch_Portable.zip")
    exe_src = os.path.join(base_dir, "build_artifacts", "SuperSearch.exe")
    if not os.path.isfile(exe_src):
        raise FileNotFoundError("Không tìm thấy SuperSearch.exe; hãy build trước khi đóng gói.")
    html_src = os.path.join(base_dir, "data", "SuperSearch.html")
    tess_src = os.path.join(base_dir, "src", "Tesseract-OCR")
    if not os.path.isfile(html_src):
        raise FileNotFoundError(f"Thiếu UI: {html_src}")
    if not os.path.isdir(tess_src) or not os.path.isfile(os.path.join(tess_src, "tesseract.exe")):
        raise FileNotFoundError("Thiếu Tesseract-OCR/tesseract.exe; không tạo gói thiếu runtime.")

    temp_dir = tempfile.mkdtemp(prefix="SuperSearch_Portable-", dir=base_dir)
    zip_tmp = f"{zip_path}.tmp-{os.getpid()}"
    try:
        _copy_required_file(exe_src, os.path.join(temp_dir, "SuperSearch.exe"))
        for name in ("Readme.html", "readme.txt", "THIRD_PARTY_NOTICES.md", "requirements.txt"):
            source = os.path.join(base_dir, name)
            if os.path.isfile(source):
                _copy_required_file(source, os.path.join(temp_dir, name))
        _copy_required_file(
            os.path.join(base_dir, "src", "LogoSS256.ico"),
            os.path.join(temp_dir, "src", "LogoSS256.ico"),
        )

        data_dest = os.path.join(temp_dir, "data")
        os.makedirs(data_dest, exist_ok=True)
        shutil.copy2(html_src, os.path.join(data_dest, "SuperSearch.html"))
        for name in os.listdir(os.path.join(base_dir, "data")):
            source = os.path.join(base_dir, "data", name)
            if os.path.isfile(source) and os.path.splitext(name)[1].lower() in {".ico", ".png", ".jpg", ".jpeg", ".svg"}:
                shutil.copy2(source, os.path.join(data_dest, name))

        runtime_root = os.path.join(temp_dir, "runtime")
        os.makedirs(os.path.join(runtime_root, "MARKDOWN"), exist_ok=True)
        for name, content in (("config.json", "{}\n"), ("index_status.json", "{}\n"), ("search_db.js", "var SEARCH_DB = [];\n")):
            with open(os.path.join(runtime_root, name), "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)

        shutil.copytree(tess_src, os.path.join(temp_dir, "src", "Tesseract-OCR"), ignore=_ignore_tesseract_tools)
        manifest = {}
        for root, _dirs, files in os.walk(temp_dir):
            for name in files:
                path = os.path.join(root, name)
                relative = os.path.relpath(path, temp_dir).replace(os.sep, "/")
                digest = hashlib.sha256()
                with open(path, "rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                manifest[relative] = digest.hexdigest()
        with open(os.path.join(temp_dir, "MANIFEST.sha256.json"), "w", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        if os.path.exists(zip_tmp):
            os.remove(zip_tmp)
        with zipfile.ZipFile(zip_tmp, "w", zipfile.ZIP_DEFLATED) as archive:
            for root, _dirs, files in os.walk(temp_dir):
                for name in files:
                    path = os.path.join(root, name)
                    archive.write(path, os.path.relpath(path, temp_dir))
        replace_error = None
        for _attempt in range(5):
            try:
                os.replace(zip_tmp, zip_path)
                replace_error = None
                break
            except PermissionError as exc:
                replace_error = exc
                time.sleep(0.5)
        if replace_error is not None:
            raise PermissionError(f"Không thể thay thế gói cũ (có thể đang mở): {zip_path}") from replace_error
        print(f"Packaging completed successfully: {zip_path}")
        return 0
    finally:
        try:
            if os.path.exists(zip_tmp):
                os.remove(zip_tmp)
        except PermissionError:
            print(f"WARNING: Không thể xóa file tạm đang bị khóa: {zip_tmp}")
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

import os
import subprocess
import sys
import time


APP_NAME = "SuperSearch.exe"
BUILD_INPUTS = (
    "app.py",
    "index_store.py",
    "SuperSearch.spec",
    "LogoSS256.ico",
)


def run(command, cwd):
    return subprocess.run(command, cwd=cwd, shell=False)


def is_exe_locked(path):
    if not os.path.exists(path):
        return False
    try:
        with open(path, "a+b"):
            return False
    except PermissionError:
        return True


def close_running_app(force_close):
    if not force_close:
        return
    subprocess.run(
        ["taskkill", "/IM", APP_NAME, "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )
    time.sleep(1)


def needs_rebuild(exe_path, script_dir, root_dir):
    """Return whether executable inputs changed after the existing artifact."""
    if not os.path.isfile(exe_path):
        return True
    exe_mtime = os.path.getmtime(exe_path)
    input_paths = [os.path.join(script_dir, name) for name in BUILD_INPUTS]
    input_paths.append(os.path.join(root_dir, "requirements.txt"))
    return any(os.path.isfile(path) and os.path.getmtime(path) > exe_mtime for path in input_paths)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    dist_dir = os.path.join(root_dir, "build_artifacts")
    exe_path = os.path.join(dist_dir, APP_NAME)
    force_close = "--force-close" in sys.argv
    force_rebuild = "--rebuild" in sys.argv or "--force-build" in sys.argv

    if force_close:
        close_running_app(force_close=True)

    if not force_rebuild and not needs_rebuild(exe_path, script_dir, root_dir):
        print("Build skipped: executable inputs are unchanged.")
        print("UI changes are loaded from the external data\\SuperSearch.html file.")
        return 0

    if is_exe_locked(exe_path):
        print(f"ERROR: {exe_path} is still running or locked.")
        print("Close SuperSearch.exe, then run build again.")
        print("Or run: python build.py --force-close --rebuild")
        return 5

    os.makedirs(dist_dir, exist_ok=True)
    print("Building executable...")
    result = run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--distpath",
            dist_dir,
            "--workpath",
            os.path.join(script_dir, "build_temp"),
            "--noconfirm",
            os.path.join(script_dir, "SuperSearch.spec"),
        ],
        script_dir,
    )

    if result.returncode != 0:
        print("ERROR: Build failed.")
        return result.returncode

    if not os.path.isfile(exe_path):
        print(f"ERROR: Build reported success but artifact is missing: {exe_path}")
        return 6
    print(f"Done! Executable is created at: {exe_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import os
import subprocess
import sys
import time


APP_NAME = "SuperSearch.exe"


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


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    exe_path = os.path.join(root_dir, APP_NAME)
    force_close = "--force-close" in sys.argv

    if force_close:
        close_running_app(force_close=True)

    if is_exe_locked(exe_path):
        print(f"ERROR: {exe_path} is still running or locked.")
        print("Close SuperSearch.exe, then run build again.")
        print("Or run: python build.py --force-close")
        return 5

    copy_script = os.path.join(script_dir, "copy_libraries.py")
    if os.path.exists(copy_script):
        print("Copying dependencies to local Lib folder...")
        result = run([sys.executable, copy_script], script_dir)
        if result.returncode != 0:
            print("ERROR: copy_libraries.py failed.")
            return result.returncode

    print("Building executable...")
    result = run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--distpath",
            root_dir,
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

    print(f"Done! Executable is created at: {exe_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

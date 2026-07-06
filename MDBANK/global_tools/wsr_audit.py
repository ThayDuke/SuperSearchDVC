import os
import sys
import subprocess
import re

# Các chuỗi unicode đặc trưng của lỗi Mojibake (double UTF-8 encoding)
MOJIBAKE_PATTERNS = [
    (r'\u00c4\u0090', '\u00c4\u0090 (\u0110)'),
    (r'\u00c4\u0091', '\u00c4\u0091 (\u0111)'),
    (r'\u00c3\u00a1', '\u00c3\u00a1 (\u00e1)'),
    (r'\u00c3\u00a0', '\u00c3\u00a0 (\u00e0)'),
    (r'\u00c3\u00a2', '\u00c3\u00a2 (\u00e2)'),
    (r'\u00c3\u00aa', '\u00c3\u00aa (\u00ea)'),
    (r'\u00c3\u00b4', '\u00c3\u00b4 (\u00f4)'),
    (r'\u00c3\u00ba', '\u00c3\u00ba (\u00fa)'),
    (r'\u00c3\u00ad', '\u00c3\u00ad (\u00ed)'),
    (r'\u00c3\u00a3', '\u00c3\u00a3 (\u00e3)'),
    (r'\u00c3\u00b9', '\u00c3\u00b9 (\u00f9)'),
    (r'\u00e1\u00ba', '\u00e1\u00ba (diacritic)'),
    (r'\u00e1\u00bb', '\u00e1\u00bb (diacritic)'),
    (r'\u00c4\u0083', '\u00c4\u0083 (\u0103)'),
    (r'\u00c6\u00a1', '\u00c6\u00a1 (\u01a1)'),
    (r'\u00c6\u00b0', '\u00c6\u00b0 (\u01b0)')
]

def get_changed_files():
    try:
        output = subprocess.check_output(['git', 'status', '--porcelain'], stderr=subprocess.DEVNULL)
        lines = output.decode('utf-8', errors='ignore').splitlines()
        files = []
        for line in lines:
            if line.strip():
                parts = line.strip().split(maxsplit=1)
                if len(parts) > 1:
                    files.append(parts[1].replace('"', ''))
        return files
    except Exception:
        return []

def check_syntax(file_path):
    if not os.path.exists(file_path):
        return None
    
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == '.js':
            subprocess.check_output(['node', '--check', file_path], stderr=subprocess.STDOUT)
            return True, "Cú pháp JS hợp lệ"
        elif ext == '.py':
            import py_compile
            py_compile.compile(file_path, doraise=True)
            return True, "Cú pháp Python hợp lệ"
    except subprocess.CalledProcessError as e:
        return False, f"Lỗi cú pháp: {e.output.decode('utf-8', errors='ignore').strip()}"
    except Exception as e:
        return False, f"Lỗi biên dịch: {str(e)}"
    
    return None, "Không cần kiểm tra cú pháp"

def check_mojibake(file_path):
    if not os.path.exists(file_path):
        return []
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ['.md', '.html', '.css', '.js', '.py', '.txt', '.json', '.yaml', '.yml']:
        return []
        
    mojibake_found = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        for pattern, label in MOJIBAKE_PATTERNS:
            unicode_pattern = pattern.encode().decode('unicode-escape')
            matches = list(re.finditer(re.escape(unicode_pattern), content))
            if matches:
                for m in matches:
                    line_no = content[:m.start()].count('\n') + 1
                    mojibake_found.append((line_no, label))
    except Exception:
        pass
        
    return mojibake_found

def check_utf8_validity(file_path):
    if not os.path.exists(file_path):
        return []
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ['.md', '.html', '.css', '.js', '.py', '.txt', '.json', '.yaml', '.yml']:
        return []
    
    errors = []
    try:
        with open(file_path, 'rb') as f:
            bytes_content = f.read()
        text = bytes_content.decode('utf-8', errors='replace')
        if '\ufffd' in text:
            lines = text.splitlines()
            for idx, line in enumerate(lines, 1):
                if '\ufffd' in line:
                    errors.append((idx, "Ký tự lỗi mã hóa U+FFFD"))
    except Exception:
        pass
    return errors

def check_markdown_codeblocks(file_path):
    if not os.path.exists(file_path):
        return []
    ext = os.path.splitext(file_path)[1].lower()
    if ext != '.md':
        return []
    
    normalized_path = file_path.replace('\\', '/')
    if not ('.codex/' in normalized_path or 'DOCS/planning_' in normalized_path):
        return []
        
    errors = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for idx, line in enumerate(lines, 1):
            if line.strip().startswith('```') and len(line.strip()) > 3:
                lang = line.strip()[3:].lower()
                if lang in ['html', 'css', 'js', 'javascript', 'python']:
                    errors.append((idx, f"In code block {lang} trong tài liệu chat/kế hoạch"))
    except Exception:
        pass
    return errors

def check_theme_synchronization(file_path):
    if not os.path.exists(file_path):
        return []
    ext = os.path.splitext(file_path)[1].lower()
    if ext != '.css':
        return []
    
    errors = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_elegant = 'data-theme="elegant"' in content or "data-theme='elegant'" in content
        has_youth = 'not([data-theme="elegant"])' in content or "not([data-theme='elegant'])" in content
        
        if has_elegant != has_youth:
            errors.append((1, "Thiếu đồng bộ giữa Elegant và Youth theme (chỉ khai báo một phía)"))
    except Exception:
        pass
    return errors

def generate_qa_steps(changed_files):
    steps = []
    has_game_files = any('GB' in f or 'ToolGame' in f or 'HexGrid' in f for f in changed_files)
    has_rules_wsr = any('.codex' in f or 'AGENTS' in f for f in changed_files)
    
    if has_game_files:
        steps = [
            "Mở file Tools/ToolGame.html trên trình duyệt bằng cổng 6868.",
            "Chọn chế độ Game Battle (GB) và tương tác phần vừa sửa đổi.",
            "Kiểm tra xem console log có xuất hiện lỗi bất thường nào không."
        ]
    elif has_rules_wsr:
        steps = [
            "Chạy lệnh /reload hoặc /reload full để tải lại cấu hình mới.",
            "Gõ thử một câu lệnh kiểm tra (ví dụ: gõ /reload để check file loaded).",
            "Xác nhận Agent phản hồi đúng định dạng, không lặp từ."
        ]
    else:
        steps = [
            "Kiểm tra trực quan các file vừa được chỉnh sửa bằng git diff.",
            "Chạy thử ứng dụng/script cục bộ để đảm bảo không phát sinh lỗi run-time.",
            "Xác nhận các thay đổi đáp ứng đúng yêu cầu của user."
        ]
        
    return steps

def main():
    print("==================================================")
    print("   TRÌNH KIỂM THỬ TÁC ĐỘNG TỰ ĐỘNG (WSR-AUDIT)")
    print("==================================================")
    
    files = get_changed_files()
    if not files:
        print("[Thông báo]: Không tìm thấy tệp tin nào thay đổi trong Git.")
        sys.exit(0)
        
    print(f"Phát hiện {len(files)} tệp tin thay đổi.")
    
    score = 100
    has_errors = False
    details = []
    
    for f in files:
        print(f"\nAudit file: {f}")
        
        # 1. Kiểm tra cú pháp
        syntax_ok, msg = check_syntax(f)
        if syntax_ok is False:
            print(f"  - [FAIL] LỖI CÚ PHÁP: {msg}")
            score -= 50
            has_errors = True
            details.append(f"{f}: Lỗi cú pháp")
        elif syntax_ok is True:
            print(f"  - [PASS] Cú pháp: OK")
            
        # 2. Kiểm tra Mojibake
        mojibake = check_mojibake(f)
        if mojibake:
            print(f"  - [FAIL] LỖI MOJIBAKE: Phát hiện {len(mojibake)} lỗi giải mã:")
            for line, label in mojibake:
                print(f"    + Dòng {line}: Tìm thấy mẫu {label}")
            score -= 30
            has_errors = True
            details.append(f"{f}: Lỗi mojibake")
        else:
            print("  - [PASS] Mã hóa: OK")
            
        # 3. Kiểm tra UTF-8 U+FFFD
        utf8_errors = check_utf8_validity(f)
        if utf8_errors:
            print(f"  - [FAIL] LỖI U+FFFD: Phát hiện {len(utf8_errors)} lỗi thay thế ký tự:")
            for line, label in utf8_errors:
                print(f"    + Dòng {line}: {label}")
            score -= 20
            has_errors = True
            details.append(f"{f}: Ký tự lỗi U+FFFD")
        
        # 4. Kiểm tra code block trong markdown
        md_codeblocks = check_markdown_codeblocks(f)
        if md_codeblocks:
            print(f"  - [WARN] CODE BLOCK IN CHAT: Phát hiện code block trong tài liệu thiết kế:")
            for line, label in md_codeblocks:
                print(f"    + Dòng {line}: {label}")
            score -= 15
            details.append(f"{f}: Code block trong tài liệu")
        
        # 5. Kiểm tra theme Youth/Elegant (Chỉ chạy tại DEC)
        theme_errors = check_theme_synchronization(f)
        if theme_errors:
            print(f"  - [WARN] THEME SYNCHRONIZATION: {theme_errors[0][1]}")
            score -= 15
            details.append(f"{f}: Thiếu đồng bộ theme")
            
    # Giới hạn điểm không âm
    score = max(0, score)
    
    print("\n==================================================")
    print("             WSR AUDIT SCORECARD")
    print("==================================================")
    print(f"Điểm số: {score}/100")
    if score >= 80:
        status = "PASS"
    elif score >= 50:
        status = "WARN"
    else:
        status = "FAIL"
        has_errors = True
        
    print(f"Trạng thái: {status}")
    if details:
        print("Chi tiết vấn đề:")
        for det in details:
            print(f"  - {det}")
            
    print("\n==================================================")
    print("             ĐỀ XUẤT BƯỚC THỬ NGHIỆM QA")
    print("==================================================")
    qa_steps = generate_qa_steps(files)
    for i, step in enumerate(qa_steps, 1):
        print(f"{i}. {step}")
        
    if has_errors or status == "FAIL":
        print("\n[CẢNH BÁO]: Có lỗi phát sinh. Vui lòng kiểm tra lại trước khi hoàn thành!")
        sys.exit(1)
    else:
        print("\n[Thành công]: Tất cả kiểm tra tĩnh đều vượt qua sạch sẽ!")
        sys.exit(0)

if __name__ == '__main__':
    main()

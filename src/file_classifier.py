import os
import re
import datetime

from core_utils import SUPPORTED_EXTENSIONS, IMAGE_EXTENSIONS


def clean_content(content: str) -> str:
    """Strip metadata comments, base64 images, and excessive whitespace from markdown text."""
    if not content:
        return ""
    content = re.sub(r'<!--\s*ORIGINAL_PATH:.*?\s*-->', '', content)
    content = re.sub(r'<!--\s*SCAN_TARGET:.*?\s*-->', '', content)
    content = re.sub(r'<!--\s*SOURCE_SIZE:.*?\s*-->', '', content)
    content = re.sub(r'<!--\s*SOURCE_MTIME_NS:.*?\s*-->', '', content)
    content = re.sub(r'<!--\s*SOURCE_SHA256:.*?\s*-->', '', content)
    content = re.sub(r'^#\s*Converted\s+from\s+.*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'<!--\s*PAGE\s+\d+\s+\([^)]*\)\s*-->', '', content)
    content = re.sub(r'<!--\s*PAGE\s+\d+\s*-->', '', content)
    content = re.sub(r'!\[[^\]]*\]\(data:image/[^)]*\)', '', content)
    content = re.sub(r'data:image/[^\s)"\'\>]+', '', content)
    content = re.sub(r'[ \t]+', ' ', content)
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()


def is_ocr_noise(text: str) -> bool:
    """Heuristic check for corrupted or meaningless OCR character noise."""
    total_len = len(text)
    if total_len == 0:
        return True
    pipes = text.count('|')
    symbols = len(re.findall(r'[^a-zA-Z0-9\sÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ]', text))
    words = re.findall(r'\w+', text)
    symbol_ratio = symbols / total_len if total_len else 1
    if len(words) < 4 and (pipes > 8 or symbol_ratio > 0.6):
        return True
    return False


def infer_original_ext(path: str) -> str:
    """Infer original file extension from cache filename or path."""
    name = os.path.basename(path)
    if name.lower().endswith('.md'):
        name = name[:-3]
    return os.path.splitext(name)[1].lower()


def calculate_ocr_quality_score(text: str) -> float:
    """Score text quality between 0.0 and 1.0 based on dictionary tokens and symbol noise."""
    text = text or ""
    tokens = re.findall(r"[A-Za-zÀ-ỹĐđ0-9]{2,}", text)
    if not tokens:
        return 0.0
    replacement_penalty = min(0.45, text.count(chr(0xfffd)) / max(1, len(text)) * 3.0)
    symbol_count = len(re.findall(r"[^A-Za-zÀ-ỹĐđ0-9\s.,;:!?()/\\\-\[\]_%]", text))
    symbol_penalty = min(0.35, symbol_count / max(1, len(text)) * 1.5)
    short_token_penalty = min(0.35, sum(len(token) <= 2 for token in tokens) / max(1, len(tokens)) * 0.35)
    diversity_penalty = 0.0
    if len(text) >= 40:
        diversity = len(set(text.lower())) / max(1, len(text))
        diversity_penalty = min(0.45, max(0.0, 0.25 - diversity) * 2.0)
    word_signal = min(1.0, len(tokens) / max(1.0, len(text.split()) * 0.75))
    score = word_signal - replacement_penalty - symbol_penalty - short_token_penalty - diversity_penalty
    return round(max(0.0, min(1.0, score)), 3)


def classify_source(filepath: str, rel_path: str, content: str, ocr_quality_score: float) -> str:
    """Categorize document into formal_document, chat_screenshot, ui_screenshot, image_ocr, or low_confidence_ocr."""
    ext = infer_original_ext(filepath)
    content_lower = (content or "").lower()
    rel_lower = (rel_path or "").lower()

    if ocr_quality_score < 0.35:
        return "low_confidence_ocr"

    if ext in SUPPORTED_EXTENSIONS and ext not in IMAGE_EXTENSIONS:
        return "formal_document"

    if ext in IMAGE_EXTENSIONS:
        chat_patterns = [
            r'\b\d{1,2}:\d{2}\b', r'\b(am|pm)\b', 'tin nhắn',
            'đã gửi', 'hôm qua', 'hôm nay', 'chúc mừng', 'sinh nhật',
            'tăng lương', '7tr', 'triệu'
        ]
        if any(re.search(pattern, content_lower) for pattern in chat_patterns):
            return "chat_screenshot"

        ui_patterns = [
            r'\b(import|const|let|function|class)\s+\w+',
            r'</?(div|html|body|script|style)\b',
            r'\b(css|javascript|python|terminal|explorer|workspace)\b',
            r'\.(html|css|js|py|md)\b'
        ]
        if any(re.search(pattern, content_lower) for pattern in ui_patterns) or "screenshot" in rel_lower:
            return "ui_screenshot"

        return "image_ocr"

    return "formal_document"


def classify_file(filepath: str, relative_path: str) -> tuple:
    """Classify markdown file as 'Real Content', 'Empty/Near Empty', 'Empty Form Template', or 'Error Reading'."""
    try:
        size = os.path.getsize(filepath)
    except Exception:
        return "Unknown", 0, "", "", ""

    if size == 0:
        return "Empty/Near Empty", size, "", "", ""

    content = ""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        try:
            with open(filepath, 'r', encoding='latin-1', errors='ignore') as f:
                content = f.read()
        except Exception:
            return "Error Reading", size, "", "", ""

    orig_match = re.search(r'<!--\s*ORIGINAL_PATH:\s*(.*?)\s*-->', content)
    header_orig_path = orig_match.group(1).strip() if orig_match else ""
    target_match = re.search(r'<!--\s*SCAN_TARGET:\s*(.*?)\s*-->', content)
    header_scan_target = target_match.group(1).strip() if target_match else ""

    stripped_content = content.strip()
    if not stripped_content:
        return "Empty/Near Empty", size, "", header_orig_path, header_scan_target

    cleaned = clean_content(stripped_content)

    generic_phrases = [
        "cict administration documents",
        "hệ thống văn bản quản lý cict",
        "loading/unloading procedure at cict",
        "cict procedure manual",
        "hệ thống kpi cict",
        "cict kpi system"
    ]

    is_generic_cover = False
    cleaned_lower = cleaned.lower()
    if len(cleaned) < 120:
        for phrase in generic_phrases:
            if phrase in cleaned_lower:
                is_generic_cover = True
                break

    ext = infer_original_ext(header_orig_path or relative_path)
    is_image_ocr = ext in IMAGE_EXTENSIONS
    words = re.findall(r'\w+', cleaned)
    word_count = len(words)

    if "error during local" in cleaned.lower() or "error reading" in cleaned.lower():
        return "Error Reading", size, cleaned, header_orig_path, header_scan_target

    if is_image_ocr:
        if len(cleaned) < 20 or word_count < 3 or is_generic_cover:
            return "Empty/Near Empty", size, cleaned, header_orig_path, header_scan_target
    elif len(cleaned) < 50 or is_generic_cover:
        return "Empty/Near Empty", size, cleaned, header_orig_path, header_scan_target

    if is_ocr_noise(cleaned):
        return "Empty/Near Empty", size, cleaned, header_orig_path, header_scan_target

    underscores = len(re.findall(r'_{3,}', cleaned))
    dots = len(re.findall(r'\.{3,}', cleaned))
    checkboxes = len(re.findall(r'\[\s*\]', cleaned))

    placeholders = [
        r'\[tên[^\]]*\]', r'\[ngày[^\]]*\]', r'\[họ\s+và\s+tên[^\]]*\]',
        r'\[địa\s+chỉ[^\]]*\]', r'\[chức\s+vụ[^\]]*\]',
        r'\(ký,\s*ghi\s*rõ\s*họ\s*tên\)', r'\(ký\s*tên\)', r'\(nếu\s*có\)',
        r'dd/mm/yyyy', r'ngày\s+\.\.\.\s+tháng\s+\.\.\.\s+năm\s+\.\.\.\.',
        r'ngày\s+___\s+tháng\s+___\s+năm\s+___',
        r'ông/bà\s+__+', r'họ\s+tên\s*:\s*__+', r'mã\s+số\s*:\s*__+'
    ]

    placeholder_count = 0
    for p in placeholders:
        matches = re.findall(p, cleaned, re.IGNORECASE)
        if matches:
            placeholder_count += len(matches)

    total_placeholders = underscores + dots + checkboxes + placeholder_count
    density = total_placeholders / word_count if word_count > 0 else 0

    rel_path_lower = relative_path.lower()
    in_biem_mau = bool(re.search(r'\b(form|forms|draft|drafts)\b', rel_path_lower)) or "biểu mẫu" in rel_path_lower
    is_policy_name = any(kw in relative_path for kw in ["Quy chế", "Quy trình", "Nội quy", "Sổ tay", "Hướng dẫn", "Regulations", "Procedure", "Manual", "Plan", "Chính sách"])

    is_template = False
    if is_policy_name and not in_biem_mau:
        if word_count < 150:
            is_template = True
    else:
        if in_biem_mau:
            if word_count < 200:
                if total_placeholders > 1 or density > 0.02:
                    is_template = True
            else:
                if density > 0.15:
                    is_template = True
        else:
            if word_count < 250:
                if total_placeholders > 5 or density > 0.05:
                    is_template = True
            else:
                if density > 0.25:
                    is_template = True

    if "họ và tên" in cleaned_lower and "ngày sinh" in cleaned_lower and word_count < 120 and (underscores > 1 or dots > 1):
        is_template = True

    if is_template:
        return "Empty Form Template", size, cleaned, header_orig_path, header_scan_target

    return "Real Content", size, cleaned, header_orig_path, header_scan_target


def detect_domain(filepath: str, rel_path: str, content_lower: str) -> str:
    """Classify functional domain from filepath and content."""
    rel_path_lower = rel_path.lower()
    if "it" in rel_path_lower or "công nghệ" in rel_path_lower or "software" in rel_path_lower or "system" in rel_path_lower:
        return "IT (Công nghệ thông tin)"
    if "safety" in rel_path_lower or "hsse" in rel_path_lower or "hse" in rel_path_lower or "ehs" in rel_path_lower or "pccc" in rel_path_lower or "cnch" in rel_path_lower or "bảo hộ lao động" in content_lower:
        return "HSSE (An toàn, Môi trường, An ninh)"
    if "kpi" in rel_path_lower or "okr" in rel_path_lower or "kpi" in content_lower or "okr" in content_lower:
        return "KPI & OKR (Quản trị hiệu suất)"
    if "hr" in rel_path_lower or "admin" in rel_path_lower or "nhân sự" in rel_path_lower or "hành chính" in rel_path_lower or "lao động" in content_lower:
        return "HR & Admin (Nhân sự & Hành chính)"
    if "operation" in rel_path_lower or "ops" in rel_path_lower or "khai thác" in rel_path_lower or "vận hành" in rel_path_lower or "sản xuất" in rel_path_lower or "logistics" in rel_path_lower or "kho bãi" in rel_path_lower:
        return "Operation (Vận hành & Khai thác)"
    if "finance" in rel_path_lower or "acc" in rel_path_lower or "kế toán" in rel_path_lower or "tài chính" in rel_path_lower or "chi tiêu" in rel_path_lower or "tạm ứng" in rel_path_lower:
        return "Finance & Accounting (Tài chính - Kế toán)"
    if "marketing" in rel_path_lower or "mkt" in rel_path_lower or "khách hàng" in rel_path_lower or "sales" in rel_path_lower or "kinh doanh" in rel_path_lower or "truyền thông" in content_lower:
        return "Marketing & Sales (Tiếp thị & Chăm sóc khách hàng)"

    if "công nghệ thông tin" in content_lower or "phần mềm" in content_lower or "máy tính" in content_lower:
        return "IT (Công nghệ thông tin)"
    if "an toàn lao động" in content_lower or "phòng cháy" in content_lower or "môi trường" in content_lower:
        return "HSSE (An toàn, Môi trường, An ninh)"
    if "vận hành" in content_lower or "quy trình vận hành" in content_lower:
        return "Operation (Vận hành & Khai thác)"

    return "Khác / Chung"


def detect_doc_type(filepath: str, rel_path: str, content_lower: str) -> str:
    """Classify document format/type from filename and content."""
    filename_lower = os.path.basename(filepath).lower()
    if any(kw in filename_lower or kw in content_lower[:1000] for kw in ["quy chế", "quy chế chi tiêu", "chính sách", "policy", "regulations"]):
        return "Quy chế / Chính sách"
    if any(kw in filename_lower or kw in content_lower[:1000] for kw in ["quy trình", "hướng dẫn", "sổ tay", "procedure", "manual", "guide", "sổ tay kế toán", "sổ tay quản lý"]):
        return "Quy trình / Hướng dẫn"
    if any(kw in filename_lower or kw in content_lower[:1000] for kw in ["quyết định", "biên bản", "nghị quyết", "minutes", "resolution", "decision"]):
        return "Quyết định / Biên bản"
    if any(kw in filename_lower or kw in content_lower[:1000] for kw in ["hợp đồng", "báo giá", "contract", "quotation"]):
        return "Hợp đồng / Báo giá"

    return "Tài liệu nghiệp vụ / Báo cáo"


def detect_language(content_lower: str) -> str:
    """Detect language of content (Vietnamese, English, or Bilingual)."""
    en_words = len(re.findall(r'\b(the|and|of|procedure|version|signed|date|page|report|manual|document|policy)\b', content_lower))
    vn_chars = len(re.findall(r'[áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]', content_lower))
    if en_words > 15 and vn_chars < 10:
        return "Tiếng Anh (EN)"
    elif vn_chars > 30 and en_words < 5:
        return "Tiếng Việt (VN)"
    elif en_words > 5 and vn_chars > 10:
        return "Song ngữ (EN/VN)"
    return "Tiếng Việt (VN)"


def get_file_creation_parts(path: str) -> tuple:
    """Return the source file CreationTime parts (year, month)."""
    try:
        stat = os.stat(path)
        birthtime = getattr(stat, "st_birthtime", None)
        if birthtime is None or birthtime <= 0:
            return 0, 0
        created_at = datetime.datetime.fromtimestamp(birthtime)
        return created_at.year, created_at.month
    except (AttributeError, OSError, OverflowError, ValueError, TypeError):
        return 0, 0

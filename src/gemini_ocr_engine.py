"""Gemini OCR Engine for SuperSearch.

Provides cloud-assisted OCR using Google Gemini API (gemini-2.5-flash, gemini-2.5-pro)
with zero external dependencies (Python standard library only).
Inherits prompt design & math preservation protocols from Looking-Back-OCR.
"""

import base64
import json
import random
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_OCR_INSTRUCTION = """Bạn là một Chuyên gia Số hóa Tài liệu và Kỹ sư OCR hàng đầu.
Nhiệm vụ của bạn là: Trích xuất chính xác 100% toàn bộ nội dung từ ảnh / trang tài liệu scan đính kèm sang định dạng Markdown sạch, trung thực với nguyên tác.

QUY TẮC BẮT BUỘC:
1. TRUNG THỰC NGUYÊN TÁC & CHỐNG BỊA CHỮ: Trích xuất chính xác 100% từng từ ngữ, số liệu, bảng biểu. Không tóm tắt, không suy đoán. Nếu gặp chữ bị rách mờ, mất nét KHÔNG THỂ đọc chính xác, bắt buộc dùng ký hiệu [?] thay vì bịa chữ.
2. CHÍNH TẢ VÀ TỪ GHÉP CỔ: Giữ nguyên các dấu gạch nối ngữ nghĩa trong từ ghép tiếng Việt thời kỳ Quốc ngữ cổ (ví dụ: "bản-báo", "thiết-tưởng", "công-luận", "quốc-ngữ").
3. NỐI DÒNG MƯỢT MÀ & DROP CAPS: Ghép các từ bị bẻ đôi do hết dòng vật lý (soft-hyphen) thành từ hoàn chỉnh (ví dụ: "lịch-\\n sử" thành "lịch sử"). Chữ cái nghệ thuật đầu đoạn (Drop caps) ghép liền mạch với từ tương ứng.
4. BỐ CỤC ĐA CỘT (MULTI-COLUMN FLOW): Nếu tài liệu in 2 hoặc 3 cột (báo chí, tạp chí, từ điển, công văn), hãy đọc trọn vẹn từng cột theo đúng thứ tự logic tự nhiên của bài viết và gộp thành một luồng đọc duy nhất, tuyệt đối không quét ngang làm đảo lộn ngữ nghĩa giữa các cột.
5. LOẠI BỎ TẠP ÂM SCAN VẬT LÝ (DOCUMENT DENOISING):
   - Loại bỏ bóng tối gáy sách (gutter shadow), mép giấy cong (page curl).
   - Khử triệt để đốm ố vàng (foxing), vết ẩm mốc, vệt rỉ bấm kim, vết băng dính, bóng ngón tay giữ sách.
   - Khử chữ thấu quang / hằn từ mặt sau (bleed-through / show-through) của trang giấy mỏng.
   - Bỏ qua chữ viết tay ngoài lề (marginalia), dấu mộc thư viện, tem lưu trữ, barcode.
   - Bỏ qua running header / footer lặp lại cơ học và số trang ở các trang ruột, NHƯNG BẢO TỒN 100% thông tin tiêu đề tại trang bìa hoặc trang nhất của ấn phẩm.
6. THƠ CA & VĂN BẢN ĐẶC THÙ: Bắt buộc giữ nguyên ngắt dòng của từng câu thơ (lục bát, song thất lục bát, thơ tự do). Đặt khối thơ trong khối trích dẫn > để hiển thị thẩm mỹ.
7. CHÚ THÍCH (FOOTNOTES): Đánh dấu vị trí tham chiếu bằng [^1], [^2] trong thân bài và gom nội dung giải nghĩa [^1]: ... ở cuối trang.
8. CÔNG THỨC TOÁN HỌC: Biểu thức toán cùng dòng dùng cú pháp \\( ... \\). Phương trình khối đứng riêng dùng cú pháp \\[ ... \\]. Không bọc trong thẻ code hay pre.
9. BẢNG BIỂU: Chuyển đổi bảng biểu sang cú pháp bảng Markdown chuẩn (| Cột 1 | Cột 2 |).
10. CHỮ HÁN NÔM: Nhận diện chính xác ký tự chữ Hán, chữ Nôm nguyên tác (bao gồm cả chữ Hán - Nôm đi liền sau từ Quốc ngữ).
11. ĐẦU RA TINH GỌN: Chỉ trả về nội dung Markdown trích xuất được. Tuyệt đối không thêm lời chào, phần giới thiệu hay giải thích thừa."""


class GeminiQuotaExhaustedError(RuntimeError):
    """Ngoại lệ khi Gemini API vượt hạn ngạch 429 hoặc cạn kiệt ngạch ngày."""
    pass


class GeminiQuotaManager:
    """Điều phối hạn ngạch gọi Gemini API với cơ chế pacing và lùi nhịp lũy thừa."""

    def __init__(self, min_interval: float = 1.0, max_retries: int = 3, base_backoff: float = 2.0):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self._last_call_time = 0.0
        self._lock = threading.Lock()
        self.quota_exhausted = False
        self.exhausted_until = 0.0

    def wait_for_slot(self):
        with self._lock:
            now = time.time()
            if self.quota_exhausted:
                if now < self.exhausted_until:
                    raise GeminiQuotaExhaustedError(
                        "Gemini API quota đang bị khóa tạm thời do lỗi 429 liên tiếp."
                    )
                else:
                    self.quota_exhausted = False
            elapsed = now - self._last_call_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_call_time = time.time()

    def record_exhaustion(self, cooldown_seconds: float = 60.0):
        with self._lock:
            self.quota_exhausted = True
            self.exhausted_until = time.time() + cooldown_seconds

    def reset(self):
        with self._lock:
            self.quota_exhausted = False
            self.exhausted_until = 0.0


GLOBAL_QUOTA_MANAGER = GeminiQuotaManager()


def _clean_markdown_fence(text: str) -> str:
    """Strip markdown wrapping ```markdown ... ``` if returned by the model."""
    if not text:
        return ""
    text = text.strip()
    match = re.match(r"^```(?:markdown|md|text)?\s*\n([\s\S]*?)\n```$", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def call_gemini_api(
    api_key: str,
    parts: list,
    model: str = DEFAULT_GEMINI_MODEL,
    system_instruction: str = SYSTEM_OCR_INSTRUCTION,
    timeout: int = 45,
    quota_manager: GeminiQuotaManager = None,
) -> str:
    """Executes a request to Google Gemini API via standard library urllib with Quota Manager."""
    clean_key = (api_key or "").strip()
    if not clean_key:
        raise ValueError("Chưa cung cấp Gemini API Key.")

    effective_model = (model or "").strip() or DEFAULT_GEMINI_MODEL
    url = f"{GEMINI_API_ENDPOINT.format(model=effective_model)}?key={urllib.parse.quote(clean_key)}"

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
        },
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    data = json.dumps(payload).encode("utf-8")
    context = ssl.create_default_context()
    qm = quota_manager or GLOBAL_QUOTA_MANAGER
    max_retries = qm.max_retries

    for attempt in range(max_retries + 1):
        qm.wait_for_slot()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, context=context, timeout=timeout) as response:
                res_bytes = response.read()
                res_json = json.loads(res_bytes.decode("utf-8"))
            break
        except urllib.error.HTTPError as http_err:
            err_body = ""
            try:
                err_body = http_err.read().decode("utf-8")
                err_json = json.loads(err_body)
                msg = err_json.get("error", {}).get("message", err_body)
                status = err_json.get("error", {}).get("status", "")
            except Exception:
                msg = str(http_err.reason)
                status = ""

            if http_err.code == 429:
                if attempt < max_retries:
                    retry_after = http_err.headers.get("Retry-After") if hasattr(http_err, "headers") else None
                    if retry_after and retry_after.strip().isdigit():
                        backoff = float(retry_after.strip()) + random.uniform(0.2, 0.8)
                    else:
                        backoff = (qm.base_backoff * (2 ** attempt)) + random.uniform(0.3, 1.2)
                    time.sleep(backoff)
                    continue
                else:
                    qm.record_exhaustion(cooldown_seconds=60.0)
                    raise GeminiQuotaExhaustedError(
                        f"Gemini API vượt ngưỡng hạn ngạch 429 sau {max_retries} lần thử lại: {msg}"
                    )
            raise RuntimeError(f"Gemini API Error (HTTP {http_err.code} {status}): {msg}")
        except urllib.error.URLError as url_err:
            raise RuntimeError(f"Lỗi kết nối mạng tới Gemini API: {url_err.reason}")

    candidates = res_json.get("candidates") or []
    if not candidates:
        block_reason = res_json.get("promptFeedback", {}).get("blockReason")
        if block_reason:
            raise RuntimeError(f"Tài liệu bị Gemini chặn xử lý: {block_reason}")
        raise RuntimeError("Gemini không trả về kết quả nào.")

    candidate = candidates[0]
    finish_reason = candidate.get("finishReason")
    if finish_reason and finish_reason not in ("STOP", "MAX_TOKENS"):
        raise RuntimeError(f"Gemini hoàn tất không bình thường: {finish_reason}")

    content_parts = candidate.get("content", {}).get("parts") or []
    out_text = "".join(part.get("text", "") for part in content_parts if "text" in part)
    return _clean_markdown_fence(out_text)


def ocr_image_bytes(
    img_bytes: bytes,
    api_key: str,
    model: str = DEFAULT_GEMINI_MODEL,
    mime_type: str = "image/png",
    custom_prompt: str = "Trích xuất toàn bộ văn bản từ hình ảnh scan này sang Markdown sạch.",
    quota_manager: GeminiQuotaManager = None,
) -> str:
    """Performs OCR on image bytes using Gemini API with Quota Manager."""
    if not img_bytes:
        return ""
    b64_data = base64.b64encode(img_bytes).decode("ascii")
    parts = [
        {
            "inlineData": {
                "mimeType": mime_type,
                "data": b64_data,
            }
        },
        {"text": custom_prompt},
    ]
    return call_gemini_api(api_key, parts, model=model, quota_manager=quota_manager)


def ocr_pdf_page_bytes(
    page_img_bytes: bytes,
    page_num: int,
    api_key: str,
    model: str = DEFAULT_GEMINI_MODEL,
    mime_type: str = "image/jpeg",
    quota_manager: GeminiQuotaManager = None,
) -> str:
    """Performs OCR on a rendered PDF page image using Gemini API with Quota Manager."""
    prompt = f"Trích xuất văn bản từ trang {page_num} của tài liệu scan sang Markdown. Bảo tồn công thức toán và bảng biểu."
    return ocr_image_bytes(
        page_img_bytes,
        api_key=api_key,
        model=model,
        mime_type=mime_type,
        custom_prompt=prompt,
        quota_manager=quota_manager,
    )


def test_gemini_connection(api_key: str, model: str = DEFAULT_GEMINI_MODEL) -> tuple[bool, str]:
    """Verifies API key and model connectivity with a lightweight ping query."""
    try:
        clean_key = (api_key or "").strip()
        if not clean_key:
            return False, "Khóa API Key không được để trống."
        parts = [{"text": "Xin chào, hãy phản hồi 'OK' để xác nhận kết nối."}]
        res = call_gemini_api(
            clean_key,
            parts,
            model=model,
            system_instruction="Chỉ phản hồi chữ OK ngắn gọn.",
            timeout=15,
        )
        return True, f"Kết nối Gemini API thành công! Mô hình: {model or DEFAULT_GEMINI_MODEL}"
    except Exception as exc:
        return False, str(exc)

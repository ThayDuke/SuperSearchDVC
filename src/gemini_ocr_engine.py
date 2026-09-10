"""Gemini OCR Engine for SuperSearch.

Provides cloud-assisted OCR using Google Gemini API (gemini-2.5-flash, gemini-2.5-pro)
with zero external dependencies (Python standard library only).
Inherits prompt design & math preservation protocols from Looking-Back-OCR.
"""

import base64
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_OCR_INSTRUCTION = """Bạn là một Chuyên gia Số hóa Tài liệu và Kỹ sư OCR hàng đầu.
Nhiệm vụ của bạn là: Trích xuất chính xác 100% toàn bộ nội dung từ ảnh / trang tài liệu scan đính kèm sang định dạng Markdown sạch, trung thực với nguyên tác.

QUY TẮC BẮT BUỘC:
1. TRUNG THỰC VỚI NGUYÊN TÁC: Trích xuất chính xác từng từ ngữ, số liệu, bảng biểu. Không tóm tắt, không bịa đặt, không bỏ sót nội dung.
2. CHÍNH TẢ VÀ TỪ GHÉP CỔ: Giữ nguyên các dấu gạch nối ngữ nghĩa trong từ ghép tiếng Việt cổ (ví dụ: "bản-báo", "thiết-tưởng", "công-luận", "quốc-ngữ").
3. NỐI DÒNG MƯỢT MÀ: Ghép các từ bị bẻ đôi do hết dòng vật lý (soft-hyphen) thành từ hoàn chỉnh. Dòng chảy văn bản liền mạch giữa các đoạn.
4. CÔNG THỨC TOÁN HỌC: Biểu thức toán cùng dòng dùng cú pháp \\( ... \\). Phương trình khối đứng riêng dùng cú pháp \\[ ... \\]. Không bọc trong thẻ code hay pre.
5. BẢNG BIỂU: Chuyển đổi bảng biểu sang cú pháp bảng Markdown chuẩn (| Cột 1 | Cột 2 |).
6. CHỮ HÁN NÔM: Nhận diện chính xác ký tự chữ Hán, chữ Nôm nguyên tác.
7. ĐẦU RA TINH GỌN: Chỉ trả về nội dung Markdown trích xuất được. Tuyệt đối không thêm lời chào, phần giới thiệu hay giải thích thừa."""


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
) -> str:
    """Executes a request to Google Gemini API via standard library urllib."""
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
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=context, timeout=timeout) as response:
            res_bytes = response.read()
            res_json = json.loads(res_bytes.decode("utf-8"))
    except urllib.error.HTTPError as http_err:
        err_body = ""
        try:
            err_body = http_err.read().decode("utf-8")
            err_json = json.loads(err_body)
            msg = err_json.get("error", {}).get("message", err_body)
            status = err_json.get("error", {}).get("status", "")
            raise RuntimeError(f"Gemini API Error (HTTP {http_err.code} {status}): {msg}")
        except Exception:
            raise RuntimeError(f"Gemini API Error (HTTP {http_err.code}): {http_err.reason} {err_body}")
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
) -> str:
    """Performs OCR on image bytes using Gemini API."""
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
    return call_gemini_api(api_key, parts, model=model)


def ocr_pdf_page_bytes(
    page_img_bytes: bytes,
    page_num: int,
    api_key: str,
    model: str = DEFAULT_GEMINI_MODEL,
    mime_type: str = "image/jpeg",
) -> str:
    """Performs OCR on a rendered PDF page image using Gemini API."""
    prompt = f"Trích xuất văn bản từ trang {page_num} của tài liệu scan sang Markdown. Bảo tồn công thức toán và bảng biểu."
    return ocr_image_bytes(
        page_img_bytes,
        api_key=api_key,
        model=model,
        mime_type=mime_type,
        custom_prompt=prompt,
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

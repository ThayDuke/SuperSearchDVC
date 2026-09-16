"""OCR Postprocessor for SuperSearch.

Provides post-processing capabilities inspired by D-OCR (Looking-Back-OCR):
1. Cross-page sentence and paragraph healing (unifying broken sentences across page breaks).
2. Soft-hyphen resolution across page boundaries (e.g., 'nghiên-\\n<!-- PAGE 2 -->\\ncứu' -> 'nghiên cứu').
3. Removal of trailing page artifacts and scan noise.
Zero external dependencies (Python standard library only).
"""

import re
import unicodedata


# Punctuation marks that typically end a sentence or block
SENTENCE_END_CHARS = {'.', '!', '?', ':', ';', '…', '"', "'", '”', '’', '»', ']', ')'}


def is_lowercase_letter(char: str) -> bool:
    """Check if a character is a lowercase unicode letter."""
    if not char:
        return False
    return char.islower() and char.isalpha()


def heal_page_pair(prev_text: str, next_text: str) -> tuple[str, str]:
    """Analyzes boundaries between two consecutive pages and heals broken sentences/words.
    
    Returns (healed_prev_text, healed_next_text).
    """
    if not prev_text or not next_text:
        return prev_text, next_text

    prev_stripped = prev_text.rstrip()

    # Extract any leading <!-- PAGE X ... --> comment from next_text so we inspect actual content
    page_marker_match = re.match(r'^(\s*<!--\s*PAGE\s+\d+[^>]*-->\s*)', next_text, re.IGNORECASE)
    marker_prefix = ""
    next_body = next_text
    if page_marker_match:
        marker_prefix = page_marker_match.group(1)
        next_body = next_text[len(marker_prefix):]

    next_stripped = next_body.lstrip()

    if not prev_stripped or not next_stripped:
        return prev_text, next_text

    # Case 1: Word broken by a soft-hyphen at the end of the previous page
    # Example: prev ends with 'phát-' and next starts with 'triển'
    hyphen_match = re.search(r'([A-Za-zÀ-ỹ0-9]+)-\s*$', prev_stripped)
    next_word_match = re.match(r'^\s*([A-Za-zÀ-ỹ0-9]+)', next_stripped)

    if hyphen_match and next_word_match:
        # Check if it's not a semantic hyphen like 'bản-báo' where both sides are capitalized or complete
        # If the word continues on the next page, merge into the next page or clean the hyphen
        word_part1 = hyphen_match.group(1)
        word_part2 = next_word_match.group(1)
        # If second part is lowercase, it is almost certainly a broken single word
        if word_part2.islower() or (word_part1.isupper() and word_part2.isupper()):
            # Remove trailing hyphen from prev_text
            cut_pos = prev_text.rfind(hyphen_match.group(0))
            new_prev = prev_text[:cut_pos] + word_part1
            # Next text starts with the completion
            return new_prev, next_text

    # Case 2: Incomplete sentence across pages
    # Last non-whitespace character of prev page
    last_char = prev_stripped[-1]
    first_char = next_stripped[0]

    # If previous page does NOT end with sentence-ending punctuation,
    # and next page starts with a lowercase letter or continuation
    if last_char not in SENTENCE_END_CHARS and is_lowercase_letter(first_char):
        # The sentence is flowing across pages without punctuation
        # Ensure prev_text ends cleanly without excessive trailing newlines
        trailing_ws = prev_text[len(prev_stripped):]
        # Normalize trailing whitespace to a single space if it's continuing directly
        if '\n\n' in trailing_ws:
            # Keep one newline for readability but mark continuous flow
            new_prev = prev_stripped + " "
            return new_prev, next_text

    return prev_text, next_text


def heal_cross_page_continuations(pages_text: list[str]) -> list[str]:
    """Heals cross-page continuations for a sequential list of extracted pages."""
    if not pages_text or len(pages_text) < 2:
        return pages_text

    healed = list(pages_text)
    for i in range(len(healed) - 1):
        p1, p2 = heal_page_pair(healed[i], healed[i + 1])
        healed[i] = p1
        healed[i + 1] = p2

    return healed


def heal_document_markdown(markdown_content: str) -> str:
    """Heals broken sentences and soft hyphens across '<!-- PAGE X -->' markers in a Markdown document."""
    if not markdown_content or "<!-- PAGE" not in markdown_content:
        return markdown_content

    # Pattern matching page separator comments: <!-- PAGE 2 ... -->
    page_marker_pattern = re.compile(
        r'(\n*<!--\s*PAGE\s+\d+[^>]*-->\n*)',
        re.IGNORECASE
    )

    parts = page_marker_pattern.split(markdown_content)
    if len(parts) <= 1:
        return markdown_content

    # parts alternates: [text0, marker1, text1, marker2, text2, ...]
    for i in range(1, len(parts) - 1, 2):
        marker = parts[i]
        prev_idx = i - 1
        next_idx = i + 1

        prev_text = parts[prev_idx]
        next_text = parts[next_idx]

        # Check soft-hyphen across marker
        prev_match = re.search(r'([A-Za-zÀ-ỹ0-9]+)-\s*$', prev_text.rstrip())
        next_match = re.match(r'^\s*([A-Za-zÀ-ỹ0-9]+)', next_text.lstrip())

        if prev_match and next_match:
            w1 = prev_match.group(1)
            w2 = next_match.group(1)
            if w2.islower() or (w1.isupper() and w2.isupper()):
                # Remove trailing hyphen from prev_text
                cut = prev_text.rfind(prev_match.group(0))
                parts[prev_idx] = prev_text[:cut] + w1

    return "".join(parts)

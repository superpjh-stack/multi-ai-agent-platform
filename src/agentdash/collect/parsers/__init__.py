"""원천 파서 (spec.md §2.1 S1~S6). 본문(message.content 의 텍스트 · thinking · 도구 결과 · 입력 command/prompt/content)은
꺼내지 않는다 — 이름 · 경로 · 도구 이름 · 숫자 · 설명 앞 120 자만."""


class ParseError(ValueError):
    """필수 필드가 없거나 JSON 이 깨진 원천 — parse_error 로 쌓는다 (조용한 실패 금지)."""

"""GIFT format parser for Moodle-compatible quiz import.

GIFT format reference: https://docs.moodle.org/en/GIFT_format
Supported types: Multiple Choice (MC), True/False, Short Answer, Essay
"""

import re
from typing import Any


def parse_gift(gift_text: str) -> list[dict[str, Any]]:
    """Parse GIFT format string into list of question dicts.

    Each question dict has keys:
      - question: str (plain text question body)
      - type: str ("Choices" | "True/False" | "Short Answer" | "Essay")
      - marks: float
      - multiple: bool (for MCQ with >1 correct)
      - option_1..option_4: str
      - is_correct_1..is_correct_4: bool
    """
    questions = []
    # Match ::title:: question body { options }
    pattern = re.compile(
        r"::(?P<title>[^:]+)::\s*(?P<body>.*?)\s*\{\s*(?P<options>[^}]+)\s*}\s*",
        re.DOTALL,
    )

    for match in pattern.finditer(gift_text.strip()):
        title = match.group("title").strip()
        body = match.group("body").strip()
        options_text = match.group("options").strip()

        q = _parse_options(title or body, body, options_text)
        if q:
            questions.append(q)

    return questions


def _parse_options(title: str, body: str, options_text: str) -> dict[str, Any] | None:
    lines = [l.strip() for l in options_text.split("\n") if l.strip()]
    if not lines:
        return None

    # Detect type
    is_truefalse = len(lines) == 2 and all(l in ("TRUE", "FALSE", "T", "F") for l in [l.strip("=").strip("~").strip() for l in lines]) if False else False  # noqa

    # Check for TRUE/FALSE
    cleaned = []
    for l in lines:
        l = l.strip()
        if l in ("TRUE", "FALSE", "T", "F", "TRUE.", "FALSE."):
            cleaned.append(l.rstrip("."))
        else:
            cleaned.append(l)
    lines = cleaned

    # Detect type from answer patterns
    is_tf = False
    if len(lines) == 1 and lines[0].lstrip("=~").strip() in ("TRUE", "FALSE", "T", "F"):
        is_tf = True

    if is_tf:
        correct = lines[0].startswith("=")
        answer = lines[0].lstrip("=~").strip().upper()
        return {
            "question": body or title,
            "type": "True/False",
            "marks": 1,
            "multiple": False,
            "option_1": "TRUE",
            "option_2": "FALSE",
            "is_correct_1": correct and answer == "TRUE",
            "is_correct_2": correct and answer == "FALSE",
            "is_correct_3": False,
            "is_correct_4": False,
        }

    # Split options into MC choices
    options = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        prefix = line[0] if line else ""
        text = line[1:].strip() if prefix in ("=", "~") else line
        is_correct = prefix == "="
        options.append({"text": text, "correct": is_correct})

    if not options:
        return None

    # Short Answer = one correct answer, no wrong options
    has_wrong = any(not o["correct"] for o in options)

    if not has_wrong and len(options) == 1:
        return {
            "question": body or title,
            "type": "Short Answer",
            "marks": 1,
            "multiple": False,
            "option_1": options[0]["text"],
            "is_correct_1": True,
            "is_correct_2": False,
            "is_correct_3": False,
            "is_correct_4": False,
        }

    # MC or Multiple answer
    correct_count = sum(1 for o in options if o["correct"])
    is_multiple = correct_count > 1

    # Pad to 4 options
    while len(options) < 4:
        options.append({"text": "", "correct": False})

    result = {
        "question": body or title,
        "type": "Choices",
        "marks": 1,
        "multiple": is_multiple,
    }
    for i, opt in enumerate(options[:4]):
        result[f"option_{i+1}"] = opt["text"]
        result[f"is_correct_{i+1}"] = opt["correct"]
        result[f"possibility_{i+1}"] = ""
        result[f"explanation_{i+1}"] = ""

    return result

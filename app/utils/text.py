from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime
from typing import Any


STOPWORDS = {
    "根据",
    "关于",
    "以及",
    "有关",
    "工作",
    "通知",
    "推进",
    "开展",
    "企业",
    "项目",
    "政策",
    "双碳",
}

REGION_PATTERN = re.compile(
    r"(北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|海南|四川|贵州|云南|陕西|甘肃|青海|台湾|内蒙古自治区|广西壮族自治区|西藏自治区|宁夏回族自治区|新疆维吾尔自治区|香港特别行政区|澳门特别行政区)[省市自治区特别行政区]*"
)
DATE_PATTERNS = [
    re.compile(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?"),
    re.compile(r"(20\d{2})(\d{2})(\d{2})"),
]



def clean_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()



def simple_token_count(text: str) -> int:
    return max(1, len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text)))



def extract_keywords(text: str, limit: int = 8) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", text)
    filtered = [token for token in tokens if token not in STOPWORDS]
    return [item for item, _ in Counter(filtered).most_common(limit)]



def infer_title(text: str, fallback: str = "未命名文档") -> str:
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line[:120]
    return fallback



def extract_first_date(text: str) -> date | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        year, month, day = [int(item) for item in match.groups()]
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return None



def extract_region(text: str) -> str | None:
    match = REGION_PATTERN.search(text)
    if match:
        value = match.group(0)
        if value.endswith(("省", "市", "自治区", "特别行政区")):
            return value
        if value in {"北京", "天津", "上海", "重庆"}:
            return f"{value}市"
        if value.endswith("自治区") or value.endswith("特别行政区"):
            return value
        return f"{value}省"
    return None



def parse_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None

    code_fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_fence_match:
        text = code_fence_match.group(1)
    else:
        brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None



def format_date(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()

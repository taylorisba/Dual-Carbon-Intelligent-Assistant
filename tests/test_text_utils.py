from app.utils.text import clean_text, extract_first_date, extract_region



def test_clean_text_normalizes_whitespace():
    assert clean_text("a   b\n\n\n c") == "a b\n\n c"



def test_extract_date_and_region():
    text = "发布日期：2025-03-01，江苏省制造业节能降碳通知"
    assert extract_first_date(text).isoformat() == "2025-03-01"
    assert extract_region(text) == "江苏省"

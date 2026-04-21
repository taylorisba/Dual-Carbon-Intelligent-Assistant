from app.utils.chunking import chunk_text



def test_chunk_text_keeps_section_and_overlap():
    text = """# 标题\n\n## 一、总则\n""" + "节能降碳" * 200
    chunks = chunk_text(text, chunk_size=80, overlap=10)

    assert len(chunks) >= 2
    assert all(chunk.section_path for chunk in chunks)
    assert chunks[0].content

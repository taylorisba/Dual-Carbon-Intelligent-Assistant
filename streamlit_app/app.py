from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="双碳智能问答系统", layout="wide")

if "api_base_url" not in st.session_state:
    st.session_state.api_base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
if "config_notice" not in st.session_state:
    st.session_state.config_notice = None



def api_request(method: str, path: str, **kwargs) -> requests.Response:
    url = st.session_state.api_base_url.rstrip("/") + path
    response = requests.request(method, url, timeout=300, **kwargs)
    response.raise_for_status()
    return response



def render_chat_page() -> None:
    st.title("智能问答")
    question = st.text_area("请输入政策咨询问题", height=120, value="首批国家碳达峰试点名额安排的省份有哪些？")
    col1, col2 = st.columns(2)
    region = col1.text_input("地区", value="")
    industry = col2.text_input("行业", value="")

    if st.button("提交问答", use_container_width=True):
        try:
            payload = {
                "question": question,
                "region": region or None,
                "industry": industry or None,
                "use_query_rewrite": True,
                "include_debug": True,
            }
            data = api_request("POST", "/api/v1/chat/query", json=payload).json()
            st.subheader("回答")
            st.write(data["answer"])
            st.caption(f"confidence: {data['confidence']} | risk_note: {data['risk_note']}")

            st.subheader("引用来源")
            if data["citations"]:
                st.dataframe(pd.DataFrame(data["citations"]), use_container_width=True)
            else:
                st.info("暂无引用")

            if data.get("debug"):
                with st.expander("检索调试信息"):
                    st.dataframe(pd.DataFrame(data["debug"]["retrieved_chunks"]), use_container_width=True)
        except Exception as exc:
            st.error(f"调用失败: {exc}")



def render_report_page() -> None:
    st.title("报告背景生成")
    with st.form("report_form"):
        report_type = st.text_input("报告类型", value="城乡建设领域碳达峰实施方案")
        col1, col2 = st.columns(2)
        region = col1.text_input("地区", value="")
        industry = col2.text_input("行业", value="")
        project_name = st.text_input("项目名称", value="城乡建设领域碳达峰实施方案")
        project_summary = st.text_area(
            "项目概况",
            value="城乡建设是碳排放的主要领域之一。随着城镇化快速推进和产业结构深度调整，城乡建设领域碳排放量及其占全社会碳排放总量比例均将进一步提高。为深入贯彻落实党中央、国务院关于碳达峰碳中和决策部署，控制城乡建设领域碳排放量增长，切实做好城乡建设领域碳达峰工作，根据《中共中央 国务院关于完整准确全面贯彻新发展理念做好碳达峰碳中和工作的意见》、《2030年前碳达峰行动方案》，制定本实施方案。",
            height=160,
        )
        mode = st.radio("生成模式", ["draft", "formal"], horizontal=True)
        submitted = st.form_submit_button("生成背景")

    if submitted:
        try:
            payload = {
                "report_type": report_type,
                "region": region or None,
                "industry": industry or None,
                "project_name": project_name,
                "project_summary": project_summary,
                "mode": mode,
            }
            data = api_request("POST", "/api/v1/report/background", json=payload).json()
            st.subheader("生成结果")
            st.markdown(data["content"])
            st.caption(data["risk_note"])
            st.subheader("引用来源")
            if data["citations"]:
                st.dataframe(pd.DataFrame(data["citations"]), use_container_width=True)
            else:
                st.info("暂无引用")
        except Exception as exc:
            st.error(f"调用失败: {exc}")



def render_knowledge_page() -> None:
    st.title("知识库导入与同步")

    st.subheader("文档列表")
    try:
        docs = api_request("GET", "/api/v1/documents").json()
        if docs:
            st.dataframe(pd.DataFrame(docs), use_container_width=True)
        else:
            st.info("暂无文档")
    except Exception as exc:
        st.error(f"获取文档列表失败: {exc}")

    st.subheader("上传文档")
    uploaded = st.file_uploader("支持 PDF / HTML / TXT / Markdown", type=["pdf", "html", "htm", "txt", "md", "markdown"])
    col1, col2, col3 = st.columns(3)
    upload_region = col1.text_input("上传地区")
    upload_industry = col2.text_input("上传行业")
    upload_doc_type = col3.text_input("文档类型", value="policy")
    if st.button("上传到知识库", use_container_width=True):
        if not uploaded:
            st.warning("请先选择文件")
        else:
            try:
                files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")}
                data = {
                    "region": upload_region,
                    "industry": upload_industry,
                    "doc_type": upload_doc_type,
                }
                result = api_request("POST", "/api/v1/documents/upload", files=files, data=data).json()
                st.success(result["message"])
                st.json(result["document"])
            except Exception as exc:
                st.error(f"上传失败: {exc}")

    st.subheader("知识源管理")
    with st.form("source_form"):
        name = st.text_input("知识源名称", value="示例 HTML 列表页")
        base_url = st.text_input("Base URL", value="https://example.com/policies")
        source_type = st.selectbox("类型", ["html", "pdf", "txt", "markdown", "html_list"])
        source_region = st.text_input("知识源地区")
        source_industry = st.text_input("知识源行业")
        crawl_config_json = st.text_area(
            "抓取配置 JSON",
            value='{"link_selector": "a", "include_patterns": ["policy"], "max_links": 10}',
            height=100,
        )
        submitted = st.form_submit_button("新增知识源")

    if submitted:
        try:
            payload = {
                "name": name,
                "base_url": base_url,
                "source_type": source_type,
                "region": source_region or None,
                "industry": source_industry or None,
                "crawl_config_json": crawl_config_json or None,
                "enabled": True,
            }
            data = api_request("POST", "/api/v1/sources", json=payload).json()
            st.success("知识源创建成功")
            st.json(data)
        except Exception as exc:
            st.error(f"创建知识源失败: {exc}")

    try:
        sources = api_request("GET", "/api/v1/sources").json()
        st.subheader("知识源列表")
        if not sources:
            st.info("暂无知识源")
        for source in sources:
            cols = st.columns([4, 2, 1])
            cols[0].write(f"{source['name']} | {source['source_type']} | {source['base_url']}")
            cols[1].write(f"last_sync_at: {source.get('last_sync_at')}")
            if cols[2].button("手动同步", key=f"sync_{source['id']}"):
                try:
                    job = api_request("POST", f"/api/v1/sources/{source['id']}/sync").json()
                    st.success(job["message"])
                except Exception as exc:
                    st.error(f"同步失败: {exc}")
    except Exception as exc:
        st.error(f"获取知识源失败: {exc}")



def render_config_page() -> None:
    st.title("系统配置")

    if st.session_state.config_notice:
        notice = st.session_state.config_notice
        st.success(notice)
        st.session_state.config_notice = None

    with st.form("api_base_url_form"):
        api_base_url = st.text_input("FastAPI 地址", value=st.session_state.api_base_url)
        save_api = st.form_submit_button("保存 API 地址")
    if save_api:
        st.session_state.api_base_url = api_base_url
        st.session_state.config_notice = "API 地址已保存"
        st.rerun()

    backend_config: dict[str, Any] | None = None
    try:
        backend_config = api_request("GET", "/api/v1/system/config").json()
    except Exception as exc:
        st.error(f"获取后端配置失败: {exc}")

    if backend_config:
        st.subheader("Embedding 配置")
        st.caption("保存配置后会写入项目根目录 `.env`，后续请求会按新配置生效。切换模型后建议立即重建向量。")

        available_models = ["embeddinggemma", "bge-m3"]
        available_apis = ["auto", "embed", "embeddings"]
        current_model = backend_config.get("embedding_model", "embeddinggemma")
        current_api = backend_config.get("embedding_api", "auto")

        with st.form("embedding_config_form"):
            model = st.selectbox(
                "Embedding 模型",
                available_models,
                index=available_models.index(current_model) if current_model in available_models else 0,
            )
            api_mode = st.selectbox(
                "Ollama Embedding API",
                available_apis,
                index=available_apis.index(current_api) if current_api in available_apis else 0,
            )
            col1, col2, col3 = st.columns(3)
            profile = col1.text_input("Profile", value=backend_config.get("embedding_profile", "auto"))
            batch_size = int(col2.number_input("Batch Size", min_value=1, max_value=256, value=int(backend_config.get("embedding_batch_size", 16))))
            dimensions = int(col3.number_input("Dimensions", min_value=0, value=int(backend_config.get("embedding_dimensions", 0))))
            col4, col5 = st.columns(2)
            truncate = col4.checkbox("Truncate", value=bool(backend_config.get("embedding_truncate", True)))
            keep_alive = col5.text_input("Keep Alive", value=backend_config.get("embedding_keep_alive", "5m"))
            col6, col7 = st.columns(2)
            query_prefix = col6.text_input("Query Prefix", value=backend_config.get("embedding_query_prefix", ""), placeholder="例如：query: ")
            document_prefix = col7.text_input("Document Prefix", value=backend_config.get("embedding_document_prefix", ""), placeholder="例如：passage: ")

            btn1, btn2, btn3 = st.columns(3)
            save_only = btn1.form_submit_button("保存配置")
            save_and_rebuild = btn2.form_submit_button("保存并重建")
            rebuild_only = btn3.form_submit_button("仅重建当前向量")

        config_payload = {
            "embedding_model": model,
            "embedding_profile": profile or "auto",
            "embedding_api": api_mode,
            "embedding_batch_size": batch_size,
            "embedding_truncate": truncate,
            "embedding_keep_alive": keep_alive or "5m",
            "embedding_dimensions": dimensions,
            "embedding_query_prefix": query_prefix,
            "embedding_document_prefix": document_prefix,
        }

        if save_only or save_and_rebuild:
            try:
                saved = api_request("POST", "/api/v1/system/config/embedding", json=config_payload).json()
                message = saved["message"]
                if save_and_rebuild:
                    rebuild = api_request("POST", "/api/v1/system/rebuild-embeddings", timeout=600).json()
                    message = (
                        f"{message}；{rebuild['message']} | model={rebuild['model_name']} | "
                        f"updated={rebuild['updated_chunks']} | failed={rebuild['failed_chunks']}"
                    )
                st.session_state.config_notice = message
                st.rerun()
            except Exception as exc:
                st.error(f"更新 embedding 配置失败: {exc}")

        if rebuild_only:
            try:
                rebuild = api_request("POST", "/api/v1/system/rebuild-embeddings", timeout=600).json()
                st.success(
                    f"{rebuild['message']} | model={rebuild['model_name']} | "
                    f"updated={rebuild['updated_chunks']} | failed={rebuild['failed_chunks']}"
                )
            except Exception as exc:
                st.error(f"重建 embedding 失败: {exc}")

        with st.expander("当前后端配置", expanded=False):
            st.json(backend_config)

    st.markdown("""
### 本地运行建议
- 切换到 `bge-m3` 前先执行 `ollama pull bge-m3`
- 切换模型后建议执行一次 embedding 重建，避免旧向量继续参与检索
- FastAPI 默认地址：`http://127.0.0.1:8000`

### 推荐命令
```bash
ollama pull deepseek-r1:8b
ollama pull embeddinggemma
ollama pull bge-m3
python scripts/init_db.py
python scripts/import_sample_data.py
python scripts/rebuild_embeddings.py
uvicorn app.main:app --reload
streamlit run streamlit_app/app.py
```
""")


PAGES: dict[str, Any] = {
    "智能问答": render_chat_page,
    "报告背景生成": render_report_page,
    "知识库导入与同步": render_knowledge_page,
    "系统配置": render_config_page,
}

selected = st.sidebar.radio("导航", list(PAGES.keys()))
PAGES[selected]()


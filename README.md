# Dual Carbon Intelligent Assistant
# 双碳智能问答系统

基于 **FastAPI + SQLite  + 本地向量缓存 + Ollama + Streamlit** 的轻量化企业级“双碳”智能问答系统代码仓库。



## 1. 技术栈

- Python 3.11
- FastAPI
- SQLite
- Ollama
  - 主模型：`deepseek-r1:8b`
  - Embedding：`embeddinggemma` / `bge-m3`，支持本地 Ollama 可切换实现
- Streamlit

## 3. 目录结构

```text
project-root/
  app/
    api/
      v1/
        endpoints/
          chat.py
          documents.py
          report.py
          sources.py
        router.py
    core/
      config.py
      logging.py
    db/
      init_db.py
      session.py
    models/
      db_models.py
    repositories/
      document_repository.py
      qa_log_repository.py
      source_repository.py
      sync_job_repository.py
    schemas/
      chat.py
      common.py
      document.py
      report.py
      source.py
    services/
      embedding_service.py
      ingestion_service.py
      ollama_service.py
      qa_service.py
      report_service.py
      retrieval_service.py
      sync_service.py
      vector_store.py
    templates/
      report_background.jinja2
      report_generation_prompt.jinja2
      report_polish_prompt.jinja2
    utils/
      chunking.py
      file_parsers.py
      text.py
      time.py
    main.py
  data/
    documents/
    sample/
    uploads/
    vector_store/
  scripts/
    import_sample_data.py
    init_db.py
    rebuild_embeddings.py
  streamlit_app/
    app.py
  tests/
  requirements.txt
  .env.example
```

## 4. Embedding 切换说明

向量文件会按 `provider + profile + model` 进入不同命名空间目录，避免切换模型时新旧向量混用。

如果把 `.env` 从 `embeddinggemma` 切到 `bge-m3`，建议立即执行：

```bash
python scripts/rebuild_embeddings.py
```

这会基于当前数据库中的 chunk 内容重建全部 embedding，确保语义检索与当前模型一致。

## 5. 核心能力说明

### 5.1 知识库导入

支持：
- HTML：`requests + BeautifulSoup4`
- PDF：`PyMuPDF`
- TXT / Markdown：直接解析

导入流程：
- 解析文本
- 清洗
- 元数据抽取
- 分块
- 写入 SQLite
- 写入 FTS5 索引
- 生成 embedding 并存本地 `npy`

### 5.2 混合检索

- 关键词召回：SQLite FTS5（SQLite 自带的一套全文检索引擎）
- 语义召回：Ollama embeddings + 本地 `npy` 向量缓存
- 合并去重 + 简单重排

重排公式：

```text
final_score = 0.40 * keyword_score
            + 0.35 * semantic_score
            + 0.15 * region_score
            + 0.10 * freshness_score
```

### 5.3 问答

API：`POST /api/v1/chat/query`

输出字段：
- `answer`
- `citations`
- `confidence`
- `risk_note`
- `debug.retrieved_chunks`

策略：
- 仅基于检索证据回答
- 检索不足时返回：`依据不足，无法判断。`
- 引用来源只来自检索到的 chunk

### 5.4 报告背景生成

API：`POST /api/v1/report/background`

支持两种模式：
- `draft`
- `formal`

实现方式：
- 先检索政策依据
- 再用 Jinja2 模板组织输出
- 有模型时进行结构化生成与润色
- 模型不可用时退化为模板初稿

### 5.5 自动同步

API：
- `GET /api/v1/sources`
- `POST /api/v1/sources`
- `POST /api/v1/sources/{id}/sync`

能力：
- 配置知识源
- 手动同步
- APScheduler 定时同步
- hash 去重
- 同 URL 版本更新时旧版本标记为 `superseded`
- 记录 `sync_jobs`

## 6. 快速启动

### 6.1 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 6.2 启动 Ollama 并拉取模型

使用默认 embeddinggemma：

```bash
ollama pull deepseek-r1:8b
ollama pull embeddinggemma
```

切换到 bge-m3：

```bash
ollama pull deepseek-r1:8b
ollama pull bge-m3
```

然后修改 `.env`：

```env
EMBEDDING_MODEL=bge-m3
EMBEDDING_PROFILE=auto
EMBEDDING_API=auto
```

如果你已经导入过文档，再执行：

```bash
python scripts/rebuild_embeddings.py
```

### 6.3 初始化数据库

```bash
python scripts/init_db.py
```

### 6.4 导入最小示例数据

```bash
python scripts/import_sample_data.py
```

### 6.5 启动后端

```bash
uvicorn app.main:app --reload
```

启动后访问：
- Swagger: `http://127.0.0.1:8000/docs`
- 健康检查: `http://127.0.0.1:8000/health`

### 6.6 启动前端

```bash
streamlit run streamlit_app/app.py
```

## 8. 功能

已实现：
- 可运行的 FastAPI 后端

- SQLite 表与 FTS5

- 本地文件导入与远程同步

- `embeddinggemma` / `bge-m3` Ollama 本地 embedding 可切换实现

- 模型切换后的 embedding 重建脚本

- 问答与报告生成

- Streamlit 多页面前端

  


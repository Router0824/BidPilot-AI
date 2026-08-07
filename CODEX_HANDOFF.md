# BidPilot MVP 未完成任務清單

> 面向 Codex 的交接文檔。標明了已完成部分、待完成任務、技術細節與檔案位置。

---

## 2026-08-06 Codex 迭代更新

P0/P1 已完成 MVP 版落地：

- P0 LLM：已接 DeepSeek/OpenAI-compatible Gateway，DeepSeek 默認 `https://api.deepseek.com` + `deepseek-v4-flash`，保留 mock fallback。
- P0 RAG：新增 `KnowledgeIndexService`，支持材料分塊、hash embedding、cosine + keyword 混合檢索、重建索引 API；草稿生成已改用 RAG 召回材料。
- P0 SSE：新增 `/api/v1/projects/{project_id}/workflow/stream?token=...`，前端 `WorkflowPage` 使用 EventSource 實時更新。
- P0 大文件：新增三步式分片上傳 API：創建 session、上傳 chunks、complete 校驗 SHA-256 後創建 Document。
- P1 Word 匯出：`requirements`、`outline`、`full_document`、`risk_list` 支持 `.docx`。
- P1 補遺衝突：新增 `AddendumAgent`，工作流加入 `detect_addendum_conflicts` 節點，並提供手動 API/前端入口。
- P1 評分跨頁：新增評分項跨頁/重複標題合併服務與 API/前端入口。
- P1 章節版本對比：`OutlinePage` 支持兩版本並排行級 diff。
- P1 Token/成本：workflow status 聚合 `token_usage_total` 和 `estimated_cost`，節點寫入模型、token、耗時。
- P1 知識庫索引：知識庫頁支持重建索引、搜尋、審核入庫。

驗證：
- `python -m compileall app` 通過。
- `npm install` 後 `npm run build` 通過。
- DeepSeek key 真實 `/models` 和 chat completion smoke test 已通。

---

## 2026-08-06 UX/流式交互更新

- 新增後端進度事件匯流排 `app/observability/progress.py`。
- Workflow SSE 現在同時推送 `workflow.status.changed` 和 `agent.progress`，並會立即返回首個狀態。
- LLM Gateway 在模型調用前、返回後、失敗時發布可展示進度摘要；不暴露模型隱藏推理。
- Workflow 節點開始/完成/失敗會發布進度事件；單章節生成、補遺識別、審查等直接 API 也接入進度上下文。
- 前端新增 `feedback.js` 和 `ApiActivity.vue`，所有 axios API 自動顯示 pending、成功、失敗、後端耗時。
- 全局按鈕/卡片/導航增加 hover、active、focus-visible、disabled 的視覺反饋。
- WorkflowPage 和 OutlinePage 顯示 Agent 進度流；長任務不再只有等待。
- axios timeout 從 30s 放寬到 120s，後端增加 `X-Process-Time-Ms` 響應頭。
- RequirementsPage 移除原生 fetch，統一走 axios feedback 管線。

驗證：
- `python -m compileall app` 通過。
- `npm run build` 通過。

---

## 2026-08-06 P2 企業化更新

P2 已完成可演示 MVP 版：

- 多人協同：新增 WebSocket 協作通道 `/enterprise/collaboration/ws`，支持在線 presence 和事件廣播。
- 任務分配：新增項目成員、章節分配 API，分配後寫入章節 owner 並創建站內任務。
- 細粒度 RBAC：章節已分配 owner 後，普通 writer 只能編輯/生成自己的章節；admin/project_admin 可管理。
- 審批流程：新增章節提交審批、審核通過/驳回、審批隊列 API。
- 私有化部署：新增 Helm chart 骨架，支持後端/前端、ConfigMap、Secret、Ingress、LDAP/SSO/LLM env 配置位。
- 模型路由：LLM Gateway 支持 task_type → model routing，DeepSeek 默認 fast=`deepseek-v4-flash`、quality=`deepseek-v4-pro`。
- 多行業模板：新增 software/construction/medical/education 模板，並接入大綱生成與企業頁手動套用。
- 完整操作審計：新增 `EnterpriseService.audit()`，對專案、文件、要求、事實、章節、匯出、商務/資格標等高危操作寫入 `audit_logs`。
- 商務標/資格標：新增 `CommercialAgent`、`QualificationAgent`，支持 LLM 生成與模板 fallback。
- 前端：新增 `EnterprisePage`，集中展示在線協作者、成員、模板、章節分配、審批、商務/資格標、審計。

驗證：
- `python -m compileall app` 通過。
- `npm run build` 通過。
- FastAPI 啟動層檢查通過：enterprise routes 14 個，WebSocket routes 1 個。
- 本機 API 實測：登入後可正常讀取 4 個行業模板。

---

## 2026-08-06 一鍵啟動更新

- 新增 `scripts/dev_start.py`：同一個終端啟動 FastAPI 後端與 Vite 前端。
- 新增 `start.sh`：根目錄執行 `./start.sh` 即可啟動。
- 啟動時會詢問是否啟用真實 DeepSeek API：
  - 選 `n`：使用 `BIDPILOT_LLM_PROVIDER=mock`，不消耗 API。
  - 選 `y`：提示輸入 DeepSeek API Key，只注入本次進程環境，不寫入檔案。
- 啟動器會自動檢查 `frontend/node_modules`，首次缺失時自動跑 `npm install`。
- 若 `8000` 或 `5173` 已有服務，啟動器會復用現有服務，不再硬啟造成端口衝突。
- `操作指南.txt` 已更新為一鍵啟動流程。

驗證：
- `python -m py_compile scripts/dev_start.py` 通過。
- `npm run build` 通過。

---

## 2026-08-06 置信度 / 咨询中心 / 资讯中心更新

- 置信度量化：新增 `ConfidenceService`，將模型先驗、來源完整性、原文命中、文本具體性、衝突狀態、人工確認拆成可解釋因子。
- 置信度 API：新增 `/projects/{project_id}/confidence/report` 和 `/confidence/recalculate`；事實與要求列表會返回 `confidence_detail`。
- 前端置信度：事实确认、要求矩阵页新增高/中/低視覺點、百分比 tooltip、一鍵重新量化。
- 咨询中心：新增項目內多輪問答，基於項目事實、招標需求、文件頁與知識庫召回回答；按當前角色給出不同視角，回答附資料引用。
- 咨询 API：新增 session 列表/創建、消息列表、提問接口。
- 资讯中心：新增商機監控、關鍵詞/地區過濾、公告源抓取、去重入庫、價值/競爭/熱度三分量化；LLM 可增強，無 API 時公式 fallback 可用。
- 前端入口：側邊欄新增「资讯中心」全局入口與項目內「咨询中心」入口。

驗證：
- `python -m compileall app` 通過。
- `npm run build` 通過。
- 本機 ASGI smoke test：登入、资讯中心列表、项目列表、置信度报告、咨询会话列表均返回 200。

---

## 2026-08-06 前端視覺美化更新

- 依照 `frontend-design` skill，確立「投標作戰室 / 藍圖控制台」視覺方向。
- 全局設計系統：新增墨藍、青色、琥珀、紅色風險色，統一卡片、表格、按鈕、focus、表單和背景藍圖網格。
- 側邊欄：新增品牌標識、工作區/當前項目分組、active 狀態條與響應式橫向導航。
- 工作台首頁：新增作戰台式 header、項目核心指標帶、卡片狀態線和更強 hover 反饋。
- 項目詳情：重做專案檔案 header、資訊卡、文件中心、工作流節點 chip、快捷入口，並補上「咨询中心」快捷入口。
- 登入頁：統一品牌入口視覺，保留本地測試帳號提示。
- API 進度浮層：改為同一套深色控制台風格，成功/錯誤提示更精緻。

驗證：
- `npm run build` 通過。
- Playwright 使用本機 Chrome 截圖檢查桌面工作台、專案詳情、手機工作台，未見明顯跑版。

---

## 一、項目狀態總覽

| 模塊 | 狀態 | 說明 |
|------|------|------|
| 後端骨架 (FastAPI) | ✅ 完成 | 路由、中間件、生命週期 |
| 數據模型 (14 個 ORM) | ✅ 完成 | SQLAlchemy async + SQLite |
| Pydantic Schema | ✅ 完成 | API 請求和響應模型 |
| JWT 認證 + RBAC | ✅ 完成 | 4 角色，sha256 密碼 |
| REST API (6 個路由模組) | ✅ 完成 | 項目/文件/要求/大綱/工作流/知識庫 |
| 工作流引擎 | ✅ 完成 | 10 節點狀態機 + 人工閘門 |
| Agent 層 (6 個 Agent) | ✅ 已接 LLM | DeepSeek/OpenAI-compatible Gateway + 規則 fallback |
| 文檔解析 (PDF/DOCX/XLSX) | ✅ 完成 | pdfplumber/python-docx/openpyxl |
| 前端 (Vue 3 + 10 頁面) | ✅ 完成 | Pinia + Vue Router + Axios |
| 導出服務 | ✅ Word MVP | Markdown + docx，xlsx 為 TSV 兼容輸出 |
| Docker Compose | ✅ 完成 | backend + nginx 前端 |

---

## 二、P0 核心任務（必須完成）

### 2.1 接入真實 LLM 網關

**狀態：** ✅ 已完成第一版接入。

**已完成：**
- `app/agents/__init__.py` 新增 `LLMGateway`，使用 OpenAI-compatible `/chat/completions` HTTP API。
- 支持 `BIDPILOT_LLM_PROVIDER=deepseek`，默認 `base_url=https://api.deepseek.com`、`model=deepseek-v4-flash`。
- 保留 `MockLLMGateway` 和規則 fallback；未配置 key 或 LLM 調用失敗時 Demo 仍可跑。
- `RequirementAgent` 的事實抽取、要求抽取，`ScoringAgent` 的評分抽取，`DraftingAgent` 的大綱/章節生成已優先走 LLM JSON。
- `WorkflowService` 已寫入節點 `model_name`、`prompt_version`、`token_usage`、`latency_ms`。

**驗證：**
- 使用 DeepSeek key 查 `/models` 成功，可用模型：`deepseek-v4-flash`、`deepseek-v4-pro`。
- `deepseek-v4-flash` chat completion smoke test 成功，JSON 解析和 token usage 正常。
- 小樣本文本驗證：可抽取項目事實、合規要求、評分項；已過濾项目名称/招标人/预算等純事實，避免混入要求矩阵。

**後續優化：**
- 成本統計目前是進程內累計和節點級 token delta，尚未做項目級持久化聚合。
- ReviewAgent 仍主要使用規則審查，可追加 LLM 語義審查。

**原始目標：** 替換為真實 LLM 調用，讓 Agent 具備語義理解與生成能力。

**改動文件：** `app/agents/__init__.py`

**具體步驟：**

1. 在 `app/agents/__init__.py` 底部新增真實 LLM Gateway 類：

```python
# 示例：OpenAI 兼容接口（也適用 DeepSeek / 通義千問 / 本地 vLLM）
import json
from openai import AsyncOpenAI

class LLMGateway:
    def __init__(self, api_key: str, base_url: str, model: str = "gpt-4o"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def call(self, task_type: str, messages: list, response_schema=None,
                   max_tokens=2000, temperature=0.1) -> dict:
        kwargs = dict(model=self.model, messages=messages,
                      max_tokens=max_tokens, temperature=temperature)
        if response_schema:
            kwargs["response_format"] = {"type": "json_object"}
        response = await self.client.chat.completions.create(**kwargs)
        return json.loads(response.choices[0].message.content)
```

2. 替換文件底部的全局 Agent 實例：

```python
llm = LLMGateway(api_key="YOUR_API_KEY", base_url="https://api.openai.com/v1")
document_agent = DocumentAgent(llm)
requirement_agent = RequirementAgent(llm)
scoring_agent = ScoringAgent(llm)
retrieval_agent = RetrievalAgent(llm)
drafting_agent = DraftingAgent(llm)
review_agent = ReviewAgent(llm)
```

3. 重寫各 Agent 的 `_mock_response` 方法為真實 LLM 調用，關鍵改動：

| Agent | 方法 | 當前做法 | 需改為 |
|-------|------|---------|--------|
| `RequirementAgent` | `_extract_facts_from_text` | 正則匹配 | LLM structured output（JSON） |
| `RequirementAgent` | `_extract_requirements_from_text` | 關鍵詞+逐行分類 | LLM 分批提取，返回結構化 JSON |
| `ScoringAgent` | `_extract_scoring_from_text` | 正則 `(\d+)\s*分` | LLM 提取評分項+分值+條件 |
| `DraftingAgent` | `_generate_section_content` | 模板拼裝 | LLM 根據要求+知識庫+事實生成 |
| `ReviewAgent` | `review` | 規則檢查 | LLM 語義審查（或混合） |

4. **Prompt 設計建議：**
   - 每個 Agent 需要一個 system prompt 定義角色和輸出格式
   - 事實提取：要求模型輸出 `{"facts": [{"key": "...", "value": "...", "confidence": 0.9}]}` 格式
   - 要求提取：要求模型輸出結構化 JSON，包含 `requirement_text`、`type`、`mandatory`、`risk_level`、`evidence_required`
   - 章節生成：五步流程（證據計劃 → 結構計劃 → 正文生成 → 引用校驗 → 風險掃描）

5. **成本控制：** 在 `app/core/config.py` 加上 `LLM_COST_LIMIT_PER_PROJECT` 配置項，在 `LLMGateway.call()` 中累計 token 用量，超限拋異常。

---

### 2.2 向量檢索 (RAG) 接入

**現狀：** `RetrievalAgent.retrieve()` 直接從 `knowledge_chunks` 表查詢前 10 條，無向量相似度排序。

**目標：** 基於 Embedding 做語義檢索，支持混合檢索（BM25 + 向量）。

**改動文件：** `app/agents/__init__.py`（RetrievalAgent）、`app/application/bid_services.py`（DraftService）

**方案選擇：**

| 方案 | 適用場景 | 改動量 |
|------|---------|--------|
| `sqlite-vec` 擴展 | MVP 快速驗證，免安裝外部服務 | 小 |
| `pgvector` + PostgreSQL | 生產環境，與業務數據庫一體 | 中 |
| `Milvus` / `Qdrant` | 大規模向量檢索 | 大 |

**建議 MVP 先用 `sqlite-vec`：**

```bash
pip install sqlite-vec
```

然後在 `RetrievalAgent` 中：
1. 對用戶查詢（章節標題 + 關聯要求）調用 Embedding API 生成向量
2. 在 `knowledge_chunks` 表中做向量相似度搜索
3. 與 BM25 關鍵詞結果合併去重
4. 返回 top-8 條，按相關性排序

**Embedding 模型建議：** `text-embedding-3-small`（OpenAI）或 `bge-large-zh-v1.5`（本地部署）

---

### 2.3 前端 SSE 進度推送

**現狀：** 前端通過輪詢（頁面刷新）獲取工作流狀態，用戶看不到 Agent 執行的即時進度。

**目標：** 後端通過 Server-Sent Events 推送節點執行進度，前端實時顯示。

**改動文件：**
- 後端：`app/api/v1/workflows.py`（新增 SSE endpoint）
- 前端：`frontend/src/pages/WorkflowPage.vue`（EventSource 監聽）

**後端 SSE 實現：**

```python
# app/api/v1/workflows.py
from sse_starlette.sse import EventSourceResponse
import asyncio

@router.get("/{project_id}/workflow/stream")
async def stream_workflow(project_id: str):
    async def event_generator():
        while True:
            # 查詢最新工作流狀態
            status = await get_workflow_status(project_id)
            yield {"event": "workflow.status.changed", "data": json.dumps(status)}
            await asyncio.sleep(2)
    return EventSourceResponse(event_generator())
```

**前端監聽：**

```javascript
const source = new EventSource(`/api/v1/projects/${projectId}/workflow/stream`)
source.addEventListener('workflow.status.changed', (e) => {
  const data = JSON.parse(e.data)
  // 更新 UI
})
```

---

### 2.4 大文件分片上傳

**現狀：** 文件上傳直接用 `UploadFile.read()` 一次性讀取，大文件（>100MB）會耗盡內存。

**目標：** 實現「創建上傳會話 → 分片上傳 → 完成校驗」三步流程。

**改動文件：** `app/api/v1/documents.py`、`app/application/document_service.py`

**參考 PRD 9G.5 節：**
- `POST /api/v1/documents/upload-sessions` — 創建會話，返回 `upload_session_id`
- `PUT /api/v1/documents/upload-sessions/{id}/chunks` — 上傳分片（每片 5-10MB）
- `POST /api/v1/documents/upload-sessions/{id}/complete` — 校驗 SHA-256 + MIME，合併文件

---

## 三、P1 任務（提升演示完整度）

### 3.1 Word 導出

**現狀：** 只支持 Markdown 導出（寫入 `.md` 文件）。

**目標：** 支持 `.docx` 格式導出，保留章節層級、表格、引用標記。

**改動文件：** `app/application/review_export_service.py`

**技術方案：** 使用 `python-docx`（已安裝）生成 Word 文檔：
- 大綱章節 → Heading 1/2/3
- 正文內容 → 段落
- 引用來源 → 腳註（Footnote）
- 待確認內容 → 黃色高亮（Highlight）

**注意：** 中文需要使用 `Noto Sans CJK SC`（黑體）和 `Noto Serif CJK SC`（宋體）字體。

---

### 3.2 補遺衝突識別

**現狀：** 未實現。

**目標：** 上傳補遺文件後，系統自動比對原招標文件與補遺，識別工期、預算、截止時間等衝突。

**改動文件：** 新增 `app/agents/addendum_agent.py`，在 `app/workflows/engine.py` 中增加 `detect_addendum_conflicts` 節點。

**參考 PRD 6.2 節流程：**
1. 解析補遺內容
2. 與原招標文件進行事實比對
3. 識別衝突（工期、預算、提交時間）
4. 展示原值、新值和來源位置
5. 人工確認 → 更新項目事實庫 → 標記受影響章節

---

### 3.3 評分表跨頁合併

**現狀：** `ScoringAgent` 逐頁提取評分項，跨頁表格會斷開。

**目標：** 檢測跨頁表格，按表頭相似度和列邊界自動合併，合併失敗時創建人工修正任務。

**改動文件：** `app/agents/__init__.py`（ScoringAgent）

**參考 PRD 9C.3 節。**

---

### 3.4 章節版本對比

**現狀：** `DraftVersion` 已保存多個版本，但前端只展示最新版本。

**目標：** 前端章節編輯器支持兩個版本並排對比，高亮差異。

**改動文件：** `frontend/src/pages/OutlinePage.vue`

**技術方案：** 使用 `diff` 庫（如 `diff-match-patch`）在前端做文本對比，差色顯示新增/刪除/修改。

---

### 3.5 Token 和成本統計

**現狀：** `NodeRun` 有 `token_usage` 字段但未寫入真實數據。

**目標：** 每次 LLM 調用後記錄 token 消耗，項目級聚合展示。

**改動文件：** `app/agents/__init__.py`（LLMGateway）、`app/workflows/workflow_service.py`

---

### 3.6 知識庫向量索引重建

**現狀：** 知識庫管理頁只能添加/查看文本，無向量索引。

**目標：** 
- 上傳材料後自動分塊 → Embedding → 入庫
- 支持「重建索引」按鈕
- 索引版本化發布（構建中版本不可被檢索）

**改動文件：** `app/api/v1/knowledge.py`、`app/agents/__init__.py`（RetrievalAgent）

**分塊策略（參考 PRD 9E.2）：**
- 普通文本：400-800 中文字符，重疊 80-120 字
- 案例：按「背景-範圍-方案-結果」保持語義單元
- 資質證書：按證書實體單獨成塊

---

## 四、P2 任務（企業化擴展）

| 任務 | 說明 |
|------|------|
| 多人協同 | 同一專案多人同時編輯，需 WebSocket + OT/CRDT |
| 任務分配 | 大綱章節分配給不同編制人員，郵件/站內通知 |
| 細粒度 RBAC | 資源級權限（某章節僅 owner 可編輯） |
| 審批流程 | 章節完成後需審核人員審批，多級審批鏈 |
| 私有化部署 | Kubernetes Helm Chart、LDAP/SSO 集成 |
| 模型路由 | 不同任務自動選擇不同模型（低成本/高精度） |
| 多行業模板 | 建築/醫療/教育等行業的預設大綱模板 |
| 完整操作審計 | `audit_logs` 表已建，需寫入所有高危操作 |
| 商務標/資格標 | 新增 `CommercialAgent`、`QualificationAgent` |

---

## 五、技術債務

### 5.1 數據庫升級

**現狀：** SQLite（`aiosqlite`）

**目標：** PostgreSQL + `pgvector`

**改動：** `app/core/config.py` 改 `DATABASE_URL`，安裝 `asyncpg`，數據模型無需修改（SQLAlchemy 兼容）。

### 5.2 異步隊列

**現狀：** 工作流節點在 API 請求內同步執行，長任務會阻塞。

**目標：** Celery + Redis 異步執行，API 立即返回 `202 Accepted`。

**改動：** `app/workflows/workflow_service.py` 中 `_execute_node` 改為 `celery_app.send_task()`。

### 5.3 安全加固

- [ ] 日誌脫敏：手機號、身份證號、郵箱、密鑰樣式
- [ ] 文件上傳安全檢查：MIME 校驗、壓縮包展開比例限制
- [ ] Prompt 注入防護：解析後標記指令性內容，Prompt 中聲明數據邊界
- [ ] 對象存儲預簽名 URL 短時有效
- [ ] RLS（Row Level Security）在 PostgreSQL 層啟用

### 5.4 測試

- [ ] 單元測試：狀態轉移、風險規則、權限過濾、引用校驗
- [ ] 集成測試：真實 PostgreSQL/Redis/對象存儲
- [ ] 合約測試：Agent 輸入輸出 Schema 校驗
- [ ] E2E 測試：完整上傳到導出主鏈路（已有 `test_e2e.py` 基礎版本）

### 5.5 可觀測性

- [ ] 結構化日誌（JSON 格式，含 trace_id/span_id）
- [ ] Prometheus metrics（API 延遲、隊列積壓、Worker 利用率、LLM 錯誤率）
- [ ] 告警規則（主流程失敗率 >5%、隊列等待 >5min、LLM 錯誤率 >10%）

---

## 六、推薦執行順序

```
第 1 步：LLM 網關接入（2.1）
  └→ 事實提取、要求抽取、章節生成全部切換為 LLM

第 2 步：向量檢索 RAG（2.2）
  └→ 知識庫材料真正用於生成

第 3 步：Word 導出（3.1）
  └→ 演示時可交付正式文檔

第 4 步：SSE 進度推送（2.3）+ 大文件上傳（2.4）
  └→ 用戶體驗提升

第 5 步：補遺衝突（3.2）+ 評分表合併（3.3）
  └→ 補齊 P1 功能

第 6 步：章節版本對比（3.4）+ Token 統計（3.5）
  └→ 演示完整度

第 7 步：數據庫升級（5.1）+ 異步隊列（5.2）
  └→ 生產就緒
```

---

## 七、關鍵檔案索引

| 檔案 | 用途 |
|------|------|
| `app/main.py` | FastAPI 入口 |
| `app/core/config.py` | 環境變量配置 |
| `app/core/auth.py` | JWT 認證 + 角色定義 |
| `app/domain/models.py` | 14 個 ORM 數據模型 |
| `app/schemas/__init__.py` | Pydantic API Schema |
| `app/agents/__init__.py` | **6 個 Agent + MockLLMGateway（核心改動點）** |
| `app/workflows/engine.py` | 工作流節點定義 + 狀態轉移 |
| `app/workflows/workflow_service.py` | 工作流編排服務 |
| `app/application/bid_services.py` | 要求/評分/大綱/草稿服務 |
| `app/application/review_export_service.py` | 審查引擎 + 導出服務 |
| `app/application/document_service.py` | 文檔解析服務 |
| `app/api/v1/bid.py` | 投標業務 API |
| `app/api/v1/workflows.py` | 工作流控制 API |
| `frontend/src/pages/` | 前端 10 個頁面 |
| `frontend/src/stores/app.js` | Pinia Store + API 客戶端 |
| `sample_tender.txt` | 示範招標文件 |
| `操作指南.txt` | Demo 操作步驟 |

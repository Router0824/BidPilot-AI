---
domain:
  - nlp
tags:
  - agent
  - fastapi
  - vue
  - bid-document
deployspec:
  entry_file: app.py
license: Apache License 2.0
---

# BidPilot-AI 智能投标 Agent 平台

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12%2B-3776ab.svg)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)
![Vue](https://img.shields.io/badge/Frontend-Vue%203-42b883.svg)
![SQLite](https://img.shields.io/badge/Database-SQLite-003b57.svg)
![Mock LLM](https://img.shields.io/badge/LLM-Mock%20Ready-111827.svg)
![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)

**招标文件解析 · Planner Agent · 增量重执行 · 证据链追溯 · Reviewer/Fixer · 90 秒 Demo**

[界面预览](#界面预览) · [核心能力](#核心能力) · [快速开始](#快速开始) · [模型设置](#模型设置) · [Demo 流程](#demo-流程) · [部署说明](#部署说明)

</div>

BidPilot-AI 是一个面向投标团队的 AI Agent 工作台。它把传统“固定顺序执行的投标文档流程”，升级为可展示 Agent 决策过程的动态工作流：系统可以解析招标文件与补遗文件，规划执行节点，预览变更影响，只重跑受影响节点，并把招标要求、原文证据、企业材料、投标章节、审查问题串成可追溯链路。

项目保留轻量 Mock 模式：没有 API Key 也能完成演示；需要真实模型时，可在前端“模型设置”页面可视化填写自己的 API。

---

## 界面预览

| 页面 | 说明 | 预览 |
| :--- | :--- | :---: |
| 登录入口 | Mock 演示账号默认填充，适合评委快速进入系统。 | ![登录入口](docs/images/preview-login.png) |
| 项目工作台 | 项目状态、风险、文档和工作流概览。 | ![项目工作台](docs/images/preview-dashboard.png) |
| 项目详情 | 文件上传、Demo 入口、Agent 主舞台入口。 | ![项目详情](docs/images/preview-project.png) |
| 咨询中心 | 基于项目上下文和知识库的问答，并展示引用来源。 | ![咨询中心](docs/images/preview-consultation.png) |
| 资讯中心 | 商机监控、关键词筛选和机会热度分析。 | ![资讯中心](docs/images/preview-information.png) |

---

## 核心能力

### Agent 自主规划

- Planner Agent 根据项目、文件类型、补遗、已完成节点、风险项和审查结果输出结构化计划。
- Planner 输出经过 Pydantic 校验，非法输出会回退到固定工作流。
- 前端展示执行原因、跳过原因、人工确认原因和当前计划图。

### 动态工作流与增量重执行

- 工作流节点定义包含输入、输出、依赖、失效来源、超时、重试、风险等级和人工确认策略。
- 新增补遗文件或人工确认变更后，系统计算受影响节点，只重跑必要下游。
- 前端提供“执行前预览”：清楚展示会重跑和不会重跑的节点。

### 响应证据图谱

- 建立“招标原文 -> 结构化要求 -> 风险等级 -> 投标章节 -> 企业材料 -> 生成内容 -> 审查结果”的链路。
- 要求覆盖矩阵展示页码、原文片段、要求类型、分值、风险、章节、材料、覆盖状态和置信度。
- 点击要求可查看完整证据链，避免只依赖模型解释。

### Reviewer/Fixer 闭环

- Reviewer 输出结构化问题，包括缺失响应、部分覆盖、内部冲突、引用不足、补遗冲突、资质风险等。
- Fixer 仅自动处理低风险问题；资格、报价、工期承诺、法律声明等高风险内容必须人工确认。
- 每个章节自动修正有最大次数限制，并保存修改前后内容。

### 可演示的工程稳定性

- 保留固定工作流作为降级方案。
- 保留 Mock LLM，适合公开演示和无 Key 环境。
- 支持 SSE 工作流进度、SQLite 本地数据库、Docker Compose 和 ModelScope 单容器部署。
- 前端提供 90 秒 Demo 引导层，评委无需猜点击顺序。

---

## 技术架构

```text
Vue 3 Frontend
  - Project Dashboard
  - Workflow Stage
  - Evidence Matrix
  - Review/Fix Center
  - LLM Settings
        |
        | REST / SSE / WebSocket
        v
FastAPI Backend
  - Auth / Projects / Documents
  - Bid / Workflow / Knowledge
  - Consultation / Information / System
        |
        v
Agent Layer
  - Planner Agent
  - Document / Requirement / Scoring Agents
  - Retrieval / Drafting / Review Agents
  - Mock or OpenAI-compatible LLM Gateway
        |
        v
SQLite + Uploads + Runtime Config
```

| 模块 | 技术 |
| --- | --- |
| 后端 | FastAPI, SQLAlchemy Async, Pydantic, SSE |
| 前端 | Vue 3, Vue Router, Pinia, Axios, Vite |
| 数据库 | SQLite |
| 文档解析 | pdfplumber, pypdf, python-docx, openpyxl |
| LLM | Mock LLM, DeepSeek, OpenAI-compatible API |
| RAG | Hash Embedding, 关键词检索, 混合召回 |
| 部署 | Docker Compose, ModelScope Docker, 本地启动脚本 |

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- npm

### 本地一键启动

```bash
git clone https://github.com/Router0824/BidPilot-AI.git
cd BidPilot-AI
cp .env.example .env
pip install -r requirements.txt
cd frontend && npm install && cd ..
./start.sh
```

启动脚本会询问是否启用真实 DeepSeek API：

- 输入 `n`：使用 Mock 模式，不需要 API Key。
- 输入 `y`：按提示输入 API Key，仅用于当前运行环境。

访问地址：

- 前端：http://localhost:5173
- 后端 API：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health/ready

### 手动启动

后端：

```bash
BIDPILOT_LLM_PROVIDER=mock python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

### Docker Compose

```bash
docker compose up --build
```

默认端口：

- 前端：http://localhost
- 后端：http://localhost:8080
- API 文档：http://localhost:8080/docs

---

## 模型设置

BidPilot-AI 默认使用 Mock 模式，公开演示时无需 API Key。需要真实模型时，登录后进入左侧导航：

```text
模型设置
```

页面支持：

- 选择 `Mock / DeepSeek / OpenAI / Custom`
- 输入 API Key
- 配置 Base URL
- 配置默认模型、快速模型和高质量模型
- 设置超时、项目成本上限和每千 Token 估算成本
- 保存后立即启用
- 点击“测试连接”验证模型可用性

安全说明：

- API Key 只保存在当前部署实例的本地运行时配置文件中。
- 页面不会回显明文 Key。
- `bidpilot_runtime_config.json` 已加入 `.gitignore` 和 `.dockerignore`。
- 公共 Demo 不建议预置个人 API Key。

也可以使用环境变量：

```bash
BIDPILOT_LLM_PROVIDER=deepseek
BIDPILOT_LLM_API_KEY=your_api_key
BIDPILOT_LLM_BASE_URL=https://api.deepseek.com
BIDPILOT_LLM_MODEL=deepseek-v4-flash
BIDPILOT_LLM_FAST_MODEL=deepseek-v4-flash
BIDPILOT_LLM_QUALITY_MODEL=deepseek-v4-pro
```

---

## Demo 流程

初始化 Mock 演示数据：

```bash
python scripts/seed_demo_data.py
```

演示数据包含：

- 一份招标主文件
- 一份将工期从 120 天修改为 90 天的补遗文件
- 若干企业资质材料
- 一个故意缺失的资格证明
- 一个前后矛盾的服务响应时间

建议 90 秒演示路线：

1. 登录系统并进入项目详情。
2. 点击“90 秒演示开始”。
3. 查看 Planner Agent 计划图。
4. 展示补遗影响范围和增量重执行预览。
5. 确认高风险变更后运行受影响节点。
6. 打开响应证据图谱，点击要求查看完整证据链。
7. 打开审查中心，展示 Reviewer 问题和 Fixer 低风险修正。
8. 展示高风险问题进入人工确认，而不是自动改写。
9. 导出当前投标文档。

完整说明见：[docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md)

### 演示账号

这些账号仅供本地 Mock 演示，禁止用于生产环境。

| Username | Password | Role |
| --- | --- | --- |
| `admin` | `admin123` | System admin |
| `bid_manager` | `bid123` | Bid manager |
| `writer` | `write123` | Writer |
| `reviewer` | `review123` | Reviewer |

---

## 部署说明

### ModelScope

仓库包含 ModelScope 单容器部署入口：

- 根目录 `Dockerfile`
- 根目录 `app.py`
- `modelscope_release/server.py`
- `modelscope_release/start.sh`

推荐设置：

- 应用部署框架：`docker`
- 端口号：`7860`
- Mock 模式：无需额外环境变量
- 真实模型：可在前端“模型设置”填写，或在平台环境变量中配置

### 健康检查

```text
GET /health/live
GET /health/ready
```

---

## 项目结构

```text
.
├── app/                    # FastAPI 后端
│   ├── agents/             # Agent 与 LLM Gateway
│   ├── api/v1/             # REST / SSE / WebSocket API
│   ├── application/        # 应用服务
│   ├── core/               # 配置、认证、运行时模型配置
│   ├── domain/             # SQLAlchemy ORM 模型
│   └── workflows/          # 工作流与依赖图
├── frontend/               # Vue 3 前端
│   └── src/pages/          # 工作台、流程、证据图谱、模型设置等页面
├── docs/                   # Demo Guide 和 README 图片
├── modelscope_release/     # ModelScope 发布辅助文件
├── scripts/                # Demo 数据初始化脚本
├── Dockerfile              # 单容器部署
├── docker-compose.yml      # 本地 Docker Compose
└── start.sh                # 本地启动入口
```

---

## 常用命令

```bash
# 后端导入检查
python -m compileall app scripts modelscope_release app.py

# 前端构建
npm --prefix frontend run build

# 初始化 Demo 数据
python scripts/seed_demo_data.py
```

---

## 常见问题

- 登录后仍回到登录页：清理浏览器该域名的 localStorage，或重新登录。
- 前端无法调用 API：确认后端运行在 `http://localhost:8000`。
- Docker 后端不可达：使用 `http://localhost:8080/docs`。
- 真实模型连接失败：先在“模型设置”点击“测试连接”，确认 Base URL、模型名和 Key。
- 演示环境没有 Key：保持 Mock 模式即可完整演示。

---

## License

Apache License 2.0

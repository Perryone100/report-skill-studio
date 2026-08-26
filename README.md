# Report Skill Studio

> Local-first, Skill-driven report workbench for turning transcripts and notes into reviewed, versioned Markdown, HTML and PDF reports.

Report Skill Studio 是一个本地优先、开源的结构化报告工作台。它把会议逐字稿或零散工作记录交给用户选择的写作模型，再按照声明式 Skill 生成可编辑、可校验、可追溯版本的报告。报告会同步为适合 Obsidian 等工具阅读的本地 Markdown，也能按需下载 HTML 或 PDF。

项目当前进入 `v0.4`：除可用的报告编辑主流程外，已经加入本地 Markdown 项目库、多地址多密钥模型连接，以及项目备份与删除保护。内置周会 Skill 已覆盖执行摘要、本周重点项目、工作进展、下周计划及风险协调；同一套工作台也可以通过 ZIP 安装其他报告 Skill，不局限于周报。

## 为什么做这个项目

常见的“逐字稿 → AI 对话 → 手工改稿 → PDF”流程存在三个问题：长期对话上下文会满、重复纠错无法沉淀、报告格式依赖每次提示词。Report Skill Studio 将这些能力拆成可维护的本地模块：

- **Skill 决定报告结构**：写作规则、JSON Schema、术语、校验规则和模板都由声明式文件描述。
- **模型只负责语义工作**：模型进行提取、合并与改写，不直接编排最终 PDF。
- **人工确认形成记忆**：只有用户确认过的专词和口语纠错才进入项目长期记忆。
- **本地流程保持可控**：项目、逐字稿、草稿、版本、Skill 和 Markdown 报告默认保存在本机。

## 当前能力

- 粘贴会议逐字稿或工作记录，生成结构化报告草稿；
- 自由选择用户配置的多个 OpenAI-compatible 写作模型；
- 项目级专词与口语矫正，立即应用到当前内容并复用于后续报告；
- 草稿自动保存、生成/确认检查点和历史版本恢复；
- 按项目文件夹自动同步纯 Markdown 报告，可直接作为 Obsidian 仓库使用；
- 检测 Markdown 外部修改，暂停自动覆盖以保护用户手工内容；
- 结构错误与写作建议分级，支持定位到具体字段；
- 确认后锁定报告，并使用安全 HTML/CSS 模板下载 HTML 或导出 PDF；
- 从 ZIP 安装、升级和管理自定义声明式 Skill；
- 安装前检查路径穿越、链接、加密条目、模板资源和工作台兼容性。
- 按最后一次模型生成时间排列最近报告，单纯查看或保存不会改变顺序，重新生成会回到最新位置；
- 将项目完整备份为不含密钥的 ZIP，并在清空历史或删除项目前保护外部修改过的 Markdown。

## 工作流程

```text
逐字稿 / 工作记录
        ↓
项目术语纠错 + 报告 Skill + 写作模型
        ↓
结构化草稿 → 人工编辑 → 自动检查 → 确认
        ↓
项目文件夹 Markdown + HTML / PDF 按需下载 + 可恢复版本
```

## 快速开始

开发环境需要 Python 3.11、[uv](https://docs.astral.sh/uv/)、Node.js 22 和 pnpm 11。

```bash
git clone https://github.com/Perryone100/report-skill-studio.git
cd report-skill-studio

uv sync --frozen --all-packages --extra dev --extra test --python 3.11
pnpm install --frozen-lockfile --ignore-scripts
cp .env.example .env

npm run dev
```

`npm run dev` 会同时启动本地 API 和 Web 工作台，等待健康检查通过后自动打开 `http://127.0.0.1:4173`。macOS 用户也可以在 Finder 中双击 `启动工作台.command`。环境诊断命令：

```bash
npm run doctor
```

完整安装、模型配置和 PDF 依赖说明见 [本地开发文档](docs/development.md)。

## 模型配置

复制 `.env.example` 后，可以配置任意兼容 OpenAI Chat Completions 接口的服务：

```dotenv
RSS_OPENAI_COMPATIBLE_BASE_URL=https://provider.example/v1
RSS_OPENAI_COMPATIBLE_API_KEY=replace-in-your-local-env
RSS_OPENAI_COMPATIBLE_MODELS=writing-standard,writing-economy
```

旧配置支持多个模型共用同一地址和密钥。若需要不同地址和密钥，使用单行 JSON 数组：

```dotenv
RSS_OPENAI_COMPATIBLE_CONNECTIONS='[{"id":"provider-a","name":"Provider A","base_url":"https://a.example/v1","api_key":"replace-locally","models":["model-a"]},{"id":"provider-b","name":"Provider B","base_url":"https://b.example/v1","api_key":"replace-locally","models":["model-b","model-b-economy"]}]'
```

每个连接的地址、密钥和模型列表相互独立，也可与旧配置同时使用。密钥只从服务端运行环境读取，不写入 SQLite、浏览器存储或日志。未配置云模型时仍可使用不会联网的本地 mock provider 验证流程。

## 报告 Skill

内置 `default-weekly-meeting` Skill 使用以下结构：

1. 执行摘要；
2. 本周重点项目；
3. 本周工作进展；
4. 下周重点计划；
5. 风险与待协调事项。

自定义 Skill 可以控制章节、写作规则、术语、确定性校验和 PDF 样式。当前工作台支持 `paragraph`、`bullet_list`、`project_table`、`status_cards` 和 `callout` 五种内容块；不兼容的 Schema 会在安装时被拒绝，而不会以残缺形式进入编辑器。

可生成四个虚构测试 Skill，用于验证安装与不同报告结构：

```bash
npm run build:test-skills
```

生成结果位于 `outputs/test-skills/`。完整格式见 [声明式 Skill 规范](docs/skill-spec.md)。

## 本地数据与隐私

默认运行数据位于 `data/`：

```text
data/
├── report-skill-studio.sqlite3
├── artifacts/
└── skills/
```

仓库内的 `.env`、数据库、逐字稿、用户 Skill、模型和渲染产物均被 Git 忽略。默认 Markdown 项目库位于仓库之外；如果用户主动把项目库放进另一个 Git 仓库，则其中的 `.md` 文件可以像普通 Obsidian 笔记一样自行版本管理。只有当用户明确配置并选择云模型时，当前生成请求需要的逐字稿、Skill 指令和 JSON Schema 才会发送到该模型服务。

左侧“隐私与数据管理”可以下载单项目 ZIP 备份、清空报告历史或删除整个项目。备份包含该项目的报告、逐字稿、版本、确认过的术语和 Markdown，不包含任何 API 密钥；执行删除前会检查工作台管理的 Markdown 是否被外部修改，检测到冲突时拒绝删除并保留数据库和文件。

默认 Markdown 项目库位于 `~/Documents/Report Skill Studio`，也可以从左侧“本地项目库设置”改为其他绝对路径：

```text
Report Skill Studio/
└── 项目名称/
    ├── 2026-08-26 周会纪要.md
    └── 2026-09-02 周会纪要.md
```

项目文件夹只由工作台写入 `.md` 报告；HTML 和 PDF 不会放入项目文件夹，而是在用户点击导出时下载。同一项目在同一日期出现同名报告时，工作台会统一为报告标题、Markdown 标题和文件名分配 `-2`、`-3` 等后缀，后续保存仍更新原文件。

## 当前边界

- MVP 尚未内置录音和语音转写；可粘贴飞书妙记等工具生成的逐字稿；
- 暂不提供云端协作、账号同步和飞书账号直连；
- 自定义 Skill 仍需使用当前五种规范化内容块；
- 修改本地项目库时需要填写绝对路径。

## 仓库结构

- `apps/server`：FastAPI 本地服务、持久化、任务和模型适配器；
- `apps/web`：React/TypeScript 报告工作台；
- `packages/skill_engine`：Skill 加载、Schema、术语和校验；
- `packages/report_renderer`：确定性 HTML/PDF 渲染；
- `skills/default-weekly-meeting`：内置通用周会 Skill；
- `docs`：架构、开发和 Skill 规范。

## 测试

```bash
uv run --frozen pytest
pnpm test:web
pnpm build:web
```

## License

[MIT](LICENSE)

# 本地开发

Report Skill Studio 是一个本地优先的 Python/TypeScript 单仓库。以下命令均从仓库根目录执行。

## macOS 环境

需要：

- macOS 13 或更高版本；
- Git；
- Python 3.11（由 `uv` 管理即可）；
- Node.js 22；
- pnpm 11.19.0。

使用 Homebrew 安装基础工具：

```bash
brew install git uv node@22 pnpm
export PATH="$(brew --prefix node@22)/bin:$PATH"
uv python install 3.11
```

`node@22` 是 Homebrew 的 versioned formula；请把上面的 `PATH` 配置加入自己的 shell 启动文件，使后续终端也能找到 Node 22。

确认版本：

```bash
uv --version
uv run --python 3.11 python --version
node --version
pnpm --version
```

## 安装依赖

后端、Skill 引擎、报告渲染器及其基础测试依赖：

```bash
uv sync --frozen --all-packages --extra dev --extra test --python 3.11
```

前端依赖：

```bash
pnpm install --frozen-lockfile --ignore-scripts
```

`--ignore-scripts` 会禁止第三方包在安装阶段执行生命周期脚本。当前前端的测试与构建不依赖这些脚本。

## 环境变量

服务端读取进程环境变量，也会读取仓库根目录的 `.env`。Vite 的 `envDir` 也指向仓库根目录，因此前后端共享这一份本地配置：

```bash
cp .env.example .env
```

可配置项：

| 变量 | 默认值或用途 |
| --- | --- |
| `RSS_DATA_DIR` | 本地数据目录，默认 `./data` |
| `RSS_SKILLS_DIR` | 声明式 Skill 目录，默认 `./skills` |
| `RSS_PROJECTS_DIR` | 本地 Markdown 项目库初始位置，默认 `~/Documents/Report Skill Studio` |
| `RSS_CORS_ORIGINS` | 逗号分隔的前端来源列表 |
| `RSS_OPENAI_COMPATIBLE_CONNECTIONS` | 多组独立地址、密钥和模型的单行 JSON 数组 |
| `RSS_OPENAI_COMPATIBLE_BASE_URL` | 可选兼容服务地址，不含 `/chat/completions` |
| `RSS_OPENAI_COMPATIBLE_API_KEY` | 可选兼容服务密钥 |
| `RSS_OPENAI_COMPATIBLE_MODELS` | 可选模型标识列表，逗号分隔；每项显示为一个写作模型选项 |
| `RSS_OPENAI_COMPATIBLE_MODEL` | 兼容原配置的单模型标识，仅在复数配置为空时使用 |
| `VITE_API_BASE_URL` | 前端访问的 API 地址，默认 `http://127.0.0.1:8000/api` |
| `VITE_USE_MOCK_API` | 设为 `true` 时显式启用前端 mock API；默认 `false` |
| `RSS_NO_OPEN` | 仅影响一键启动；设为 `true` 时不自动打开浏览器 |

地址、密钥和至少一个模型同时设置后，服务端才会注册对应的 OpenAI-compatible 写作模型；保持为空时，开发环境只提供不会联网的 `mock` provider。旧变量中的多个模型共用一组地址和密钥；`RSS_OPENAI_COMPATIBLE_CONNECTIONS` 中每个对象使用独立连接，格式如下：

```dotenv
RSS_OPENAI_COMPATIBLE_CONNECTIONS='[{"id":"deepseek","name":"DeepSeek","base_url":"https://api.deepseek.com","api_key":"replace-in-local-env","models":["deepseek-chat"]},{"id":"gateway","name":"内部网关","base_url":"http://127.0.0.1:9000/v1","api_key":"replace-in-local-env","models":["writing-standard","writing-economy"]}]'
```

`.env` 已被 Git 忽略，但它仍是本机上的明文文件。真实密钥更适合在启动前通过 shell 或系统密钥管理工具注入，例如：

```bash
export RSS_OPENAI_COMPATIBLE_BASE_URL="https://provider.example/v1"
export RSS_OPENAI_COMPATIBLE_API_KEY="replace-in-your-shell-only"
export RSS_OPENAI_COMPATIBLE_MODELS="your-standard-model,your-economy-model"
```

模型配置变化后需要重启服务端。已有的 `RSS_OPENAI_COMPATIBLE_MODEL` 无需立即修改，仍可继续使用。

不要把真实密钥写入 `.env.example`、测试夹具、SQLite、日志或提交记录。

## 启动工作台

日常使用只需在仓库根目录运行一个命令：

```bash
npm run dev
```

它会同时启动本地 API 与 Web 工作台，等待两端就绪后打开
`http://127.0.0.1:4173`。按 `Control+C` 会停止由本次命令启动的两个服务。
若服务已经在运行，会直接复用。只想检查环境、不启动服务时运行：

```bash
npm run doctor
```

也可以在 Finder 中直接双击仓库根目录的 `启动工作台.command`，不需要先进入
项目目录。启动器会优先使用 pnpm，普通终端没有 pnpm 时自动使用 Node.js 自带
的 npm。诊断只判断云模型的地址、密钥和模型列表是否齐全，不显示它们的值。
若不希望启动后自动打开浏览器，可临时运行 `RSS_NO_OPEN=true npm run dev`。

以下分开启动命令保留给后端或前端单独调试。

### 单独启动服务端

```bash
uv run --package report-skill-server uvicorn report_skill_server.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

OpenAPI 页面位于 `http://127.0.0.1:8000/docs`。

### 单独启动前端

另开一个终端：

```bash
pnpm dev:web
```

浏览器打开 `http://127.0.0.1:4173`。前端默认使用 `VITE_API_BASE_URL` 连接真实本地服务端，因此请保持前一个终端中的服务端运行。

需要在没有服务端的情况下调试界面时，在仓库根目录 `.env` 中设置：

```bash
VITE_USE_MOCK_API=true
```

修改 Vite 环境变量后需要重启前端开发服务器。

## 日常启动、休眠与重启

当前仓库以本地浏览器模式运行，`npm run dev` 会占用一个常驻终端。Mac 只是进入睡眠、终端窗口和进程仍保留时，唤醒后通常可以直接继续使用；关闭终端、结束进程或重启电脑后，需要重新运行启动命令或双击启动文件。

## 可选 PDF 支持

HTML 预览和渲染器基础测试不需要浏览器。只有导出 PDF 时才安装 Playwright Python 包与 Chromium：

```bash
uv sync --frozen --all-packages --all-extras --python 3.11
uv run playwright install chromium
```

Chromium 会被下载到 Playwright 的用户缓存，而不是仓库。基础 CI 不安装 Playwright 浏览器；相关测试通过依赖边界和错误信息进行验证。

## 测试与构建

分别运行 Python 测试：

```bash
uv run --frozen --package report-skill-server pytest apps/server/tests tests/e2e/test_mvp_report_flow.py
uv run --frozen --package report-skill-engine pytest packages/skill_engine/tests
uv run --frozen --package report-skill-renderer pytest packages/report_renderer/tests
```

运行前端测试和生产构建：

```bash
pnpm test:web
pnpm build:web
```

GitHub Actions 会把 server、Skill engine、report renderer 和 web 分为四个独立 job。Python job 固定使用 3.11；web job 固定使用 Node 22 与 pnpm 11.19.0。

## 数据目录与隐私边界

默认数据位于仓库根目录的 `data/`：

```text
data/
├── report-skill-studio.sqlite3
├── artifacts/
└── skills/
```

SQLite 保存项目、逐字稿、结构化报告、版本及用户确认过的术语记忆；PDF 渲染过程的本地文件位于 `artifacts/`；从界面安装的用户 Skill 位于 `skills/`。`data/`、数据库文件、`.env` 与常见模型目录都被 Git 忽略。修改 `RSS_DATA_DIR` 可以把运行数据放到仓库外的绝对路径。

生成后的可读文档另外同步到 Markdown 项目库，初始位置由 `RSS_PROJECTS_DIR` 指定，默认是 `~/Documents/Report Skill Studio`。用户在左侧设置中保存新路径后，SQLite 中的本地选择优先于环境变量初始值。项目库采用普通目录：

```text
Report Skill Studio/
└── 项目名称/
    └── 2026-08-26 周会纪要.md
```

项目文件夹只由工作台创建 `.md` 文件。Markdown 属性区包含报告 ID、项目、日期、状态和 Skill；正文使用标准标题、列表和表格，提示内容使用 Obsidian callout 语法。应用每次保存前会比较上次同步哈希；若文件已在 Obsidian 或其他编辑器中改变，会暂停覆盖并在界面提示冲突。当同日期、同标题发生冲突时，数字后缀会同时写入系统报告标题和 Markdown 标题，而不是只修改文件名。当前版本不会把外部 Markdown 修改反向导入结构化编辑器。

HTML 和 PDF 只在用户点击相应导出按钮时下载，不写入 Markdown 项目文件夹。工作台通过绝对路径文本框修改项目库位置。

用户 Skill 以 ZIP 原始内容上传到本地 API，限制为 8 MB 压缩包、25 MB 解压内容和 200 个文件。服务端拒绝路径穿越、符号链接、加密条目、不安全模板和当前工作台无法编辑的报告 Schema。内置 Skill 不能替换或删除；被已有报告引用的用户 Skill 也不能删除，避免历史报告失去渲染规则。

未确认报告采用“工作副本 + 检查点”两层持久化：编辑停止约 0.8 秒后，标题、逐字稿和结构化内容会写入工作副本，但不会增加版本号；模型生成、确认前保存和主动恢复才形成可恢复版本。已确认报告保持不可变，恢复其中的历史版本时会创建一份新的未确认草稿。前端会比较当前工作副本与最近检查点，保守提取短文本修改作为专词候选；候选只有在用户点击“记住”后才写入长期项目记忆。

默认前端只连接 `127.0.0.1`；`mock` provider、本地数据库、Skill 加载、校验和 HTML/PDF 渲染都不向外部服务发送数据。只有用户明确配置并选择云端 provider 时，生成请求所需的逐字稿、Skill 指令和 JSON Schema 才会发送到该 provider 的 `base_url`。把 `VITE_API_BASE_URL` 改成远程地址也会让浏览器把工作台请求发送到该地址，因此只能配置为自己信任的服务。API 密钥只从服务端运行环境读取，不应持久化到 SQLite、浏览器存储或日志。

“隐私与数据管理”中的项目备份包含项目元数据、逐字稿、报告、版本、确认术语和 Markdown，不含运行环境或 API 密钥。清空历史和删除项目会先校验工作台上次写入的 Markdown 内容哈希；外部修改过的文件会触发 `409` 冲突，数据库和本地文件均保持不变。

Skill 必须保持声明式：模板、Schema、术语和校验规则不能执行任意 Python 或 JavaScript。只有用户明确确认的纠错可以进入长期记忆。

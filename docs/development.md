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
| `RSS_CORS_ORIGINS` | 逗号分隔的前端来源列表 |
| `RSS_OPENAI_COMPATIBLE_BASE_URL` | 可选兼容服务地址，不含 `/chat/completions` |
| `RSS_OPENAI_COMPATIBLE_API_KEY` | 可选兼容服务密钥 |
| `RSS_OPENAI_COMPATIBLE_MODEL` | 可选模型标识 |
| `VITE_API_BASE_URL` | 前端访问的 API 地址，默认 `http://127.0.0.1:8000/api` |
| `VITE_USE_MOCK_API` | 设为 `true` 时显式启用前端 mock API；默认 `false` |

三个 OpenAI-compatible 变量同时设置后，服务端才会注册 `openai-compatible` provider；保持为空时，开发环境只提供不会联网的 `mock` provider。

`.env` 已被 Git 忽略，但它仍是本机上的明文文件。真实密钥更适合在启动前通过 shell 或系统密钥管理工具注入，例如：

```bash
export RSS_OPENAI_COMPATIBLE_BASE_URL="https://provider.example/v1"
export RSS_OPENAI_COMPATIBLE_API_KEY="replace-in-your-shell-only"
export RSS_OPENAI_COMPATIBLE_MODEL="your-model-id"
```

不要把真实密钥写入 `.env.example`、测试夹具、SQLite、日志或提交记录。

## 启动服务端

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

## 启动前端

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

当前仓库以开发模式运行：服务端和前端各占用一个常驻进程。Mac 只是进入睡眠、终端窗口和进程仍保留时，唤醒后通常可以直接继续使用，不需要重新启动；关闭对应终端、结束进程或重启电脑后，需要重新运行启动命令。

面向普通用户发布时，推荐把前端和本地服务封装为 Tauri 桌面应用，由应用图标负责启动和停止本地服务，这样不需要用户接触终端。开发阶段可以补充双击启动脚本作为过渡方案，但它不替代正式的桌面安装包。

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
└── artifacts/
```

SQLite 保存项目、逐字稿、报告、版本及用户确认过的术语记忆；导出的 PDF 等文件位于 `artifacts/`。`data/`、数据库文件、`.env` 与常见模型目录都被 Git 忽略。修改 `RSS_DATA_DIR` 可以把数据放到仓库外的绝对路径。

默认前端只连接 `127.0.0.1`；`mock` provider、本地数据库、Skill 加载、校验和 HTML/PDF 渲染都不向外部服务发送数据。只有用户明确配置并选择云端 provider 时，生成请求所需的逐字稿、Skill 指令和 JSON Schema 才会发送到该 provider 的 `base_url`。把 `VITE_API_BASE_URL` 改成远程地址也会让浏览器把工作台请求发送到该地址，因此只能配置为自己信任的服务。API 密钥只从服务端运行环境读取，不应持久化到 SQLite、浏览器存储或日志。

Skill 必须保持声明式：模板、Schema、术语和校验规则不能执行任意 Python 或 JavaScript。只有用户明确确认的纠错可以进入长期记忆。

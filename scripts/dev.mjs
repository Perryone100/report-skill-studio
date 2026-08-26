import { existsSync, readFileSync } from 'node:fs'
import { spawn, spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const repositoryRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const apiHealthUrl = 'http://127.0.0.1:8000/api/health'
const webUrl = 'http://127.0.0.1:4173'
const isDoctor = process.argv.includes('--doctor')
const children = new Set()
let stopping = false

function commandName(name) {
  return process.platform === 'win32' ? `${name}.cmd` : name
}

function commandVersion(command, args = ['--version']) {
  const result = spawnSync(commandName(command), args, {
    cwd: repositoryRoot,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'ignore'],
  })
  return result.status === 0 ? result.stdout.trim() : ''
}

function webRunner() {
  const pnpmVersion = commandVersion('pnpm')
  if (pnpmVersion) {
    return {
      command: 'pnpm',
      args: ['dev:web'],
      description: `pnpm ${pnpmVersion}`,
    }
  }
  const npmVersion = commandVersion('npm')
  if (npmVersion) {
    return {
      command: 'npm',
      args: ['--prefix', 'apps/web', 'run', 'dev'],
      description: `npm ${npmVersion}（pnpm 未安装，使用兼容启动）`,
    }
  }
  return null
}

function readLocalEnvironment() {
  const values = { ...process.env }
  const path = join(repositoryRoot, '.env')
  if (!existsSync(path)) return { values, exists: false }
  for (const line of readFileSync(path, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/)
    if (!match || values[match[1]]) continue
    let value = match[2]
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1)
    }
    values[match[1]] = value
  }
  return { values, exists: true }
}

async function reachable(url, timeout = 900) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(timeout) })
    return response.ok
  } catch {
    return false
  }
}

async function waitUntilReachable(url, label, milliseconds = 30000) {
  const deadline = Date.now() + milliseconds
  while (Date.now() < deadline) {
    if (await reachable(url)) return
    await new Promise((resolve) => setTimeout(resolve, 350))
  }
  throw new Error(`${label} 未在 ${Math.round(milliseconds / 1000)} 秒内就绪：${url}`)
}

function start(command, args, label) {
  const child = spawn(commandName(command), args, {
    cwd: repositoryRoot,
    env: process.env,
    stdio: 'inherit',
  })
  children.add(child)
  child.on('exit', (code, signal) => {
    children.delete(child)
    if (stopping) return
    const reason = signal ? `信号 ${signal}` : `退出码 ${code}`
    console.error(`\n${label} 已停止（${reason}）。`)
    stop(code || 1)
  })
  child.on('error', (error) => {
    console.error(`${label} 无法启动：${error.message}`)
    stop(1)
  })
  return child
}

function openBrowser(url) {
  if (process.env.RSS_NO_OPEN === 'true') return
  const command = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'cmd' : 'xdg-open'
  const args = process.platform === 'win32' ? ['/c', 'start', '', url] : [url]
  const opener = spawn(command, args, { detached: true, stdio: 'ignore' })
  opener.unref()
}

function stop(exitCode = 0) {
  if (stopping) return
  stopping = true
  for (const child of children) child.kill('SIGTERM')
  setTimeout(() => {
    for (const child of children) child.kill('SIGKILL')
    process.exit(exitCode)
  }, 1200).unref()
  if (children.size === 0) process.exit(exitCode)
}

async function doctor() {
  const nodeVersion = process.versions.node
  const nodeMajor = Number(nodeVersion.split('.')[0])
  const uvVersion = commandVersion('uv')
  const runner = webRunner()
  const environment = readLocalEnvironment()
  const configuredLegacyProvider = [
    environment.values.RSS_OPENAI_COMPATIBLE_BASE_URL,
    environment.values.RSS_OPENAI_COMPATIBLE_API_KEY,
    environment.values.RSS_OPENAI_COMPATIBLE_MODELS || environment.values.RSS_OPENAI_COMPATIBLE_MODEL,
  ].every((value) => Boolean(value?.trim()))
  const connectionConfig = environment.values.RSS_OPENAI_COMPATIBLE_CONNECTIONS?.trim()
  const configuredProvider = configuredLegacyProvider || Boolean(connectionConfig && connectionConfig !== '[]')
  const pythonEnvironment = existsSync(join(repositoryRoot, '.venv'))
  const webDependencies = existsSync(join(repositoryRoot, 'apps', 'web', 'node_modules'))
  const apiRunning = await reachable(apiHealthUrl)
  const webRunning = await reachable(webUrl)

  const checks = [
    [nodeMajor >= 22, `Node.js ${nodeVersion}`, '需要 Node.js 22 或更高版本'],
    [Boolean(runner), runner?.description || '未找到 npm 或 pnpm', '请先安装 Node.js（需包含 npm）'],
    [Boolean(uvVersion), uvVersion || 'uv 未找到', '请先安装 uv'],
    [pythonEnvironment, 'Python 工作区依赖已安装', '运行 uv sync --frozen --all-packages --extra dev --extra test --python 3.11'],
    [webDependencies, 'Web 依赖已安装', '运行 pnpm install --frozen-lockfile --ignore-scripts'],
  ]

  console.log('Report Skill Studio 环境诊断\n')
  for (const [ok, success, failure] of checks) {
    console.log(`${ok ? '✓' : '✗'} ${ok ? success : failure}`)
  }
  console.log(`${environment.exists ? '✓' : '○'} 根目录 .env ${environment.exists ? '已找到' : '未创建（可从 .env.example 复制）'}`)
  console.log(`${configuredProvider ? '✓' : '○'} 云模型配置${configuredProvider ? '完整' : '未完整配置；仍可使用本地 mock 模型'}`)
  console.log(`${apiRunning ? '✓' : '○'} 本地 API ${apiRunning ? '正在运行' : '尚未启动'}`)
  console.log(`${webRunning ? '✓' : '○'} Web 工作台 ${webRunning ? '正在运行' : '尚未启动'}`)
  console.log('○ PDF 为可选能力；首次导出前请按开发文档安装 Playwright 与 Chromium。')

  if (checks.some(([ok]) => !ok)) process.exitCode = 1
}

async function dev() {
  const missing = []
  if (!commandVersion('uv')) missing.push('uv')
  const runner = webRunner()
  if (!runner) missing.push('npm 或 pnpm')
  if (missing.length) throw new Error(`缺少开发工具：${missing.join('、')}。请先运行 npm run doctor 查看安装说明。`)

  process.on('SIGINT', () => stop(0))
  process.on('SIGTERM', () => stop(0))

  const apiWasRunning = await reachable(apiHealthUrl)
  const webWasRunning = await reachable(webUrl)
  if (!apiWasRunning) {
    console.log('启动本地 API：http://127.0.0.1:8000')
    start('uv', [
      'run', '--frozen', '--package', 'report-skill-server',
      'uvicorn', 'report_skill_server.main:app',
      '--app-dir', 'apps/server/src', '--host', '127.0.0.1', '--port', '8000', '--reload',
    ], '本地 API')
  } else {
    console.log('复用已运行的本地 API：http://127.0.0.1:8000')
  }

  if (!webWasRunning) {
    console.log('启动 Web 工作台：http://127.0.0.1:4173')
    start(runner.command, runner.args, 'Web 工作台')
  } else {
    console.log('复用已运行的 Web 工作台：http://127.0.0.1:4173')
  }

  await Promise.all([
    waitUntilReachable(apiHealthUrl, '本地 API'),
    waitUntilReachable(webUrl, 'Web 工作台'),
  ])
  console.log(`\n工作台已就绪：${webUrl}`)
  console.log('保持这个终端窗口运行；按 Control+C 同时停止本次启动的服务。')
  openBrowser(webUrl)

  if (apiWasRunning && webWasRunning) {
    console.log('两个服务都已由其他进程运行，本命令无需常驻。')
  }
}

try {
  if (isDoctor) await doctor()
  else await dev()
} catch (error) {
  console.error(`\n启动失败：${error instanceof Error ? error.message : String(error)}`)
  stop(1)
}

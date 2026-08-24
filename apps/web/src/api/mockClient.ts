import { ApiError, type WorkbenchApi } from './client'
import type {
  ExportArtifact,
  GenerateReportInput,
  ReportDraft,
  TerminologyMemoryEntry,
  WorkspaceBootstrap,
} from './types'

const wait = (milliseconds: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(resolve, milliseconds)
    signal?.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timer)
        reject(new DOMException('请求已取消', 'AbortError'))
      },
      { once: true },
    )
  })

const createId = () =>
  typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `mock-${Date.now()}-${Math.random().toString(16).slice(2)}`

const bootstrap: WorkspaceBootstrap = {
  projects: [
    {
      id: 'demo-product',
      name: '演示产品组',
      description: '完全虚构的产品与研发协作示例',
      status: 'active',
      updatedAt: '2026-08-24T09:30:00+08:00',
    },
    {
      id: 'demo-platform',
      name: '演示平台组',
      description: '完全虚构的平台能力建设示例',
      status: 'active',
      updatedAt: '2026-08-21T18:10:00+08:00',
    },
  ],
  reports: [
    {
      id: 'report-demo-latest',
      projectId: 'demo-product',
      title: '产品研发周会纪要',
      period: '2026.08.17—2026.08.21',
      status: 'exported',
      updatedAt: '2026-08-21T19:20:00+08:00',
    },
    {
      id: 'report-demo-previous',
      projectId: 'demo-product',
      title: '产品研发周会纪要（上期）',
      period: '2026.08.10—2026.08.14',
      status: 'confirmed',
      updatedAt: '2026-08-14T18:42:00+08:00',
    },
  ],
  skills: [
    {
      id: 'default-weekly-meeting@0.2.1',
      name: '通用周会纪要',
      version: '0.2.1',
      description: '按固定工作维度整理进展、计划与风险。',
    },
  ],
  models: [
    {
      id: 'openai-compatible:example-writing-standard',
      name: 'example-writing-standard',
      provider: 'OpenAI-compatible API',
      locality: 'cloud',
      ready: true,
    },
    {
      id: 'openai-compatible:example-writing-economy',
      name: 'example-writing-economy',
      provider: 'OpenAI-compatible API',
      locality: 'cloud',
      ready: true,
    },
  ],
}

const terminologyMemory: TerminologyMemoryEntry[] = [
  {
    id: 'term-demo-1',
    projectId: 'demo-product',
    sourceValue: '模块爱',
    normalizedValue: '功能模块 A',
    scope: 'project',
    updatedAt: '2026-08-24T09:30:00+08:00',
  },
]

function buildDraft(input: GenerateReportInput): ReportDraft {
  const transcriptPreview = input.transcript
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 96)

  return {
    reportId: createId(),
    title: input.title,
    meeting_date: '2026-08-21',
    executive_summary:
      '本周核心工作进入联调和验收阶段；功能模块 A 已完成关键链路验证，当前需关注跨团队测试数据依赖。',
    summary_cards: [
      { label: '本周阶段', value: '重点功能进入联调', tone: 'info' },
      { label: '核心进展', value: '关键链路验证完成', tone: 'success' },
      { label: '重点风险', value: '1 项依赖待协调', tone: 'warning' },
    ],
    sections: [
      {
        id: 'overall_conclusion',
        title: '本周整体结论',
        blocks: [
          {
            type: 'paragraph',
            text: `已完成需求梳理与核心链路联调。逐字稿摘要：${transcriptPreview}`,
          },
        ],
      },
      {
        id: 'this_week_progress',
        title: '本周工作进展',
        blocks: [
          {
            type: 'project_table',
            columns: ['工作项', '本周进展', '当前状态', '下一步'],
            rows: [
              ['功能模块 A', '核心链路联调完成', '进行中', '验收后安排灰度'],
              ['活动页面 C', '配置与数据回传进入 UAT', '进行中', '完成全场景验收'],
              ['平台监控', '稳定性优化完成', '已完成', '补充成本统计和异常告警'],
            ],
          },
        ],
      },
      {
        id: 'next_week_plan',
        title: '下周重点计划',
        blocks: [
          {
            type: 'bullet_list',
            items: [
              '完成功能模块 A 验收并启动灰度。',
              '收口活动页面 C 的 UAT 问题。',
              '补齐平台监控的成本统计与异常告警。',
            ],
          },
        ],
      },
      {
        id: 'risks_and_coordination',
        title: '风险与待协调事项',
        blocks: [
          {
            type: 'callout',
            title: '验收资源依赖',
            text: '上线窗口较紧，需提前锁定业务验收人员并明确测试数据交付时间。',
            tone: 'warning',
          },
        ],
      },
    ],
  }
}

export const mockApiClient: WorkbenchApi = {
  async getWorkspace(signal) {
    await wait(450, signal)
    return structuredClone(bootstrap)
  },

  async createProject(input, signal) {
    await wait(300, signal)
    const project = {
      id: createId(),
      name: input.name,
      description: input.description,
      status: 'active' as const,
      updatedAt: new Date().toISOString(),
    }
    bootstrap.projects.push(project)
    return structuredClone(project)
  },

  async listTerminologyMemory(projectId, signal) {
    await wait(180, signal)
    return structuredClone(terminologyMemory.filter((item) => !item.projectId || item.projectId === projectId))
  },

  async saveTerminologyMemory(input, signal) {
    await wait(220, signal)
    const existing = terminologyMemory.find((item) =>
      item.projectId === input.projectId
      && item.sourceValue.toLocaleLowerCase() === input.sourceValue.toLocaleLowerCase())
    if (existing) {
      existing.normalizedValue = input.normalizedValue
      existing.updatedAt = new Date().toISOString()
      return structuredClone(existing)
    }
    const memory: TerminologyMemoryEntry = {
      id: createId(),
      projectId: input.projectId,
      sourceValue: input.sourceValue,
      normalizedValue: input.normalizedValue,
      scope: 'project',
      updatedAt: new Date().toISOString(),
    }
    terminologyMemory.unshift(memory)
    return structuredClone(memory)
  },

  async deleteTerminologyMemory(memoryId, signal) {
    await wait(180, signal)
    const index = terminologyMemory.findIndex((item) => item.id === memoryId)
    if (index >= 0) terminologyMemory.splice(index, 1)
  },

  async generateReport(input, signal) {
    if (input.transcript.includes('[触发错误]')) {
      await wait(350, signal)
      throw new ApiError('模拟模型服务暂时不可用，请稍后重试。', 'MODEL_UNAVAILABLE')
    }
    await wait(900, signal)
    return { report: buildDraft(input), issues: [], confirmed: false }
  },

  async confirmReport(report, signal) {
    await wait(350, signal)
    return { report: structuredClone(report), issues: [], confirmed: true }
  },

  async exportReport(report, signal): Promise<ExportArtifact> {
    await wait(450, signal)
    const { reportId: _reportId, ...content } = report
    const escaped = JSON.stringify(content, null, 2)
    const html = `<!doctype html><html lang="zh-CN"><meta charset="UTF-8"><title>${report.title}</title><body><pre>${escaped}</pre></body></html>`
    return {
      blob: new Blob([html], { type: 'text/html;charset=utf-8' }),
      fileName: `${report.title.replace(/[\\/:*?"<>|]/g, '-')}-Mock预览.html`,
      mock: true,
    }
  },
}

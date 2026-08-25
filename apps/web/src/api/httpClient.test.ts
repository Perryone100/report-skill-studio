import { describe, expect, it, vi } from 'vitest'
import type { ReportDraft } from './types'
import { createHttpApiClient, stripReportMetadata } from './httpClient'

const jsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

const content = {
  title: '产品研发周会纪要',
  meeting_date: '2026-08-21',
  executive_summary: '本周整体按计划推进。',
  summary_cards: [{ label: '本周阶段', value: '进入联调', tone: 'info' }],
  sections: [
    {
      id: 'overall_conclusion',
      title: '本周整体结论',
      blocks: [{ type: 'paragraph', text: '核心链路联调完成。' }],
    },
  ],
} satisfies Omit<ReportDraft, 'reportId'>

const apiReport = (status: 'draft' | 'confirmed' = 'draft') => ({
  id: 'report-1',
  project_id: 'project-1',
  title: content.title,
  transcript: '测试逐字稿',
  skill_id: 'default-weekly-meeting',
  content,
  status,
  version: 2,
  created_at: '2026-08-21T10:00:00Z',
  updated_at: '2026-08-21T11:00:00Z',
})

describe('HTTP API client', () => {
  it('组合工作区接口并映射前端类型', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input)).pathname
      if (path.endsWith('/projects')) return jsonResponse([{ id: 'project-1', name: '产品研发', description: '周会', created_at: '2026-08-21T10:00:00Z', updated_at: '2026-08-21T11:00:00Z' }])
      if (path.endsWith('/reports')) return jsonResponse([apiReport()])
      if (path.endsWith('/skills')) return jsonResponse([{ id: 'default-weekly-meeting', name: '默认周会', version: '0.2.1', description: '通用周会报告', locale: 'zh-CN' }])
      if (path.endsWith('/providers')) return jsonResponse([
        { id: 'mock', name: '本地演示模型', model: 'deterministic-mock', local: true, configured: true },
        { id: 'openai-compatible:writing-economy', name: 'OpenAI-compatible API', model: 'writing-economy', local: false, configured: true },
      ])
      return jsonResponse({ detail: 'not found' }, 404)
    })
    const client = createHttpApiClient('http://localhost:8000/api/', fetchMock as typeof fetch)

    const workspace = await client.getWorkspace()

    expect(workspace.projects[0]).toMatchObject({ id: 'project-1', status: 'active' })
    expect(workspace.reports[0]).toMatchObject({ id: 'report-1', period: '2026-08-21' })
    expect(workspace.skills[0].id).toBe('default-weekly-meeting')
    expect(workspace.models[0]).toMatchObject({ id: 'mock', locality: 'local', ready: true })
    expect(workspace.models[1]).toMatchObject({
      id: 'openai-compatible:writing-economy',
      name: 'writing-economy',
      provider: 'OpenAI-compatible API',
    })
    expect(fetchMock).toHaveBeenCalledTimes(4)
  })

  it('按 create → generate → fetch → validation 组合生成流程', async () => {
    const paths: string[] = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input)).pathname
      paths.push(`${init?.method ?? 'GET'} ${path}`)
      if (path.endsWith('/reports') && init?.method === 'POST') return jsonResponse({ ...apiReport(), content: {} }, 201)
      if (path.endsWith('/reports/report-1/generate')) return jsonResponse({ id: 'job-1', status: 'succeeded', error: null })
      if (path.endsWith('/reports/report-1/validation')) return jsonResponse({
        valid: true,
        issues: [{ code: 'section.empty', severity: 'warning', message: '章节内容较少', path: '$.sections[0]', suggestion: '补充关键进展' }],
      })
      if (path.endsWith('/reports/report-1')) return jsonResponse(apiReport())
      return jsonResponse({ detail: 'not found' }, 404)
    })
    const client = createHttpApiClient('http://localhost:8000/api', fetchMock as typeof fetch)

    const result = await client.generateReport({
      projectId: 'project-1',
      title: '产品研发周会纪要',
      transcript: '这是一段长度足够的逐字稿。',
      skillId: 'default-weekly-meeting',
      modelId: 'mock',
    })

    expect(result.report.reportId).toBe('report-1')
    expect(result.report.executive_summary).toBe(content.executive_summary)
    expect(result.issues[0]).toMatchObject({ source: 'server', severity: 'warning', suggestion: '补充关键进展' })
    expect(paths).toEqual([
      'POST /api/reports',
      'POST /api/reports/report-1/generate',
      'GET /api/reports/report-1',
      'GET /api/reports/report-1/validation',
    ])
  })

  it('仅在用户提交后创建项目', async () => {
    let body: Record<string, unknown> | undefined
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      body = JSON.parse(String(init?.body)) as Record<string, unknown>
      return jsonResponse({
        id: 'project-new',
        name: body.name,
        description: body.description,
        created_at: '2026-08-24T10:00:00Z',
        updated_at: '2026-08-24T10:00:00Z',
      }, 201)
    })
    const client = createHttpApiClient('http://localhost:8000/api', fetchMock as typeof fetch)

    const project = await client.createProject({ name: '演示项目', description: '虚构周会' })

    expect(body).toEqual({ name: '演示项目', description: '虚构周会' })
    expect(project).toMatchObject({ id: 'project-new', name: '演示项目', status: 'active' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('加载历史详情、自动保存工作副本并恢复版本', async () => {
    const requests: Array<{ path: string; method: string; body?: Record<string, unknown> }> = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input)).pathname
      const method = init?.method ?? 'GET'
      requests.push({
        path,
        method,
        body: init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : undefined,
      })
      if (path.endsWith('/versions/2/restore')) return jsonResponse(apiReport())
      if (path.endsWith('/versions')) return jsonResponse([
        {
          id: 'version-2', report_id: 'report-1', version: 2, title: content.title,
          transcript: '测试逐字稿', content, reason: 'generated', created_at: '2026-08-21T11:00:00Z',
        },
        {
          id: 'version-1', report_id: 'report-1', version: 1, title: content.title,
          transcript: '测试逐字稿', content: {}, reason: 'created', created_at: '2026-08-21T10:00:00Z',
        },
      ])
      if (path.endsWith('/validation')) return jsonResponse({ valid: true, issues: [] })
      if (path.endsWith('/draft') && method === 'PATCH') return jsonResponse(apiReport())
      if (path.endsWith('/reports/report-1')) return jsonResponse(apiReport())
      return jsonResponse({ detail: 'not found' }, 404)
    })
    const client = createHttpApiClient('http://localhost:8000/api', fetchMock as typeof fetch)

    const loaded = await client.loadReport('report-1')
    const saveResult = await client.saveReportDraft(loaded.draft!, '修改后的逐字稿')
    const restored = await client.restoreReportVersion('report-1', 2)

    expect(loaded).toMatchObject({ reportId: 'report-1', version: 2, status: 'draft' })
    expect(loaded.versions.map((version) => version.hasContent)).toEqual([true, false])
    expect(saveResult.version).toBe(2)
    expect(restored.draft?.reportId).toBe('report-1')
    const autosave = requests.find((request) => request.path.endsWith('/draft'))
    expect(autosave?.body?.transcript).toBe('修改后的逐字稿')
    expect((autosave?.body?.content as Record<string, unknown>).reportId).toBeUndefined()
    expect(requests.some((request) => request.method === 'POST' && request.path.endsWith('/versions/2/restore'))).toBe(true)
  })

  it('管理项目专词并使用确认后的矫正规则', async () => {
    const paths: string[] = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input))
      paths.push(`${init?.method ?? 'GET'} ${url.pathname}${url.search}`)
      if (init?.method === 'DELETE') return new Response(null, { status: 204 })
      const memory = {
        id: 'term-1',
        project_id: 'project-1',
        source_value: '模块爱',
        normalized_value: '功能模块 A',
        scope: 'project',
        confirmed: true,
        created_at: '2026-08-24T10:00:00Z',
        updated_at: '2026-08-24T11:00:00Z',
      }
      return jsonResponse(init?.method === 'POST' ? memory : [memory])
    })
    const client = createHttpApiClient('http://localhost:8000/api', fetchMock as typeof fetch)

    const saved = await client.saveTerminologyMemory({
      projectId: 'project-1',
      sourceValue: '模块爱',
      normalizedValue: '功能模块 A',
    })
    const listed = await client.listTerminologyMemory('project-1')
    await client.deleteTerminologyMemory(saved.id)

    expect(saved).toMatchObject({ sourceValue: '模块爱', normalizedValue: '功能模块 A', scope: 'project' })
    expect(listed).toEqual([saved])
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      project_id: 'project-1',
      source_value: '模块爱',
      normalized_value: '功能模块 A',
      scope: 'project',
      confirmed: true,
    })
    expect(paths).toEqual([
      'POST /api/memory/terms',
      'GET /api/memory/terms?project_id=project-1',
      'DELETE /api/memory/terms/term-1',
    ])
  })

  it('保存时剥离 reportId，并在校验通过后确认', async () => {
    let patchPayload: Record<string, unknown> | undefined
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input)).pathname
      if (path.endsWith('/reports/report-1') && init?.method === 'PATCH') {
        patchPayload = JSON.parse(String(init.body)) as Record<string, unknown>
        return jsonResponse(apiReport())
      }
      if (path.endsWith('/reports/report-1/validation')) return jsonResponse({ valid: true, issues: [] })
      if (path.endsWith('/reports/report-1/confirm')) return jsonResponse(apiReport('confirmed'))
      return jsonResponse({ detail: 'not found' }, 404)
    })
    const client = createHttpApiClient('http://localhost:8000/api', fetchMock as typeof fetch)
    const draft: ReportDraft = { ...content, reportId: 'report-1' }

    const result = await client.confirmReport(draft, '测试逐字稿')

    expect(result.confirmed).toBe(true)
    expect(patchPayload?.transcript).toBe('测试逐字稿')
    expect((patchPayload?.content as Record<string, unknown>).reportId).toBeUndefined()
    expect(stripReportMetadata(draft)).toEqual(content)
  })
})

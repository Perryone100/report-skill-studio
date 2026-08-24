import { ApiError, type WorkbenchApi } from './client'
import type {
  CreateProjectInput,
  ExportArtifact,
  GenerateReportInput,
  IssueSeverity,
  ModelOption,
  ProjectSummary,
  ReportContent,
  ReportDraft,
  ReportOperationResult,
  ReportSummary,
  SaveTerminologyMemoryInput,
  SkillOption,
  TerminologyMemoryEntry,
  ValidationIssue,
  WorkspaceBootstrap,
} from './types'

interface ApiProject {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
}

interface ApiReport {
  id: string
  project_id: string
  title: string
  transcript: string
  skill_id: string
  content: ReportContent
  status: 'draft' | 'confirmed'
  version: number
  created_at: string
  updated_at: string
}

interface ApiProvider {
  id: string
  name: string
  model: string
  local: boolean
  configured: boolean
}

interface ApiSkill {
  id: string
  name: string
  version: string
  description: string
  locale: string
}

interface ApiJob {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  error: string | null
}

interface ApiTerminologyMemory {
  id: string
  project_id: string | null
  source_value: string
  normalized_value: string
  scope: 'global' | 'project' | 'temporary'
  confirmed: boolean
  created_at: string
  updated_at: string
}

interface ApiValidationIssue {
  code: string
  severity: IssueSeverity
  message: string
  path?: string | null
  suggestion?: string | null
}

interface ApiValidationResult {
  valid: boolean
  issues: ApiValidationIssue[]
}

type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

const issueTitles: Record<string, string> = {
  'schema.invalid': '内容结构不符合 Skill',
  'section.missing': '缺少必填章节',
  'section.empty': '必填章节为空',
  'phrase.forbidden': '页面标签建议',
  'terminology.noncanonical': '术语不一致',
}

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, '')
}

async function errorMessage(response: Response) {
  try {
    const payload = await response.json() as { detail?: unknown }
    if (typeof payload.detail === 'string') return payload.detail
    if (payload.detail) return JSON.stringify(payload.detail)
  } catch {
    // Non-JSON failures fall back to the HTTP status below.
  }
  return `请求失败（HTTP ${response.status}）`
}

function mapProject(project: ApiProject): ProjectSummary {
  return {
    id: project.id,
    name: project.name,
    description: project.description,
    status: 'active',
    updatedAt: project.updated_at,
  }
}

function mapReportSummary(report: ApiReport): ReportSummary {
  const meetingDate = report.content?.meeting_date
  return {
    id: report.id,
    projectId: report.project_id,
    title: report.title,
    period: meetingDate || report.created_at.slice(0, 10),
    status: report.status,
    updatedAt: report.updated_at,
  }
}

function mapSkill(skill: ApiSkill): SkillOption {
  return {
    id: skill.id,
    name: skill.name,
    version: skill.version,
    description: skill.description,
  }
}

function mapProvider(provider: ApiProvider): ModelOption {
  return {
    id: provider.id,
    name: provider.name,
    provider: provider.model,
    locality: provider.local ? 'local' : 'cloud',
    ready: provider.configured,
  }
}

function mapTerminologyMemory(memory: ApiTerminologyMemory): TerminologyMemoryEntry {
  return {
    id: memory.id,
    projectId: memory.project_id ?? undefined,
    sourceValue: memory.source_value,
    normalizedValue: memory.normalized_value,
    scope: memory.scope,
    updatedAt: memory.updated_at,
  }
}

function mapDraft(report: ApiReport): ReportDraft {
  const content = report.content
  if (!content || !Array.isArray(content.sections) || !Array.isArray(content.summary_cards)) {
    throw new ApiError('服务端返回的报告内容结构不完整。', 'INVALID_RESPONSE')
  }
  return { ...content, reportId: report.id }
}

function mapValidation(result: ApiValidationResult): ValidationIssue[] {
  return result.issues.map((issue, index) => ({
    id: `server-${issue.code}-${issue.path ?? 'report'}-${index}`,
    severity: issue.severity,
    title: issueTitles[issue.code] ?? '服务端检查提示',
    message: issue.message,
    field: issue.path ?? undefined,
    source: 'server',
    suggestion: issue.suggestion ?? undefined,
  }))
}

/** Remove UI-only fields before sending canonical report content to the server. */
export function stripReportMetadata(report: ReportDraft): ReportContent {
  const { reportId: _reportId, ...content } = report
  return content
}

export function createHttpApiClient(
  baseUrl = 'http://127.0.0.1:8000/api',
  fetchImpl: FetchLike = fetch,
): WorkbenchApi {
  const apiBaseUrl = trimTrailingSlash(baseUrl)

  const requestJson = async <Result>(path: string, init: RequestInit = {}, signal?: AbortSignal) => {
    let response: Response
    try {
      response = await fetchImpl(`${apiBaseUrl}${path}`, {
        ...init,
        signal,
        headers: {
          ...(init.body ? { 'Content-Type': 'application/json' } : {}),
          ...init.headers,
        },
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new ApiError('无法连接本地服务，请确认 FastAPI 已启动。', 'NETWORK_ERROR')
    }
    if (!response.ok) {
      throw new ApiError(await errorMessage(response), `HTTP_${response.status}`)
    }
    try {
      return await response.json() as Result
    } catch {
      throw new ApiError('服务端返回了无法解析的数据。', 'INVALID_RESPONSE')
    }
  }

  const requestValidation = async (reportId: string, signal?: AbortSignal) =>
    requestJson<ApiValidationResult>(`/reports/${reportId}/validation`, {}, signal)

  const requestVoid = async (path: string, init: RequestInit, signal?: AbortSignal) => {
    let response: Response
    try {
      response = await fetchImpl(`${apiBaseUrl}${path}`, { ...init, signal })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new ApiError('无法连接本地服务，请确认 FastAPI 已启动。', 'NETWORK_ERROR')
    }
    if (!response.ok) throw new ApiError(await errorMessage(response), `HTTP_${response.status}`)
  }

  return {
    async getWorkspace(signal): Promise<WorkspaceBootstrap> {
      const [projects, reports, skills, providers] = await Promise.all([
        requestJson<ApiProject[]>('/projects', {}, signal),
        requestJson<ApiReport[]>('/reports', {}, signal),
        requestJson<ApiSkill[]>('/skills', {}, signal),
        requestJson<ApiProvider[]>('/providers', {}, signal),
      ])
      return {
        projects: projects.map(mapProject),
        reports: reports.map(mapReportSummary),
        skills: skills.map(mapSkill),
        models: providers.map(mapProvider),
      }
    },

    async createProject(input: CreateProjectInput, signal) {
      const project = await requestJson<ApiProject>('/projects', {
        method: 'POST',
        body: JSON.stringify({ name: input.name, description: input.description }),
      }, signal)
      return mapProject(project)
    },

    async listTerminologyMemory(projectId, signal) {
      const memories = await requestJson<ApiTerminologyMemory[]>(
        `/memory/terms?project_id=${encodeURIComponent(projectId)}`,
        {},
        signal,
      )
      return memories.map(mapTerminologyMemory)
    },

    async saveTerminologyMemory(input: SaveTerminologyMemoryInput, signal) {
      const memory = await requestJson<ApiTerminologyMemory>('/memory/terms', {
        method: 'POST',
        body: JSON.stringify({
          project_id: input.projectId,
          source_value: input.sourceValue,
          normalized_value: input.normalizedValue,
          scope: 'project',
          confirmed: true,
        }),
      }, signal)
      return mapTerminologyMemory(memory)
    },

    async deleteTerminologyMemory(memoryId, signal) {
      await requestVoid(`/memory/terms/${encodeURIComponent(memoryId)}`, { method: 'DELETE' }, signal)
    },

    async generateReport(input: GenerateReportInput, signal): Promise<ReportOperationResult> {
      const created = await requestJson<ApiReport>('/reports', {
        method: 'POST',
        body: JSON.stringify({
          project_id: input.projectId,
          title: input.title,
          transcript: input.transcript,
          skill_id: input.skillId,
        }),
      }, signal)
      const job = await requestJson<ApiJob>(`/reports/${created.id}/generate`, {
        method: 'POST',
        body: JSON.stringify({ provider_id: input.modelId }),
      }, signal)
      if (job.status !== 'succeeded') {
        throw new ApiError(job.error || `生成任务状态异常：${job.status}`, 'GENERATION_FAILED')
      }
      const [report, validation] = await Promise.all([
        requestJson<ApiReport>(`/reports/${created.id}`, {}, signal),
        requestValidation(created.id, signal),
      ])
      return {
        report: mapDraft(report),
        issues: mapValidation(validation),
        confirmed: report.status === 'confirmed',
      }
    },

    async confirmReport(report: ReportDraft, signal): Promise<ReportOperationResult> {
      const saved = await requestJson<ApiReport>(`/reports/${report.reportId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: report.title, content: stripReportMetadata(report) }),
      }, signal)
      const validation = await requestValidation(report.reportId, signal)
      const issues = mapValidation(validation)
      if (!validation.valid) {
        return { report: mapDraft(saved), issues, confirmed: false }
      }
      const confirmedReport = await requestJson<ApiReport>(`/reports/${report.reportId}/confirm`, {
        method: 'POST',
      }, signal)
      return { report: mapDraft(confirmedReport), issues, confirmed: true }
    },

    async exportReport(report: ReportDraft, signal): Promise<ExportArtifact> {
      let response: Response
      try {
        response = await fetchImpl(`${apiBaseUrl}/reports/${report.reportId}/export`, {
          method: 'POST',
          signal,
        })
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') throw error
        throw new ApiError('无法连接本地服务，请确认 FastAPI 已启动。', 'NETWORK_ERROR')
      }
      if (!response.ok) {
        throw new ApiError(await errorMessage(response), `HTTP_${response.status}`)
      }
      const disposition = response.headers.get('content-disposition') ?? ''
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
      const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1]
      const fileName = encodedName
        ? decodeURIComponent(encodedName)
        : plainName || `${report.title}.pdf`
      return { blob: await response.blob(), fileName, mock: false }
    },
  }
}

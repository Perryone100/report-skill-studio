import { ApiError, type WorkbenchApi } from './client'
import type {
  CreateProjectInput,
  ExportArtifact,
  ExportFormat,
  GenerateReportInput,
  IssueSeverity,
  LoadedReport,
  LocalLibraryInfo,
  MarkdownSyncResult,
  ModelOption,
  ProjectSummary,
  ReportContent,
  ReportDraft,
  ReportOperationResult,
  ReportSummary,
  ReportVersionEntry,
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

interface ApiSession {
  request_token: string
}

interface ApiReport {
  id: string
  project_id: string
  title: string
  transcript: string
  skill_id: string
  content: ReportContent | Record<string, never>
  status: 'draft' | 'confirmed'
  version: number
  generated_at: string
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
  source: 'bundled' | 'user'
  can_delete: boolean
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

interface ApiReportVersion {
  id: string
  report_id: string
  version: number
  title: string
  transcript: string
  content: ReportContent | Record<string, never>
  reason: string
  created_at: string
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

interface ApiLocalLibrary {
  root_path: string
  configured: boolean
  exists: boolean
  writable: boolean
}

interface ApiMarkdownSync {
  status: MarkdownSyncResult['status']
  root_path: string
  relative_path: string | null
  file_path: string | null
  message: string
  synced_at: string | null
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
  const meetingDate = hasReportContent(report) ? report.content.meeting_date : undefined
  return {
    id: report.id,
    projectId: report.project_id,
    title: report.title,
    period: meetingDate || report.created_at.slice(0, 10),
    status: report.status,
    generatedAt: report.generated_at,
    updatedAt: report.updated_at,
  }
}

function mapSkill(skill: ApiSkill): SkillOption {
  return {
    id: skill.id,
    name: skill.name,
    version: skill.version,
    description: skill.description,
    source: skill.source,
    canDelete: skill.can_delete,
  }
}

function mapProvider(provider: ApiProvider): ModelOption {
  return {
    id: provider.id,
    name: provider.local ? provider.name : provider.model,
    provider: provider.local ? provider.model : provider.name,
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
  if (!hasReportContent(report)) {
    throw new ApiError('服务端返回的报告内容结构不完整。', 'INVALID_RESPONSE')
  }
  return { ...report.content, reportId: report.id }
}

function hasReportContent(report: ApiReport): report is ApiReport & { content: ReportContent } {
  const content = report.content as Partial<ReportContent>
  return Boolean(
    content
    && Array.isArray(content.sections)
    && Array.isArray(content.summary_cards),
  )
}

function mapVersion(version: ApiReportVersion): ReportVersionEntry {
  const content = hasCanonicalContent(version.content) ? version.content : undefined
  return {
    id: version.id,
    reportId: version.report_id,
    version: version.version,
    title: version.title,
    reason: version.reason,
    createdAt: version.created_at,
    hasContent: Boolean(content),
    content,
  }
}

function hasCanonicalContent(content: ReportContent | Record<string, never>): content is ReportContent {
  const candidate = content as Partial<ReportContent>
  return Boolean(candidate && Array.isArray(candidate.sections) && Array.isArray(candidate.summary_cards))
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

function mapLocalLibrary(info: ApiLocalLibrary): LocalLibraryInfo {
  return {
    rootPath: info.root_path,
    configured: info.configured,
    exists: info.exists,
    writable: info.writable,
  }
}

function mapMarkdownSync(sync: ApiMarkdownSync): MarkdownSyncResult {
  return {
    status: sync.status,
    rootPath: sync.root_path,
    relativePath: sync.relative_path ?? undefined,
    filePath: sync.file_path ?? undefined,
    message: sync.message,
    syncedAt: sync.synced_at ?? undefined,
  }
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
  let sessionTokenPromise: Promise<string> | null = null

  const getSessionToken = async (signal?: AbortSignal) => {
    if (!sessionTokenPromise) {
      sessionTokenPromise = (async () => {
        const response = await fetchImpl(`${apiBaseUrl}/session`, { signal })
        if (!response.ok) throw new ApiError(await errorMessage(response), `HTTP_${response.status}`)
        const session = await response.json() as ApiSession
        if (!session.request_token) throw new ApiError('本地服务未返回请求令牌。', 'INVALID_RESPONSE')
        return session.request_token
      })()
      sessionTokenPromise.catch(() => { sessionTokenPromise = null })
    }
    return sessionTokenPromise
  }

  const performFetch = async (
    path: string,
    init: RequestInit = {},
    signal?: AbortSignal,
    retry = true,
  ): Promise<Response> => {
    const method = (init.method ?? 'GET').toUpperCase()
    const unsafe = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)
    const headers = new Headers(init.headers)
    if (unsafe) headers.set('X-Report-Skill-Token', await getSessionToken(signal))
    const response = await fetchImpl(`${apiBaseUrl}${path}`, { ...init, headers, signal })
    if (unsafe && response.status === 403 && retry) {
      sessionTokenPromise = null
      return performFetch(path, init, signal, false)
    }
    return response
  }

  const requestJson = async <Result>(path: string, init: RequestInit = {}, signal?: AbortSignal) => {
    let response: Response
    try {
      response = await performFetch(path, {
        ...init,
        headers: {
          ...(init.body ? { 'Content-Type': 'application/json' } : {}),
          ...init.headers,
        },
      }, signal)
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
      response = await performFetch(path, init, signal)
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new ApiError('无法连接本地服务，请确认 FastAPI 已启动。', 'NETWORK_ERROR')
    }
    if (!response.ok) throw new ApiError(await errorMessage(response), `HTTP_${response.status}`)
  }

  const loadReportBundle = async (report: ApiReport, signal?: AbortSignal): Promise<LoadedReport> => {
    const [versions, validation] = await Promise.all([
      requestJson<ApiReportVersion[]>(`/reports/${report.id}/versions`, {}, signal),
      hasReportContent(report)
        ? requestValidation(report.id, signal)
        : Promise.resolve<ApiValidationResult>({ valid: false, issues: [] }),
    ])
    return {
      reportId: report.id,
      projectId: report.project_id,
      title: report.title,
      transcript: report.transcript,
      skillId: report.skill_id,
      status: report.status,
      version: report.version,
      generatedAt: report.generated_at,
      updatedAt: report.updated_at,
      draft: hasReportContent(report) ? mapDraft(report) : null,
      issues: hasReportContent(report) ? mapValidation(validation) : [],
      versions: versions.map(mapVersion),
    }
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

    async getLocalLibrary(signal) {
      const info = await requestJson<ApiLocalLibrary>('/local-library', {}, signal)
      return mapLocalLibrary(info)
    },

    async configureLocalLibrary(rootPath, signal) {
      const info = await requestJson<ApiLocalLibrary>('/local-library', {
        method: 'PUT',
        body: JSON.stringify({ root_path: rootPath }),
      }, signal)
      return mapLocalLibrary(info)
    },

    async createProject(input: CreateProjectInput, signal) {
      const project = await requestJson<ApiProject>('/projects', {
        method: 'POST',
        body: JSON.stringify({ name: input.name, description: input.description }),
      }, signal)
      return mapProject(project)
    },

    async exportProjectBackup(projectId, signal) {
      let response: Response
      try {
        response = await performFetch(
          `/projects/${encodeURIComponent(projectId)}/backup`, {}, signal,
        )
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') throw error
        throw new ApiError('无法连接本地服务，请确认 FastAPI 已启动。', 'NETWORK_ERROR')
      }
      if (!response.ok) throw new ApiError(await errorMessage(response), `HTTP_${response.status}`)
      const disposition = response.headers.get('content-disposition') ?? ''
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
      const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1]
      return {
        blob: await response.blob(),
        fileName: encodedName ? decodeURIComponent(encodedName) : plainName || 'project-backup.zip',
        mock: false,
      }
    },

    async clearProjectReports(projectId, signal) {
      await requestVoid(`/projects/${encodeURIComponent(projectId)}/reports`, { method: 'DELETE' }, signal)
    },

    async deleteProject(projectId, signal) {
      await requestVoid(`/projects/${encodeURIComponent(projectId)}`, { method: 'DELETE' }, signal)
    },

    async installSkill(file, replaceExisting, signal) {
      const installed = await requestJson<ApiSkill>(
        `/skills/install?replace=${replaceExisting ? 'true' : 'false'}`,
        {
          method: 'POST',
          body: file,
          headers: { 'Content-Type': 'application/zip' },
        },
        signal,
      )
      return mapSkill(installed)
    },

    async deleteSkill(skillId, signal) {
      await requestVoid(`/skills/${encodeURIComponent(skillId)}`, { method: 'DELETE' }, signal)
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

    async loadReport(reportId, signal) {
      const report = await requestJson<ApiReport>(`/reports/${encodeURIComponent(reportId)}`, {}, signal)
      return loadReportBundle(report, signal)
    },

    async saveReportDraft(report, transcript, signal) {
      const saved = await requestJson<ApiReport>(`/reports/${report.reportId}/draft`, {
        method: 'PATCH',
        body: JSON.stringify({
          title: report.title,
          transcript,
          content: stripReportMetadata(report),
        }),
      }, signal)
      return { updatedAt: saved.updated_at, version: saved.version, report: mapDraft(saved) }
    },

    async restoreReportVersion(reportId, version, signal) {
      const report = await requestJson<ApiReport>(
        `/reports/${encodeURIComponent(reportId)}/versions/${version}/restore`,
        { method: 'POST' },
        signal,
      )
      return loadReportBundle(report, signal)
    },

    async getReportMarkdownStatus(reportId, signal) {
      const sync = await requestJson<ApiMarkdownSync>(
        `/reports/${encodeURIComponent(reportId)}/markdown`,
        {},
        signal,
      )
      return mapMarkdownSync(sync)
    },

    async syncReportMarkdown(reportId, signal) {
      const sync = await requestJson<ApiMarkdownSync>(
        `/reports/${encodeURIComponent(reportId)}/markdown/sync`,
        { method: 'POST' },
        signal,
      )
      return mapMarkdownSync(sync)
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

    async confirmReport(report: ReportDraft, transcript, signal): Promise<ReportOperationResult> {
      const saved = await requestJson<ApiReport>(`/reports/${report.reportId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: report.title, transcript, content: stripReportMetadata(report) }),
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

    async exportReport(report: ReportDraft, format: ExportFormat, signal): Promise<ExportArtifact> {
      let response: Response
      try {
        const path = format === 'pdf'
          ? `/reports/${report.reportId}/export`
          : `/reports/${report.reportId}/export/html`
        response = await performFetch(path, { method: 'POST' }, signal)
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
        : plainName || `${report.title}.${format}`
      return { blob: await response.blob(), fileName, mock: false }
    },
  }
}

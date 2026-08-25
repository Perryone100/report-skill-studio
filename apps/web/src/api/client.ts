import type {
  CreateProjectInput,
  DraftSaveResult,
  ExportArtifact,
  GenerateReportInput,
  LoadedReport,
  ProjectSummary,
  ReportDraft,
  ReportOperationResult,
  SaveTerminologyMemoryInput,
  TerminologyMemoryEntry,
  WorkspaceBootstrap,
} from './types'

export interface WorkbenchApi {
  getWorkspace(signal?: AbortSignal): Promise<WorkspaceBootstrap>
  createProject(input: CreateProjectInput, signal?: AbortSignal): Promise<ProjectSummary>
  listTerminologyMemory(projectId: string, signal?: AbortSignal): Promise<TerminologyMemoryEntry[]>
  saveTerminologyMemory(input: SaveTerminologyMemoryInput, signal?: AbortSignal): Promise<TerminologyMemoryEntry>
  deleteTerminologyMemory(memoryId: string, signal?: AbortSignal): Promise<void>
  loadReport(reportId: string, signal?: AbortSignal): Promise<LoadedReport>
  saveReportDraft(report: ReportDraft, transcript: string, signal?: AbortSignal): Promise<DraftSaveResult>
  restoreReportVersion(reportId: string, version: number, signal?: AbortSignal): Promise<LoadedReport>
  generateReport(input: GenerateReportInput, signal?: AbortSignal): Promise<ReportOperationResult>
  confirmReport(report: ReportDraft, transcript: string, signal?: AbortSignal): Promise<ReportOperationResult>
  exportReport(report: ReportDraft, signal?: AbortSignal): Promise<ExportArtifact>
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

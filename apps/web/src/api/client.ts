import type {
  CreateProjectInput,
  ExportArtifact,
  GenerateReportInput,
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
  generateReport(input: GenerateReportInput, signal?: AbortSignal): Promise<ReportOperationResult>
  confirmReport(report: ReportDraft, signal?: AbortSignal): Promise<ReportOperationResult>
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

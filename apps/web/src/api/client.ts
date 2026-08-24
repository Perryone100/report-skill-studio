import type {
  CreateProjectInput,
  ExportArtifact,
  GenerateReportInput,
  ProjectSummary,
  ReportDraft,
  ReportOperationResult,
  WorkspaceBootstrap,
} from './types'

export interface WorkbenchApi {
  getWorkspace(signal?: AbortSignal): Promise<WorkspaceBootstrap>
  createProject(input: CreateProjectInput, signal?: AbortSignal): Promise<ProjectSummary>
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

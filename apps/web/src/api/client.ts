import type {
  CreateProjectInput,
  DraftSaveResult,
  ExportArtifact,
  ExportFormat,
  GenerateReportInput,
  LoadedReport,
  LocalLibraryInfo,
  MarkdownSyncResult,
  ProjectSummary,
  ReportDraft,
  ReportOperationResult,
  SaveTerminologyMemoryInput,
  TerminologyMemoryEntry,
  SkillOption,
  WorkspaceBootstrap,
} from './types'

export interface WorkbenchApi {
  getWorkspace(signal?: AbortSignal): Promise<WorkspaceBootstrap>
  getLocalLibrary(signal?: AbortSignal): Promise<LocalLibraryInfo>
  configureLocalLibrary(rootPath: string, signal?: AbortSignal): Promise<LocalLibraryInfo>
  createProject(input: CreateProjectInput, signal?: AbortSignal): Promise<ProjectSummary>
  exportProjectBackup(projectId: string, signal?: AbortSignal): Promise<ExportArtifact>
  clearProjectReports(projectId: string, signal?: AbortSignal): Promise<void>
  deleteProject(projectId: string, signal?: AbortSignal): Promise<void>
  installSkill(file: File, replaceExisting: boolean, signal?: AbortSignal): Promise<SkillOption>
  deleteSkill(skillId: string, signal?: AbortSignal): Promise<void>
  listTerminologyMemory(projectId: string, signal?: AbortSignal): Promise<TerminologyMemoryEntry[]>
  saveTerminologyMemory(input: SaveTerminologyMemoryInput, signal?: AbortSignal): Promise<TerminologyMemoryEntry>
  deleteTerminologyMemory(memoryId: string, signal?: AbortSignal): Promise<void>
  loadReport(reportId: string, signal?: AbortSignal): Promise<LoadedReport>
  saveReportDraft(report: ReportDraft, transcript: string, signal?: AbortSignal): Promise<DraftSaveResult>
  restoreReportVersion(reportId: string, version: number, signal?: AbortSignal): Promise<LoadedReport>
  getReportMarkdownStatus(reportId: string, signal?: AbortSignal): Promise<MarkdownSyncResult>
  syncReportMarkdown(reportId: string, signal?: AbortSignal): Promise<MarkdownSyncResult>
  generateReport(input: GenerateReportInput, signal?: AbortSignal): Promise<ReportOperationResult>
  confirmReport(report: ReportDraft, transcript: string, signal?: AbortSignal): Promise<ReportOperationResult>
  exportReport(report: ReportDraft, format: ExportFormat, signal?: AbortSignal): Promise<ExportArtifact>
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

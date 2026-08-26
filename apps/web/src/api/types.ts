export type ReportStatus = 'draft' | 'confirmed' | 'exported'
export type ProjectStatus = 'active' | 'archived'
export type IssueSeverity = 'error' | 'warning' | 'info'
export type ReportTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'
export type MemoryScope = 'global' | 'project' | 'temporary'

export interface ProjectSummary {
  id: string
  name: string
  description: string
  status: ProjectStatus
  updatedAt: string
}

export interface ReportSummary {
  id: string
  projectId: string
  title: string
  period: string
  status: ReportStatus
  generatedAt: string
  updatedAt: string
}

export interface ReportVersionEntry {
  id: string
  reportId: string
  version: number
  title: string
  reason: string
  createdAt: string
  hasContent: boolean
  content?: ReportContent
}

export interface SkillOption {
  id: string
  name: string
  version: string
  description: string
  source: 'bundled' | 'user'
  canDelete: boolean
}

export interface ModelOption {
  id: string
  name: string
  provider: string
  locality: 'local' | 'cloud'
  ready: boolean
}

export interface SummaryCard {
  label: string
  value: string
  tone?: ReportTone
}

export interface ParagraphBlock {
  type: 'paragraph'
  text: string
}

export interface BulletListBlock {
  type: 'bullet_list'
  items: string[]
}

export interface ProjectTableBlock {
  type: 'project_table'
  columns: string[]
  rows: string[][]
}

export interface StatusCard {
  title: string
  status: string
  details?: string[]
}

export interface StatusCardsBlock {
  type: 'status_cards'
  cards: StatusCard[]
}

export interface CalloutBlock {
  type: 'callout'
  title?: string
  text: string
  tone?: ReportTone
}

export type ReportBlock =
  | ParagraphBlock
  | BulletListBlock
  | ProjectTableBlock
  | StatusCardsBlock
  | CalloutBlock

export interface ReportSection {
  id: string
  title: string
  blocks: ReportBlock[]
}

export interface ReportContent {
  title: string
  meeting_date: string
  executive_summary: string
  summary_cards: SummaryCard[]
  sections: ReportSection[]
}

export interface ReportDraft extends ReportContent {
  /** UI-only persistence identity. Never include this in the report content payload. */
  reportId: string
}

export interface ValidationIssue {
  id: string
  severity: IssueSeverity
  title: string
  message: string
  field?: string
  source?: 'local' | 'server'
  suggestion?: string
}

export interface WorkspaceBootstrap {
  projects: ProjectSummary[]
  reports: ReportSummary[]
  skills: SkillOption[]
  models: ModelOption[]
}

export interface LocalLibraryInfo {
  rootPath: string
  configured: boolean
  exists: boolean
  writable: boolean
}

export interface MarkdownSyncResult {
  status: 'synced' | 'unsynced' | 'conflict' | 'missing' | 'no_content' | 'error'
  rootPath: string
  relativePath?: string
  filePath?: string
  message: string
  syncedAt?: string
}

export interface GenerateReportInput {
  projectId: string
  title: string
  transcript: string
  skillId: string
  modelId: string
}

export interface CreateProjectInput {
  name: string
  description: string
}

export interface ReportOperationResult {
  report: ReportDraft
  issues: ValidationIssue[]
  confirmed: boolean
}

export interface LoadedReport {
  reportId: string
  projectId: string
  title: string
  transcript: string
  skillId: string
  status: 'draft' | 'confirmed'
  version: number
  generatedAt: string
  updatedAt: string
  draft: ReportDraft | null
  issues: ValidationIssue[]
  versions: ReportVersionEntry[]
}

export interface DraftSaveResult {
  updatedAt: string
  version: number
  report: ReportDraft
}

export interface ExportArtifact {
  blob: Blob
  fileName: string
  mock: boolean
}

export type ExportFormat = 'html' | 'pdf'

export interface TerminologyMemoryEntry {
  id: string
  projectId?: string
  sourceValue: string
  normalizedValue: string
  scope: MemoryScope
  updatedAt: string
}

export interface SaveTerminologyMemoryInput {
  projectId: string
  sourceValue: string
  normalizedValue: string
}

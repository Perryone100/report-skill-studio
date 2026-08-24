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
  updatedAt: string
}

export interface SkillOption {
  id: string
  name: string
  version: string
  description: string
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

export interface ExportArtifact {
  blob: Blob
  fileName: string
  mock: boolean
}

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

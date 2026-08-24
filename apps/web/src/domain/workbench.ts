import type { ReportBlock, ReportDraft, ValidationIssue } from '../api'

const forbiddenExpressions = ['图文结合版', '内容来源', '汇报口径', 'AI生成']

function blockText(block: ReportBlock): string[] {
  switch (block.type) {
    case 'paragraph':
      return [block.text]
    case 'bullet_list':
      return block.items
    case 'project_table':
      return [...block.columns, ...block.rows.flat()]
    case 'status_cards':
      return block.cards.flatMap((card) => [card.title, card.status, ...(card.details ?? [])])
    case 'callout':
      return [block.title ?? '', block.text]
  }
}

const allReportText = (draft: ReportDraft) =>
  [
    draft.title,
    draft.meeting_date,
    draft.executive_summary,
    ...draft.summary_cards.flatMap((card) => [card.label, card.value]),
    ...draft.sections.flatMap((section) => [
      section.title,
      ...section.blocks.flatMap(blockText),
    ]),
  ].join('\n')

export function validateReport(draft: ReportDraft): ValidationIssue[] {
  const issues: ValidationIssue[] = []
  const text = allReportText(draft)

  if (!draft.title.trim()) {
    issues.push({ id: 'missing-title', severity: 'error', title: '缺少报告标题', message: '请填写报告标题后再确认。', field: 'title' })
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.meeting_date)) {
    issues.push({ id: 'invalid-meeting-date', severity: 'error', title: '会议日期格式错误', message: '会议日期需要使用 YYYY-MM-DD 格式。', field: 'meeting_date' })
  }
  if (!draft.executive_summary.trim()) {
    issues.push({ id: 'missing-executive-summary', severity: 'error', title: '缺少执行摘要', message: '管理层报告需要先给出整体判断。', field: 'executive_summary' })
  }
  if (draft.summary_cards.length === 0) {
    issues.push({ id: 'missing-summary-cards', severity: 'error', title: '缺少摘要卡片', message: '至少需要一张摘要卡片。', field: 'summary_cards' })
  }

  for (const expression of forbiddenExpressions) {
    if (text.includes(expression)) {
      issues.push({ id: `forbidden-${expression}`, severity: 'error', title: '发现内部表达', message: `“${expression}”不应出现在最终报告中。` })
    }
  }
  if (draft.sections.length === 0) {
    issues.push({ id: 'missing-sections', severity: 'error', title: '缺少报告章节', message: '至少需要一个报告章节。', field: 'sections' })
  }

  draft.sections.forEach((section) => {
    if (!section.title.trim()) {
      issues.push({ id: `missing-section-title-${section.id}`, severity: 'error', title: '章节标题为空', message: `章节“${section.id}”需要填写标题。` })
    }
    if (section.blocks.length === 0) {
      issues.push({ id: `empty-section-${section.id}`, severity: 'error', title: '空章节', message: `“${section.title || section.id}”尚无内容区块。` })
    }

    section.blocks.forEach((block, blockIndex) => {
      const path = `${section.id}-${blockIndex}`
      if (block.type === 'paragraph' && !block.text.trim()) {
        issues.push({ id: `empty-paragraph-${path}`, severity: 'error', title: '段落内容为空', message: `“${section.title}”中的段落需要填写内容。` })
      }
      if (block.type === 'bullet_list' && (block.items.length === 0 || block.items.some((item) => !item.trim()))) {
        issues.push({ id: `empty-bullet-list-${path}`, severity: 'error', title: '列表内容不完整', message: `“${section.title}”中的列表含有空项。` })
      }
      if (block.type === 'project_table') {
        if (block.columns.length === 0 || block.rows.length === 0) {
          issues.push({ id: `empty-project-table-${path}`, severity: 'error', title: '项目表格不完整', message: `“${section.title}”中的表格缺少列或数据行。` })
        } else if (block.rows.some((row) => row.length !== block.columns.length)) {
          issues.push({ id: `uneven-project-table-${path}`, severity: 'warning', title: '表格列数不一致', message: `“${section.title}”中部分数据行与表头列数不同。` })
        }
      }
      if (block.type === 'status_cards' && block.cards.length === 0) {
        issues.push({ id: `empty-status-cards-${path}`, severity: 'error', title: '状态卡片为空', message: `“${section.title}”至少需要一张状态卡片。` })
      }
      if (block.type === 'callout' && !block.text.trim()) {
        issues.push({ id: `empty-callout-${path}`, severity: 'error', title: '提示内容为空', message: `“${section.title}”中的重点提示需要填写内容。` })
      }
    })
  })

  if (issues.length === 0) {
    issues.push({ id: 'quality-pass', severity: 'info', title: '自动检查通过', message: '未发现术语、结构或禁用表达问题。' })
  }
  return issues
}

interface WorkflowInput {
  transcript: string
  projectId: string
  skillId: string
  modelId: string
  draft: ReportDraft | null
  issues: ValidationIssue[]
  isGenerating: boolean
  isConfirmed: boolean
}

export function deriveWorkflowState(input: WorkflowInput) {
  const hasBlockingIssue = input.issues.some((issue) => issue.severity === 'error')
  const hasSelections = Boolean(input.projectId && input.skillId && input.modelId)
  return {
    canGenerate: input.transcript.trim().length >= 20 && hasSelections && !input.isGenerating,
    canConfirm: Boolean(input.draft) && !hasBlockingIssue && !input.isGenerating,
    canExport: Boolean(input.draft) && input.isConfirmed && !hasBlockingIssue,
    hasBlockingIssue,
  }
}

export function formatRelativeTime(isoDate: string) {
  const date = new Date(isoDate)
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date)
}

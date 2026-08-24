import { describe, expect, it } from 'vitest'
import type { ReportDraft } from '../api'
import { deriveWorkflowState, validateReport } from './workbench'

const validDraft = (): ReportDraft => ({
  reportId: 'report-1',
  title: '产品研发周会纪要',
  meeting_date: '2026-08-21',
  executive_summary: '本周整体按计划推进。',
  summary_cards: [{ label: '本周阶段', value: '进入联调', tone: 'info' }],
  sections: [
    {
      id: 'overall_conclusion',
      title: '本周整体结论',
      blocks: [
        {
          type: 'paragraph',
          text: '功能模块 A 联调完成，下周启动灰度。',
        },
      ],
    },
  ],
})

describe('validateReport', () => {
  it('为合法报告返回通过信息', () => {
    const issues = validateReport(validDraft())
    expect(issues).toHaveLength(1)
    expect(issues[0].severity).toBe('info')
  })

  it('接受 canonical 契约的五类内容区块', () => {
    const draft = validDraft()
    draft.sections[0].blocks = [
      { type: 'paragraph', text: '整体按计划推进。' },
      { type: 'bullet_list', items: ['完成验收。'] },
      { type: 'project_table', columns: ['工作项', '进展'], rows: [['功能模块 A', '联调完成']] },
      { type: 'status_cards', cards: [{ title: '上线准备', status: '正常' }] },
      { type: 'callout', title: '关注事项', text: '锁定验收资源。', tone: 'warning' },
    ]
    expect(validateReport(draft).every((issue) => issue.severity !== 'error')).toBe(true)
  })

  it('拦截禁用表达', () => {
    const draft = validDraft()
    draft.executive_summary = '这是 AI生成 的图文结合版。'
    const issues = validateReport(draft)
    expect(issues.filter((issue) => issue.severity === 'error')).toHaveLength(2)
  })

  it('段落为空时阻止确认', () => {
    const draft = validDraft()
    const block = draft.sections[0].blocks[0]
    if (block.type === 'paragraph') block.text = ''
    const issues = validateReport(draft)
    const workflow = deriveWorkflowState({
      transcript: '这是一段长度足够用于生成报告的测试会议逐字稿内容。',
      projectId: 'project-1',
      skillId: 'skill-1',
      modelId: 'model-1',
      draft,
      issues,
      isGenerating: false,
      isConfirmed: false,
    })
    expect(workflow.canConfirm).toBe(false)
    expect(workflow.hasBlockingIssue).toBe(true)
  })
})

describe('deriveWorkflowState', () => {
  it('要求逐字稿和三个选择项齐全才能生成', () => {
    const base = {
      projectId: 'project-1',
      skillId: 'skill-1',
      modelId: 'model-1',
      draft: null,
      issues: [],
      isGenerating: false,
      isConfirmed: false,
    }
    expect(deriveWorkflowState({ ...base, transcript: '太短' }).canGenerate).toBe(false)
    expect(
      deriveWorkflowState({
        ...base,
        transcript: '这是一段长度足够用于生成报告的测试会议逐字稿内容。',
      }).canGenerate,
    ).toBe(true)
  })

  it('只有确认后才能导出', () => {
    const draft = validDraft()
    const base = {
      transcript: '这是一段长度足够用于生成报告的测试会议逐字稿内容。',
      projectId: 'project-1',
      skillId: 'skill-1',
      modelId: 'model-1',
      draft,
      issues: validateReport(draft),
      isGenerating: false,
    }
    expect(deriveWorkflowState({ ...base, isConfirmed: false }).canExport).toBe(false)
    expect(deriveWorkflowState({ ...base, isConfirmed: true }).canExport).toBe(true)
  })
})

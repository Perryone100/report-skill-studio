import { describe, expect, it } from 'vitest'
import type { ReportDraft } from '../api'
import {
  applyTerminologyToDraft,
  deriveWorkflowState,
  inferTerminologyCorrections,
  replaceTerminologyInText,
  validateReport,
} from './workbench'

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

  it('允许业务正文描述 AI 生成能力，并仅提醒内部标签', () => {
    const draft = validDraft()
    draft.executive_summary = '本周完成 AI 生成报告能力联调。'
    draft.sections[0].blocks = [{ type: 'paragraph', text: '输出形式：图文结合版' }]
    const issues = validateReport(draft)
    expect(issues.some((issue) => issue.message.includes('AI 生成'))).toBe(false)
    expect(issues.filter((issue) => issue.severity === 'error')).toHaveLength(0)
    expect(issues.filter((issue) => issue.severity === 'warning')).toHaveLength(2)
    expect(issues.every((issue) => issue.field?.startsWith('$.') ?? true)).toBe(true)
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
    expect(deriveWorkflowState({ ...base, isConfirmed: true }).canConfirm).toBe(false)
  })
})

describe('项目术语应用', () => {
  it('在逐字稿中以不区分大小写的方式应用已确认矫正', () => {
    const result = replaceTerminologyInText('PinCode 已上线，pincode 待复核。', 'pincode', 'PingCode')
    expect(result).toEqual({ text: 'PingCode 已上线，PingCode 待复核。', count: 2 })
  })

  it('一次更新报告全部五类内容块并保留结构字段', () => {
    const draft = validDraft()
    draft.executive_summary = '模块爱进入联调。'
    draft.summary_cards = [{ label: '模块爱', value: '模块爱完成' }]
    draft.sections[0].blocks = [
      { type: 'paragraph', text: '模块爱段落' },
      { type: 'bullet_list', items: ['模块爱计划'] },
      { type: 'project_table', columns: ['工作项'], rows: [['模块爱']] },
      { type: 'status_cards', cards: [{ title: '模块爱', status: '模块爱进行中', details: ['模块爱详情'] }] },
      { type: 'callout', title: '模块爱风险', text: '模块爱需协调' },
    ]

    const result = applyTerminologyToDraft(draft, '模块爱', '功能模块 A')

    expect(result.count).toBe(11)
    expect(JSON.stringify(result.draft)).not.toContain('模块爱')
    expect(result.draft.reportId).toBe('report-1')
    expect(result.draft.sections[0].id).toBe('overall_conclusion')
  })
})

describe('从人工修改中学习', () => {
  it('从同一位置的小范围修改中提取候选矫正规则', () => {
    const baseline = validDraft()
    baseline.executive_summary = '模块爱本周完成联调。'
    const current = structuredClone(baseline)
    current.executive_summary = '功能模块 A本周完成联调。'

    expect(inferTerminologyCorrections(baseline, current)).toEqual([{
      id: '模块爱\u0000功能模块 a',
      sourceValue: '模块爱',
      normalizedValue: '功能模块 A',
      count: 1,
    }])
  })

  it('合并跨字段的相同修改次数，并忽略大段重写', () => {
    const baseline = validDraft()
    baseline.executive_summary = '模块爱进入联调。'
    baseline.summary_cards[0].value = '模块爱已上线'
    const current = structuredClone(baseline)
    current.executive_summary = '功能模块 A进入联调。'
    current.summary_cards[0].value = '功能模块 A已上线'
    current.sections[0].blocks = [{ type: 'paragraph', text: '这是完全不同的一整段内容；不应该被当作术语。' }]

    expect(inferTerminologyCorrections(baseline, current)).toMatchObject([{
      sourceValue: '模块爱',
      normalizedValue: '功能模块 A',
      count: 2,
    }])
  })
})

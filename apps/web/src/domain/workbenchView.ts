import type { ReportDraft } from '../api'

export const exampleTranscript = `主持人：先同步本周的几个重点。功能模块 A 已完成核心流程联调，遗留问题本周五前收口，下周安排小流量灰度。

产品负责人：业务侧完成了内容验收，历史数据还有一批需要人工复核。整体不影响灰度，但要补充监控。

运营负责人：活动页面 C 的配置和数据回传已经进入 UAT。上线窗口比较紧，希望本周提前锁定验收人。

平台负责人：OCR 和 ASR 的稳定性优化已完成，接下来补成本统计和异常告警。`

export function describeIssueField(field: string, draft: ReportDraft): string {
  if (field === '$.title') return '报告标题'
  if (field === '$.meeting_date') return '会议日期'
  if (field === '$.executive_summary') return '执行摘要'
  const summaryMatch = field.match(/^\$\.summary_cards\[(\d+)]/)
  if (summaryMatch) return `概览卡片 ${Number(summaryMatch[1]) + 1}`
  const sectionMatch = field.match(/^\$\.sections\[(\d+)](?:\.blocks\[(\d+)])?/)
  if (sectionMatch) {
    const sectionIndex = Number(sectionMatch[1])
    const sectionName = draft.sections[sectionIndex]?.title || `章节 ${sectionIndex + 1}`
    return sectionMatch[2] === undefined
      ? sectionName
      : `${sectionName} · 内容块 ${Number(sectionMatch[2]) + 1}`
  }
  return '报告内容'
}

export function locateReportField(field: string) {
  const candidates = Array.from(document.querySelectorAll<HTMLElement>('[data-report-path]'))
  const exact = candidates.find((element) => element.dataset.reportPath === field)
  const parent = candidates
    .filter((element) => field.startsWith(element.dataset.reportPath ?? ''))
    .sort((left, right) => (right.dataset.reportPath?.length ?? 0) - (left.dataset.reportPath?.length ?? 0))[0]
  const child = candidates
    .filter((element) => (element.dataset.reportPath ?? '').startsWith(field))
    .sort((left, right) => (left.dataset.reportPath?.length ?? 0) - (right.dataset.reportPath?.length ?? 0))[0]
  const target = exact ?? parent ?? child
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  const focusTarget = target.matches('input, textarea, select, button')
    ? target
    : target.querySelector<HTMLElement>('input, textarea, select, button')
  focusTarget?.focus({ preventScroll: true })
  target.classList.add('report-field-highlight')
  window.setTimeout(() => target.classList.remove('report-field-highlight'), 1800)
}

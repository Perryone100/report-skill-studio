import type { ReportBlock, ReportDraft } from '../api'
import { Icon } from './Icons'

interface ReportEditorProps {
  draft: ReportDraft
  confirmed: boolean
  onChange: (nextDraft: ReportDraft) => void
}

const blockLabel: Record<ReportBlock['type'], string> = {
  paragraph: '段落',
  bullet_list: '列表',
  project_table: '项目表格',
  status_cards: '状态卡片',
  callout: '重点提示',
}

export function ReportEditor({ draft, confirmed, onChange }: ReportEditorProps) {
  const update = <Key extends keyof ReportDraft>(key: Key, value: ReportDraft[Key]) =>
    onChange({ ...draft, [key]: value })

  const updateBlock = (sectionIndex: number, blockIndex: number, block: ReportBlock) => {
    const sections = structuredClone(draft.sections)
    sections[sectionIndex].blocks[blockIndex] = block
    update('sections', sections)
  }

  return (
    <section className="report-editor" aria-label="结构化报告编辑区">
      <div className="editor-titlebar">
        <div>
          <span className="eyebrow">结构化报告</span>
          <div className="editor-title-row">
            <h2>内容编辑</h2>
            <span className={`draft-state ${confirmed ? 'confirmed' : ''}`}>
              {confirmed ? <><Icon name="check" /> 已确认</> : <><Icon name="edit" /> 待确认</>}
            </span>
          </div>
        </div>
        <span className="autosave">
          {confirmed ? '已锁定 · 如需修改请新建版本' : '尚未保存 · 点击确认后写入本地'}
        </span>
      </div>

      <fieldset className="report-sheet" disabled={confirmed}>
        <div className="title-fields two-column-fields">
          <label>
            报告标题
            <input data-report-path="$.title" value={draft.title} onChange={(event) => update('title', event.target.value)} />
          </label>
          <label>
            会议日期
            <input
              type="date"
              data-report-path="$.meeting_date"
              value={draft.meeting_date}
              onChange={(event) => update('meeting_date', event.target.value)}
            />
          </label>
        </div>

        <div className="sheet-section executive-section">
          <div className="section-number">摘要</div>
          <div className="section-content">
            <h3>执行摘要</h3>
            <textarea
              data-report-path="$.executive_summary"
              rows={4}
              value={draft.executive_summary}
              onChange={(event) => update('executive_summary', event.target.value)}
            />
          </div>
        </div>

        <div className="summary-card-grid">
          {draft.summary_cards.map((card, cardIndex) => (
            <div
              className={`summary-edit-card ${card.tone ?? 'neutral'}`}
              data-report-path={`$.summary_cards[${cardIndex}]`}
              key={`${card.label}-${cardIndex}`}
            >
              <input
                data-report-path={`$.summary_cards[${cardIndex}].label`}
                aria-label={`概览卡片 ${cardIndex + 1} 标签`}
                value={card.label}
                onChange={(event) => {
                  const cards = [...draft.summary_cards]
                  cards[cardIndex] = { ...card, label: event.target.value }
                  update('summary_cards', cards)
                }}
              />
              <textarea
                data-report-path={`$.summary_cards[${cardIndex}].value`}
                aria-label={`概览卡片 ${cardIndex + 1} 内容`}
                rows={2}
                value={card.value}
                onChange={(event) => {
                  const cards = [...draft.summary_cards]
                  cards[cardIndex] = { ...card, value: event.target.value }
                  update('summary_cards', cards)
                }}
              />
            </div>
          ))}
        </div>

        {draft.sections.map((section, sectionIndex) => (
          <div className="sheet-section" data-report-path={`$.sections[${sectionIndex}]`} key={section.id}>
            <div className="section-number">{String(sectionIndex + 1).padStart(2, '0')}</div>
            <div className="section-content">
              <input
                className="section-title-input"
                data-report-path={`$.sections[${sectionIndex}].title`}
                aria-label={`章节 ${sectionIndex + 1} 标题`}
                value={section.title}
                onChange={(event) => {
                  const sections = structuredClone(draft.sections)
                  sections[sectionIndex].title = event.target.value
                  update('sections', sections)
                }}
              />

              <div className="block-stack">
                {section.blocks.map((block, blockIndex) => (
                  <div
                    className={`report-block block-${block.type}`}
                    data-report-path={`$.sections[${sectionIndex}].blocks[${blockIndex}]`}
                    key={`${section.id}-${blockIndex}`}
                  >
                    <div className="block-heading">
                      <span>{blockLabel[block.type]}</span>
                    </div>
                    <BlockContent
                      block={block}
                      label={section.title}
                      path={`$.sections[${sectionIndex}].blocks[${blockIndex}]`}
                      onChange={(nextBlock) => updateBlock(sectionIndex, blockIndex, nextBlock)}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </fieldset>
    </section>
  )
}

function BlockContent({
  block,
  label,
  path,
  onChange,
}: {
  block: ReportBlock
  label: string
  path: string
  onChange: (block: ReportBlock) => void
}) {
  switch (block.type) {
    case 'paragraph':
      return (
        <textarea
          data-report-path={`${path}.text`}
          rows={4}
          value={block.text}
          aria-label={`${label}段落内容`}
          onChange={(event) => onChange({ ...block, text: event.target.value })}
        />
      )
    case 'bullet_list':
      return (
        <div className="list-editor">
          {block.items.map((item, index) => (
            <label key={`${label}-bullet-${index}`}>
              <span>{index + 1}</span>
              <textarea
                data-report-path={`${path}.items[${index}]`}
                rows={2}
                value={item}
                aria-label={`${label}列表项 ${index + 1}`}
                onChange={(event) => {
                  const items = [...block.items]
                  items[index] = event.target.value
                  onChange({ ...block, items })
                }}
              />
            </label>
          ))}
        </div>
      )
    case 'project_table':
      return (
        <div className="table-preview table-editor" role="region" aria-label={`${label}项目表格`} tabIndex={0}>
          <table>
            <thead><tr>{block.columns.map((column, index) => (
              <th key={`${column}-${index}`}>
                <input
                  data-report-path={`${path}.columns[${index}]`}
                  aria-label={`${label}表头 ${index + 1}`}
                  value={column}
                  onChange={(event) => {
                    const columns = [...block.columns]
                    columns[index] = event.target.value
                    onChange({ ...block, columns })
                  }}
                />
              </th>
            ))}</tr></thead>
            <tbody>
              {block.rows.map((row, rowIndex) => (
                <tr key={`row-${rowIndex}`}>{row.map((cell, cellIndex) => (
                  <td key={`cell-${cellIndex}`}>
                    <textarea
                      data-report-path={`${path}.rows[${rowIndex}][${cellIndex}]`}
                      rows={2}
                      aria-label={`${label}第 ${rowIndex + 1} 行第 ${cellIndex + 1} 列`}
                      value={cell}
                      onChange={(event) => {
                        const rows = block.rows.map((currentRow) => [...currentRow])
                        rows[rowIndex][cellIndex] = event.target.value
                        onChange({ ...block, rows })
                      }}
                    />
                  </td>
                ))}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    case 'status_cards':
      return (
        <div className="status-card-preview">
          {block.cards.map((card, index) => (
            <article data-report-path={`${path}.cards[${index}]`} key={`${card.title}-${index}`}>
              <input
                data-report-path={`${path}.cards[${index}].title`}
                aria-label={`${label}状态卡片 ${index + 1} 标题`}
                value={card.title}
                onChange={(event) => {
                  const cards = structuredClone(block.cards)
                  cards[index].title = event.target.value
                  onChange({ ...block, cards })
                }}
              />
              <input
                data-report-path={`${path}.cards[${index}].status`}
                aria-label={`${label}状态卡片 ${index + 1} 状态`}
                value={card.status}
                onChange={(event) => {
                  const cards = structuredClone(block.cards)
                  cards[index].status = event.target.value
                  onChange({ ...block, cards })
                }}
              />
              <textarea
                data-report-path={`${path}.cards[${index}].details`}
                rows={3}
                aria-label={`${label}状态卡片 ${index + 1} 详情`}
                value={(card.details ?? []).join('\n')}
                onChange={(event) => {
                  const cards = structuredClone(block.cards)
                  cards[index].details = event.target.value
                    .split('\n')
                    .map((item) => item.trim())
                    .filter(Boolean)
                  onChange({ ...block, cards })
                }}
              />
            </article>
          ))}
        </div>
      )
    case 'callout':
      return (
        <aside className={`callout-preview tone-${block.tone ?? 'neutral'}`}>
          <input
            data-report-path={`${path}.title`}
            aria-label={`${label}重点提示标题`}
            value={block.title ?? ''}
            placeholder="提示标题（可选）"
            onChange={(event) => onChange({ ...block, title: event.target.value || undefined })}
          />
          <textarea
            data-report-path={`${path}.text`}
            rows={4}
            aria-label={`${label}重点提示内容`}
            value={block.text}
            onChange={(event) => onChange({ ...block, text: event.target.value })}
          />
        </aside>
      )
  }
}

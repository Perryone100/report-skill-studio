import { useState } from 'react'
import type { TerminologyMemoryEntry } from '../api'
import { Icon } from './Icons'

interface TerminologyMemoryPanelProps {
  projectName: string
  entries: TerminologyMemoryEntry[]
  loading: boolean
  onSave: (sourceValue: string, normalizedValue: string) => Promise<void>
  onApply: (entry: TerminologyMemoryEntry) => void
  onDelete: (entry: TerminologyMemoryEntry) => Promise<void>
  canApplyToDraft: boolean
}

export function TerminologyMemoryPanel({
  projectName,
  entries,
  loading,
  onSave,
  onApply,
  onDelete,
  canApplyToDraft,
}: TerminologyMemoryPanelProps) {
  const [sourceValue, setSourceValue] = useState('')
  const [normalizedValue, setNormalizedValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState('')

  const canSave = sourceValue.trim()
    && normalizedValue.trim()
    && sourceValue.trim().toLocaleLowerCase() !== normalizedValue.trim().toLocaleLowerCase()

  const handleSave = async () => {
    if (!canSave || saving) return
    setSaving(true)
    try {
      await onSave(sourceValue.trim(), normalizedValue.trim())
      setSourceValue('')
      setNormalizedValue('')
    } catch {
      // The parent displays the API error and the inputs stay available for retry.
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (entry: TerminologyMemoryEntry) => {
    if (deletingId) return
    setDeletingId(entry.id)
    try {
      await onDelete(entry)
    } catch {
      // The parent displays the API error and keeps the record in the table.
    } finally {
      setDeletingId('')
    }
  }

  const handleEdit = (entry: TerminologyMemoryEntry) => {
    setSourceValue(entry.sourceValue)
    setNormalizedValue(entry.normalizedValue)
  }

  return (
    <section className="terminology-panel">
      <div className="terminology-heading">
        <span className="terminology-summary-icon"><Icon name="edit" /></span>
        <span>
          <strong>项目专词与口语矫正</strong>
          <small>{projectName || '当前项目'} · 保存后持续复用</small>
        </span>
        <b>{entries.length} 条</b>
      </div>

      <div className="terminology-body">
        <div className="terminology-form">
          <label>
            原始转写 / 常见误写
            <input
              maxLength={120}
              value={sourceValue}
              placeholder="例如：模块爱"
              onChange={(event) => setSourceValue(event.target.value)}
            />
          </label>
          <span className="terminology-arrow">→</span>
          <label>
            标准写法
            <input
              maxLength={120}
              value={normalizedValue}
              placeholder="例如：功能模块 A"
              onChange={(event) => setNormalizedValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  void handleSave()
                }
              }}
            />
          </label>
          <button
            type="button"
            className="secondary-button terminology-save"
            disabled={!canSave || saving}
            onClick={() => void handleSave()}
          >
            {saving ? <><span className="spinner dark" /> 保存中</> : <><Icon name="plus" /> 保存并应用</>}
          </button>
        </div>

        <p className="terminology-help">
          保存后会立即修正逐字稿和未确认报告；下一次生成也会自动使用。
        </p>

        <div className="terminology-list" role="region" aria-label="项目术语与口语矫正记录表" tabIndex={0}>
          {loading ? (
            <p className="terminology-empty">正在读取项目记忆…</p>
          ) : entries.length === 0 ? (
            <p className="terminology-empty">还没有记录。遇到重复错词时，在上方登记一次即可。</p>
          ) : entries.map((entry) => (
            <article className="terminology-entry" key={entry.id}>
              <div className="terminology-pair">
                <span>{entry.sourceValue}</span>
                <span className="terminology-inline-arrow">→</span>
                <strong>{entry.normalizedValue}</strong>
              </div>
              <div className="terminology-entry-actions">
                <span className={`memory-scope ${entry.scope}`}>{entry.scope === 'project' ? '本项目' : entry.scope === 'global' ? '全局' : '临时'}</span>
                <button type="button" onClick={() => handleEdit(entry)}>编辑</button>
                <button
                  type="button"
                  disabled={!canApplyToDraft}
                  title={canApplyToDraft ? '应用到当前逐字稿和报告' : '生成未确认报告后可应用'}
                  onClick={() => onApply(entry)}
                >
                  应用
                </button>
                {entry.projectId ? (
                  <button
                    type="button"
                    className="terminology-delete"
                    disabled={deletingId === entry.id}
                    onClick={() => void handleDelete(entry)}
                  >
                    {deletingId === entry.id ? '删除中' : '删除'}
                  </button>
                ) : <span className="terminology-readonly">只读</span>}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

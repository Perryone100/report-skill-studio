import { useState } from 'react'
import type { TerminologyMemoryEntry } from '../api'
import { Icon } from './Icons'

interface TerminologyMemoryPanelProps {
  projectName: string
  entries: TerminologyMemoryEntry[]
  loading: boolean
  onSave: (sourceValue: string, normalizedValue: string) => Promise<void>
  onDelete: (entry: TerminologyMemoryEntry) => Promise<void>
}

export function TerminologyMemoryPanel({
  projectName,
  entries,
  loading,
  onSave,
  onDelete,
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

  return (
    <details className="terminology-panel">
      <summary>
        <span className="terminology-summary-icon"><Icon name="edit" /></span>
        <span>
          <strong>项目专词与口语矫正</strong>
          <small>为“{projectName || '当前项目'}”保存，下一次生成前自动应用</small>
        </span>
        <b>{entries.length} 条</b>
      </summary>

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
            {saving ? <><span className="spinner dark" /> 保存中</> : <><Icon name="plus" /> 保存矫正</>}
          </button>
        </div>

        <p className="terminology-help">
          仅保存你确认过的对应关系。再次输入相同原始说法会更新原记录，不会重复增加。
        </p>

        <div className="terminology-table" role="region" aria-label="项目术语与口语矫正记录表" tabIndex={0}>
          <table>
            <thead><tr><th>原始说法</th><th>标准写法</th><th>范围</th><th>操作</th></tr></thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4} className="terminology-empty">正在读取项目记忆…</td></tr>
              ) : entries.length === 0 ? (
                <tr><td colSpan={4} className="terminology-empty">还没有记录。遇到重复错词时，在上方登记一次即可。</td></tr>
              ) : entries.map((entry) => (
                <tr key={entry.id}>
                  <td>{entry.sourceValue}</td>
                  <td><strong>{entry.normalizedValue}</strong></td>
                  <td><span className={`memory-scope ${entry.scope}`}>{entry.scope === 'project' ? '本项目' : entry.scope === 'global' ? '全局' : '临时'}</span></td>
                  <td>
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  )
}

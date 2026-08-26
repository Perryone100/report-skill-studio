import { useState } from 'react'
import type { ProjectSummary } from '../api'
import { Icon } from './Icons'

interface PrivacyDataDialogProps {
  project: ProjectSummary
  reportCount: number
  libraryRoot: string
  onExportBackup: () => Promise<void>
  onClearReports: () => Promise<void>
  onDeleteProject: () => Promise<void>
  onClose: () => void
}

type Action = 'backup' | 'clear' | 'delete' | null

export function PrivacyDataDialog({
  project,
  reportCount,
  libraryRoot,
  onExportBackup,
  onClearReports,
  onDeleteProject,
  onClose,
}: PrivacyDataDialogProps) {
  const [action, setAction] = useState<Action>(null)
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')

  const run = async (nextAction: Exclude<Action, null>, operation: () => Promise<void>) => {
    if (action) return
    setAction(nextAction)
    setError('')
    try {
      await operation()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '操作失败。')
    } finally {
      setAction(null)
    }
  }

  const handleClear = () => {
    if (reportCount === 0) return
    if (!window.confirm(`确定清空“${project.name}”的 ${reportCount} 份报告和未被外部修改的 Markdown 吗？`)) return
    void run('clear', onClearReports)
  }

  const canDelete = confirmation.trim() === project.name && !action

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !action) onClose()
    }}>
      <section className="skill-dialog privacy-dialog" role="dialog" aria-modal="true" aria-labelledby="privacy-dialog-title">
        <header>
          <div>
            <span className="eyebrow">本地数据</span>
            <h2 id="privacy-dialog-title">隐私与数据管理</h2>
            <p>{project.name} · {reportCount} 份报告</p>
          </div>
          <button type="button" className="dialog-close" onClick={onClose} disabled={Boolean(action)} aria-label="关闭">×</button>
        </header>

        <div className="skill-dialog-body privacy-dialog-body">
          <section className="privacy-summary">
            <Icon name="document" />
            <div>
              <strong>数据默认保存在本机</strong>
              <p>SQLite 保存结构化数据；Markdown 位于 {libraryRoot}。备份不包含模型 API 密钥。</p>
            </div>
          </section>

          <section className="privacy-action-card">
            <div>
              <strong>导出项目备份</strong>
              <p>下载 ZIP，包含项目、逐字稿、报告版本、专词记忆和 Markdown。</p>
            </div>
            <button type="button" onClick={() => void run('backup', onExportBackup)} disabled={Boolean(action)}>
              <Icon name="download" /> {action === 'backup' ? '正在打包' : '下载备份'}
            </button>
          </section>

          <section className="privacy-cloud-note">
            <Icon name="warning" />
            <p>选择云模型时，生成前会再次确认。会发送当前逐字稿、Skill 写作规则、结构 Schema 和相关项目专词；本地 mock 不会联网。</p>
          </section>

          <section className="privacy-danger-zone">
            <div>
              <strong>危险操作</strong>
              <p>如果 Markdown 已在 Obsidian 中修改，工作台会拒绝删除并保留数据。</p>
            </div>
            <button type="button" className="danger-outline" disabled={reportCount === 0 || Boolean(action)} onClick={handleClear}>
              {action === 'clear' ? '正在清理' : '清空报告历史'}
            </button>
            <label>
              <span>输入项目名称“{project.name}”后可删除整个项目</span>
              <input value={confirmation} disabled={Boolean(action)} onChange={(event) => setConfirmation(event.target.value)} />
            </label>
            <button type="button" className="danger-solid" disabled={!canDelete} onClick={() => void run('delete', onDeleteProject)}>
              {action === 'delete' ? '正在删除' : '删除项目及本地数据'}
            </button>
          </section>

          {error && <div className="skill-dialog-error"><Icon name="warning" /> {error}</div>}
        </div>
      </section>
    </div>
  )
}

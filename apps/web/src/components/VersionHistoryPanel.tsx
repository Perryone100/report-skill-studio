import type { ReportVersionEntry } from '../api'
import { formatRelativeTime } from '../domain/workbench'
import { Icon } from './Icons'

interface VersionHistoryPanelProps {
  versions: ReportVersionEntry[]
  currentVersion: number | null
  confirmed: boolean
  restoringVersion: number | null
  onRestore: (version: number) => void
}

const reasonLabels: Record<string, string> = {
  created: '创建报告',
  generated: '模型生成',
  edited: '确认前保存',
  updated: '确认前保存',
  confirmed: '内容确认',
}

function reasonLabel(reason: string) {
  if (reason.startsWith('restored')) return '恢复历史版本'
  if (reason.startsWith('generated:')) return '模型生成'
  return reasonLabels[reason] ?? reason
}

export function VersionHistoryPanel({
  versions,
  currentVersion,
  confirmed,
  restoringVersion,
  onRestore,
}: VersionHistoryPanelProps) {
  if (versions.length === 0) return null

  return (
    <section className="version-panel">
      <div className="version-heading">
        <span><Icon name="document" /></span>
        <div>
          <strong>版本记录</strong>
          <small>{confirmed ? '恢复后会创建一份新草稿' : '可回到任一已保存版本'}</small>
        </div>
        <b>{versions.length} 个</b>
      </div>
      <div className="version-list">
        {versions.map((version) => (
          <article key={version.id} className={!version.hasContent ? 'empty' : ''}>
            <div className="version-copy">
              <strong>v{version.version} · {reasonLabel(version.reason)}</strong>
              <small>{formatRelativeTime(version.createdAt)}</small>
            </div>
            {version.version === currentVersion ? (
              <span className="current-version">当前</span>
            ) : (
              <button
                type="button"
                disabled={!version.hasContent || restoringVersion !== null}
                title={version.hasContent ? '恢复这个版本' : '创建时尚无报告内容'}
                onClick={() => onRestore(version.version)}
              >
                {restoringVersion === version.version ? '恢复中' : '恢复'}
              </button>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}

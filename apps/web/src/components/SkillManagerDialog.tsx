import { useRef, useState } from 'react'
import type { SkillOption } from '../api'
import { Icon } from './Icons'

interface SkillManagerDialogProps {
  skills: SkillOption[]
  onInstall: (file: File, replaceExisting: boolean) => Promise<void>
  onDelete: (skill: SkillOption) => Promise<void>
  onClose: () => void
}

export function SkillManagerDialog({ skills, onInstall, onDelete, onClose }: SkillManagerDialogProps) {
  const [file, setFile] = useState<File | null>(null)
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [busyAction, setBusyAction] = useState('')
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const install = async () => {
    if (!file || busyAction) return
    setBusyAction('install')
    setError('')
    try {
      await onInstall(file, replaceExisting)
      setFile(null)
      setReplaceExisting(false)
      if (inputRef.current) inputRef.current.value = ''
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Skill 安装失败。')
    } finally {
      setBusyAction('')
    }
  }

  const remove = async (skill: SkillOption) => {
    if (busyAction || !skill.canDelete) return
    if (!window.confirm(`确定删除本地 Skill“${skill.name}”吗？已生成的报告不会被删除。`)) return
    setBusyAction(`delete:${skill.id}`)
    setError('')
    try {
      await onDelete(skill)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Skill 删除失败。')
    } finally {
      setBusyAction('')
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !busyAction) onClose()
    }}>
      <section className="skill-dialog" role="dialog" aria-modal="true" aria-labelledby="skill-dialog-title">
        <header>
          <div>
            <span className="eyebrow">本地扩展</span>
            <h2 id="skill-dialog-title">管理报告 Skill</h2>
            <p>上传声明式 ZIP 包。安装前会检查结构、报告契约和模板安全性。</p>
          </div>
          <button className="dialog-close" type="button" onClick={onClose} disabled={Boolean(busyAction)} aria-label="关闭">×</button>
        </header>

        <div className="skill-dialog-body">
          <section className="skill-upload">
            <label className="skill-file-field">
              <span>选择 Skill ZIP</span>
              <input
                ref={inputRef}
                type="file"
                accept=".zip,application/zip"
                disabled={Boolean(busyAction)}
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null)
                  setError('')
                }}
              />
            </label>
            {file && <p className="selected-file"><Icon name="document" /> {file.name} · {(file.size / 1024).toFixed(1)} KB</p>}
            <label className="replace-skill">
              <input
                type="checkbox"
                checked={replaceExisting}
                disabled={Boolean(busyAction)}
                onChange={(event) => setReplaceExisting(event.target.checked)}
              />
              同 ID 时替换已有的用户 Skill
            </label>
            <button className="primary-button" type="button" disabled={!file || Boolean(busyAction)} onClick={() => void install()}>
              {busyAction === 'install' ? <><span className="spinner" /> 正在检查并安装</> : <><Icon name="plus" /> 安装 Skill</>}
            </button>
          </section>

          {error && <div className="skill-dialog-error" role="alert"><Icon name="warning" /> <span>{error}</span></div>}

          <section className="installed-skills">
            <div className="installed-skills-heading">
              <h3>已安装</h3>
              <span>{skills.length} 个</span>
            </div>
            <div className="installed-skill-list">
              {skills.map((skill) => (
                <article key={skill.id}>
                  <div className="skill-source-icon"><Icon name={skill.source === 'bundled' ? 'briefcase' : 'document'} /></div>
                  <div className="installed-skill-copy">
                    <strong>{skill.name} <small>v{skill.version}</small></strong>
                    <p>{skill.description || '暂无说明'}</p>
                    <code>{skill.id}</code>
                  </div>
                  <div className="installed-skill-actions">
                    <span className={`skill-source ${skill.source}`}>{skill.source === 'bundled' ? '内置' : '用户'}</span>
                    {skill.canDelete && (
                      <button
                        type="button"
                        disabled={Boolean(busyAction)}
                        onClick={() => void remove(skill)}
                      >
                        {busyAction === `delete:${skill.id}` ? '删除中' : '删除'}
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>
      </section>
    </div>
  )
}

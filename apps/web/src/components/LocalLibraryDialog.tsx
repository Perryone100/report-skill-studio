import { useEffect, useState } from 'react'
import type { LocalLibraryInfo } from '../api'
import { Icon } from './Icons'

interface LocalLibraryDialogProps {
  info: LocalLibraryInfo
  onSave: (rootPath: string) => Promise<void>
  onClose: () => void
}

export function LocalLibraryDialog({ info, onSave, onClose }: LocalLibraryDialogProps) {
  const [rootPath, setRootPath] = useState(info.rootPath)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => setRootPath(info.rootPath), [info.rootPath])

  const handleSave = async () => {
    if (!rootPath.trim() || saving) return
    setSaving(true)
    setError('')
    try {
      await onSave(rootPath.trim())
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '本地项目库设置失败。')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !saving) onClose()
    }}>
      <section className="skill-dialog library-dialog" role="dialog" aria-modal="true" aria-labelledby="library-dialog-title">
        <header>
          <div>
            <span className="eyebrow">本地项目库</span>
            <h2 id="library-dialog-title">Markdown 保存位置</h2>
            <p>采用类似 Obsidian 的普通文件夹结构，每个项目文件夹只写入 Markdown 报告。</p>
          </div>
          <button type="button" className="dialog-close" onClick={onClose} disabled={saving} aria-label="关闭">×</button>
        </header>

        <div className="skill-dialog-body">
          <div className="library-structure" aria-label="目录结构示例">
            <span>Report Skill Studio/</span>
            <span>└── 项目名称/</span>
            <strong>　　└── 2026-08-26 周会纪要.md</strong>
          </div>

          <label className="library-path-field">
            <span>本机绝对路径</span>
            <input
              autoFocus
              value={rootPath}
              disabled={saving}
              placeholder="/Users/你的名字/Documents/Report Skill Studio"
              onChange={(event) => setRootPath(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void handleSave()
              }}
            />
          </label>

          <div className={`library-health ${info.exists && info.writable ? 'ready' : ''}`}>
            <Icon name={info.exists && info.writable ? 'check' : 'warning'} />
            <div>
              <strong>{info.exists ? (info.writable ? '目录可写' : '目录不可写') : '保存后将自动创建目录'}</strong>
              <p>HTML 和 PDF 不会写入这里，仍由你点击导出后下载。</p>
            </div>
          </div>

          <p className="library-note">
            浏览器为保护本地文件权限，暂时需要手动填写文件夹的绝对路径。
            如果 Markdown 在 Obsidian 等软件中被修改，工作台会暂停覆盖并提示冲突。
          </p>

          {error && <div className="skill-dialog-error"><Icon name="warning" /> {error}</div>}

          <div className="library-dialog-actions">
            <button type="button" className="text-button" onClick={onClose} disabled={saving}>取消</button>
            <button type="button" className="primary-button" onClick={() => void handleSave()} disabled={!rootPath.trim() || saving}>
              {saving ? <><span className="spinner" /> 正在保存</> : <><Icon name="check" /> 保存位置</>}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

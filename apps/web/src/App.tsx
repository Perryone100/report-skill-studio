import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError } from './api/client'
import {
  apiClient,
  apiMode,
  type ModelOption,
  type LoadedReport,
  type ReportDraft,
  type ReportSummary,
  type ReportVersionEntry,
  type SkillOption,
  type TerminologyMemoryEntry,
  type ValidationIssue,
  type WorkspaceBootstrap,
} from './api'
import { Icon } from './components/Icons'
import { ReportEditor } from './components/ReportEditor'
import { Sidebar } from './components/Sidebar'
import { SkillManagerDialog } from './components/SkillManagerDialog'
import { TerminologyMemoryPanel } from './components/TerminologyMemoryPanel'
import { VersionHistoryPanel } from './components/VersionHistoryPanel'
import {
  applyTerminologyToDraft,
  deriveWorkflowState,
  inferTerminologyCorrections,
  replaceTerminologyInText,
  validateReport,
} from './domain/workbench'

type LoadState = 'loading' | 'ready' | 'error'
type AutosaveStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'error'

const exampleTranscript = `主持人：先同步本周的几个重点。功能模块 A 已完成核心流程联调，遗留问题本周五前收口，下周安排小流量灰度。

产品负责人：业务侧完成了内容验收，历史数据还有一批需要人工复核。整体不影响灰度，但要补充监控。

运营负责人：活动页面 C 的配置和数据回传已经进入 UAT。上线窗口比较紧，希望本周提前锁定验收人。

平台负责人：OCR 和 ASR 的稳定性优化已完成，接下来补成本统计和异常告警。`

function describeIssueField(field: string, draft: ReportDraft): string {
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

function locateReportField(field: string) {
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

function App() {
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [workspace, setWorkspace] = useState<WorkspaceBootstrap | null>(null)
  const [loadError, setLoadError] = useState('')
  const [projectId, setProjectId] = useState('')
  const [skillId, setSkillId] = useState('')
  const [modelId, setModelId] = useState('')
  const [transcript, setTranscript] = useState('')
  const [draft, setDraft] = useState<ReportDraft | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isConfirming, setIsConfirming] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')
  const [serverIssues, setServerIssues] = useState<ValidationIssue[]>([])
  const [showProjectCreator, setShowProjectCreator] = useState(false)
  const [showSkillManager, setShowSkillManager] = useState(false)
  const [projectName, setProjectName] = useState('')
  const [projectDescription, setProjectDescription] = useState('')
  const [isCreatingProject, setIsCreatingProject] = useState(false)
  const [terminologyMemory, setTerminologyMemory] = useState<TerminologyMemoryEntry[]>([])
  const [isLoadingTerminology, setIsLoadingTerminology] = useState(false)
  const [versions, setVersions] = useState<ReportVersionEntry[]>([])
  const [currentReportVersion, setCurrentReportVersion] = useState<number | null>(null)
  const [autosaveStatus, setAutosaveStatus] = useState<AutosaveStatus>('idle')
  const [loadingReportId, setLoadingReportId] = useState('')
  const [restoringVersion, setRestoringVersion] = useState<number | null>(null)
  const [learningBaseline, setLearningBaseline] = useState<ReportDraft | null>(null)
  const [dismissedSuggestionIds, setDismissedSuggestionIds] = useState<string[]>([])
  const lastSavedSignature = useRef('')
  const saveSequence = useRef(0)

  const draftSignature = (nextDraft: ReportDraft, nextTranscript: string) => JSON.stringify({
    transcript: nextTranscript,
    report: nextDraft,
  })

  const upsertReportSummary = (loaded: LoadedReport) => {
    const summary: ReportSummary = {
      id: loaded.reportId,
      projectId: loaded.projectId,
      title: loaded.title,
      period: loaded.draft?.meeting_date || loaded.updatedAt.slice(0, 10),
      status: loaded.status,
      updatedAt: loaded.updatedAt,
    }
    setWorkspace((current) => {
      if (!current) return current
      return {
        ...current,
        reports: [summary, ...current.reports.filter((report) => report.id !== summary.id)],
      }
    })
  }

  const adoptLoadedReport = (loaded: LoadedReport) => {
    const checkpoint = loaded.versions.find((version) => version.content)?.content
    const baseline = checkpoint
      ? { ...structuredClone(checkpoint), reportId: loaded.reportId }
      : loaded.draft ? structuredClone(loaded.draft) : null
    setProjectId(loaded.projectId)
    setTranscript(loaded.transcript)
    setSkillId((current) => loaded.skillId || current)
    setDraft(loaded.draft)
    setConfirmed(loaded.status === 'confirmed')
    setServerIssues(loaded.issues)
    setVersions(loaded.versions)
    setCurrentReportVersion(loaded.version)
    setLearningBaseline(baseline)
    setDismissedSuggestionIds([])
    lastSavedSignature.current = loaded.draft ? draftSignature(loaded.draft, loaded.transcript) : ''
    setAutosaveStatus(loaded.draft ? 'saved' : 'idle')
    upsertReportSummary(loaded)
  }

  const loadWorkspace = async () => {
    setLoadState('loading')
    setLoadError('')
    try {
      const result = await apiClient.getWorkspace()
      setWorkspace(result)
      setProjectId((current) => current || result.projects[0]?.id || '')
      setSkillId((current) => current || result.skills[0]?.id || '')
      setModelId((current) => current || result.models.find((model) => model.ready)?.id || '')
      setShowProjectCreator(result.projects.length === 0)
      setLoadState('ready')
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : '工作台加载失败。')
      setLoadState('error')
    }
  }

  useEffect(() => {
    void loadWorkspace()
  }, [])

  useEffect(() => {
    if (!projectId) {
      setTerminologyMemory([])
      return
    }
    const controller = new AbortController()
    setIsLoadingTerminology(true)
    void apiClient.listTerminologyMemory(projectId, controller.signal)
      .then(setTerminologyMemory)
      .catch((error) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setActionError(error instanceof Error ? error.message : '项目专词读取失败。')
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingTerminology(false)
      })
    return () => controller.abort()
  }, [projectId])

  useEffect(() => {
    if (!draft || confirmed) return
    const signature = draftSignature(draft, transcript)
    if (signature === lastSavedSignature.current) return

    setAutosaveStatus('dirty')
    const sequence = ++saveSequence.current
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setAutosaveStatus('saving')
      void apiClient.saveReportDraft(draft, transcript, controller.signal)
        .then((saved) => {
          if (sequence !== saveSequence.current) return
          lastSavedSignature.current = signature
          setCurrentReportVersion(saved.version)
          setAutosaveStatus('saved')
          setWorkspace((current) => current ? {
            ...current,
            reports: current.reports.map((report) => report.id === draft.reportId ? {
              ...report,
              title: draft.title,
              period: draft.meeting_date,
              updatedAt: saved.updatedAt,
            } : report),
          } : current)
        })
        .catch((error) => {
          if (controller.signal.aborted || sequence !== saveSequence.current) return
          setAutosaveStatus('error')
          setActionError(error instanceof Error ? error.message : '草稿自动保存失败。')
        })
    }, 800)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [draft, transcript, confirmed])

  const localIssues = useMemo(
    () => (draft ? validateReport(draft).map((issue) => ({ ...issue, source: 'local' as const })) : []),
    [draft],
  )
  const issues = useMemo(
    () => [
      ...serverIssues,
      ...localIssues.filter((issue) => issue.id !== 'quality-pass' || serverIssues.length === 0),
    ],
    [localIssues, serverIssues],
  )
  const workflow = deriveWorkflowState({
    transcript,
    projectId,
    skillId,
    modelId,
    draft,
    issues,
    isGenerating,
    isConfirmed: confirmed,
  })

  const selectedProject = workspace?.projects.find((project) => project.id === projectId)
  const selectedSkill = workspace?.skills.find((skill) => skill.id === skillId)
  const selectedModel = workspace?.models.find((model) => model.id === modelId)
  const warningCount = issues.filter((issue) => issue.severity === 'warning').length
  const correctionSuggestions = useMemo(() => {
    if (!learningBaseline || !draft || confirmed) return []
    const knownSources = new Set(terminologyMemory.map((entry) => entry.sourceValue.toLocaleLowerCase()))
    const dismissed = new Set(dismissedSuggestionIds)
    return inferTerminologyCorrections(learningBaseline, draft)
      .filter((suggestion) => !knownSources.has(suggestion.sourceValue.toLocaleLowerCase()))
      .filter((suggestion) => !dismissed.has(suggestion.id))
  }, [learningBaseline, draft, confirmed, terminologyMemory, dismissedSuggestionIds])

  const updateDraft = (nextDraft: ReportDraft) => {
    setDraft(nextDraft)
    setConfirmed(false)
    setServerIssues([])
    setNotice('内容已修改，正在等待自动保存。')
  }

  const handleGenerate = async () => {
    if (!workflow.canGenerate) return
    setIsGenerating(true)
    setActionError('')
    setNotice('')
    setConfirmed(false)
    try {
      const result = await apiClient.generateReport({
        projectId,
        title: `${selectedProject?.name ?? '项目'}周会纪要`,
        transcript,
        skillId,
        modelId,
      })
      const loaded = await apiClient.loadReport(result.report.reportId)
      adoptLoadedReport(loaded)
      setNotice('报告已生成，请检查并确认内容。')
    } catch (error) {
      if (error instanceof ApiError) {
        setActionError(`${error.message}（${error.code}）`)
      } else {
        setActionError(error instanceof Error ? error.message : '报告生成失败。')
      }
    } finally {
      setIsGenerating(false)
    }
  }

  const handleConfirm = async () => {
    if (!draft || !workflow.canConfirm) return
    setIsConfirming(true)
    setActionError('')
    try {
      const result = await apiClient.confirmReport(draft, transcript)
      setDraft(result.report)
      setServerIssues(result.issues)
      setConfirmed(result.confirmed)
      if (result.confirmed) {
        const loaded = await apiClient.loadReport(result.report.reportId)
        adoptLoadedReport(loaded)
      }
      setNotice(result.confirmed ? '内容已确认，现在可以导出。' : '服务端检查发现问题，请修改后重新确认。')
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '确认失败。')
    } finally {
      setIsConfirming(false)
    }
  }

  const handleExport = async () => {
    if (!draft || !workflow.canExport) return
    setIsExporting(true)
    setActionError('')
    try {
      const artifact = await apiClient.exportReport(draft)
      const url = URL.createObjectURL(artifact.blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = artifact.fileName
      anchor.click()
      URL.revokeObjectURL(url)
      setNotice(
        artifact.mock
          ? 'Mock 阶段已导出 HTML 数据预览；接入渲染服务后将直接生成 PDF。'
          : 'PDF 已导出。',
      )
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '导出失败。')
    } finally {
      setIsExporting(false)
    }
  }

  const handleSelectReport = async (report: ReportSummary) => {
    if (loadingReportId) return
    setLoadingReportId(report.id)
    setActionError('')
    try {
      const loaded = await apiClient.loadReport(report.id)
      adoptLoadedReport(loaded)
      setNotice(`已打开“${report.title}”。`)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '历史报告读取失败。')
    } finally {
      setLoadingReportId('')
    }
  }

  const handleRestoreVersion = async (version: number) => {
    if (!draft || restoringVersion !== null) return
    setRestoringVersion(version)
    setActionError('')
    try {
      const loaded = await apiClient.restoreReportVersion(draft.reportId, version)
      adoptLoadedReport(loaded)
      setNotice(confirmed
        ? `已从 v${version} 创建一份可编辑的新草稿。`
        : `已恢复到 v${version}，并保留了恢复前的版本。`)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '历史版本恢复失败。')
    } finally {
      setRestoringVersion(null)
    }
  }

  const handleCreateProject = async () => {
    if (!projectName.trim() || isCreatingProject) return
    setIsCreatingProject(true)
    setActionError('')
    try {
      const project = await apiClient.createProject({
        name: projectName.trim(),
        description: projectDescription.trim(),
      })
      setWorkspace((current) => current ? { ...current, projects: [...current.projects, project] } : current)
      setProjectId(project.id)
      setProjectName('')
      setProjectDescription('')
      setShowProjectCreator(false)
      setNotice(`项目“${project.name}”已创建。`)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '项目创建失败。')
    } finally {
      setIsCreatingProject(false)
    }
  }

  const handleInstallSkill = async (file: File, replaceExisting: boolean) => {
    const installed = await apiClient.installSkill(file, replaceExisting)
    setWorkspace((current) => current ? {
      ...current,
      skills: [...current.skills.filter((skill) => skill.id !== installed.id), installed],
    } : current)
    setSkillId(installed.id)
    setNotice(`Skill“${installed.name}”已安装并选中。`)
  }

  const handleDeleteSkill = async (skill: SkillOption) => {
    await apiClient.deleteSkill(skill.id)
    const fallbackSkillId = workspace?.skills.find((item) => item.id !== skill.id)?.id ?? ''
    setWorkspace((current) => current ? {
      ...current,
      skills: current.skills.filter((item) => item.id !== skill.id),
    } : current)
    if (skillId === skill.id) setSkillId(fallbackSkillId)
    setNotice(`本地 Skill“${skill.name}”已删除。`)
  }

  const applyTerminologyToCurrentWork = (sourceValue: string, normalizedValue: string) => {
    const transcriptResult = replaceTerminologyInText(transcript, sourceValue, normalizedValue)
    if (transcriptResult.count > 0) setTranscript(transcriptResult.text)

    let reportCount = 0
    if (draft && !confirmed) {
      const reportResult = applyTerminologyToDraft(draft, sourceValue, normalizedValue)
      reportCount = reportResult.count
      if (reportCount > 0) {
        setDraft(reportResult.draft)
        setServerIssues([])
        setConfirmed(false)
      }
    }
    return { transcriptCount: transcriptResult.count, reportCount }
  }

  const handleSaveTerminology = async (sourceValue: string, normalizedValue: string) => {
    if (!projectId) return
    setActionError('')
    try {
      const saved = await apiClient.saveTerminologyMemory({ projectId, sourceValue, normalizedValue })
      setTerminologyMemory((current) => [saved, ...current.filter((item) => item.id !== saved.id)])
      const applied = applyTerminologyToCurrentWork(saved.sourceValue, saved.normalizedValue)
      const appliedMessage = applied.reportCount > 0
        ? `并修正当前报告 ${applied.reportCount} 处`
        : applied.transcriptCount > 0
          ? `并修正逐字稿 ${applied.transcriptCount} 处`
          : '；当前内容中没有发现该写法'
      setNotice(`已记住“${saved.sourceValue} → ${saved.normalizedValue}”${appliedMessage}，下次生成继续应用。`)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '矫正规则保存失败。')
      throw error
    }
  }

  const handleApplyTerminology = (entry: TerminologyMemoryEntry) => {
    const applied = applyTerminologyToCurrentWork(entry.sourceValue, entry.normalizedValue)
    const total = applied.transcriptCount + applied.reportCount
    setNotice(total > 0
      ? `已应用“${entry.sourceValue} → ${entry.normalizedValue}”，共修正 ${total} 处。`
      : '当前逐字稿和报告中没有发现需要替换的内容。')
  }

  const handleDeleteTerminology = async (entry: TerminologyMemoryEntry) => {
    setActionError('')
    try {
      await apiClient.deleteTerminologyMemory(entry.id)
      setTerminologyMemory((current) => current.filter((item) => item.id !== entry.id))
      setNotice(`已删除“${entry.sourceValue} → ${entry.normalizedValue}”。`)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '矫正规则删除失败。')
      throw error
    }
  }

  if (loadState === 'loading') {
    return <LoadingScreen />
  }

  if (loadState === 'error' || !workspace) {
    return (
      <main className="fatal-state">
        <div className="fatal-icon"><Icon name="warning" /></div>
        <h1>工作台暂时无法加载</h1>
        <p>{loadError || '没有获取到工作区数据。'}</p>
        <button className="primary-button" type="button" onClick={() => void loadWorkspace()}>
          <Icon name="refresh" /> 重新加载
        </button>
      </main>
    )
  }

  return (
    <div className="app-shell">
      <Sidebar
        projects={workspace.projects}
        reports={workspace.reports}
        activeProjectId={projectId}
        activeReportId={draft?.reportId}
        onCreateProject={() => setShowProjectCreator(true)}
        onSelectProject={(nextProjectId) => {
          setProjectId(nextProjectId)
          setDraft(null)
          setConfirmed(false)
          setServerIssues([])
          setVersions([])
          setCurrentReportVersion(null)
          setLearningBaseline(null)
          setDismissedSuggestionIds([])
          lastSavedSignature.current = ''
          setAutosaveStatus('idle')
          setNotice('')
        }}
        onSelectReport={(report) => void handleSelectReport(report)}
      />

      <main className="workspace">
        <header className="workspace-header">
          <div>
            <div className="breadcrumb">项目 / {selectedProject?.name}</div>
            <h1>生成周会纪要</h1>
            <p>粘贴会议逐字稿，生成结构清晰、可检查的管理报告。</p>
          </div>
          <div className="header-meta"><span className="local-dot" /> {apiMode === 'mock' ? 'Mock 演示模式' : '本地服务'}</div>
        </header>

        {(actionError || notice) && (
          <div className={`banner ${actionError ? 'error' : 'success'}`} role={actionError ? 'alert' : 'status'}>
            <Icon name={actionError ? 'warning' : 'check'} />
            <span>{actionError || notice}</span>
            <button type="button" onClick={() => { setActionError(''); setNotice('') }} aria-label="关闭提示">×</button>
          </div>
        )}

        {showProjectCreator && (
          <section className="project-creator">
            <div className="project-creator-copy">
              <span className="step-badge">开始使用</span>
              <h2>{workspace.projects.length === 0 ? '先创建第一个项目' : '创建新项目'}</h2>
              <p>项目用于归档逐字稿、报告版本和已确认的术语记忆，不会被隐式创建。</p>
            </div>
            <div className="project-creator-form">
              <label>
                项目名称
                <input
                  autoFocus
                  value={projectName}
                  placeholder="例如：产品研发组"
                  disabled={isCreatingProject}
                  onChange={(event) => setProjectName(event.target.value)}
                />
              </label>
              <label>
                项目说明（可选）
                <input
                  value={projectDescription}
                  placeholder="简要说明项目范围"
                  disabled={isCreatingProject}
                  onChange={(event) => setProjectDescription(event.target.value)}
                />
              </label>
              <div className="project-creator-actions">
                {workspace.projects.length > 0 && (
                  <button type="button" className="text-button" onClick={() => setShowProjectCreator(false)}>取消</button>
                )}
                <button
                  type="button"
                  className="primary-button"
                  disabled={!projectName.trim() || isCreatingProject}
                  onClick={() => void handleCreateProject()}
                >
                  {isCreatingProject ? <><span className="spinner" /> 正在创建</> : <><Icon name="plus" /> 创建项目</>}
                </button>
              </div>
            </div>
          </section>
        )}

        <section className="generation-card">
          <div className="generation-head">
            <div>
              <span className="step-badge">第一步</span>
              <h2>准备生成内容</h2>
            </div>
            <button
              type="button"
              className="text-button"
              onClick={() => setTranscript(exampleTranscript)}
              disabled={isGenerating}
            >
              填入示例逐字稿
            </button>
          </div>

          <div className="input-grid">
            <label className="transcript-field">
              <span>会议逐字稿</span>
              <textarea
                value={transcript}
                onChange={(event) => setTranscript(event.target.value)}
                placeholder="在这里粘贴飞书妙记、录音转写或手工会议记录……"
                disabled={isGenerating}
              />
              <small>
                <span>{transcript.trim().length.toLocaleString()} 字符</span>
                <span>内容仅在你选择云模型时发送</span>
              </small>
            </label>

            <div className="generation-settings">
              <SelectField
                label="报告 Skill"
                value={skillId}
                options={workspace.skills}
                disabled={isGenerating}
                onChange={setSkillId}
                renderLabel={(skill) => `${skill.name} · v${skill.version}`}
              />
              <button type="button" className="skill-manage-button" disabled={isGenerating} onClick={() => setShowSkillManager(true)}>
                <Icon name="settings" /> 管理与安装 Skill
              </button>
              <SelectField
                label="写作模型"
                value={modelId}
                options={workspace.models}
                disabled={isGenerating}
                onChange={setModelId}
                renderLabel={(model) => `${model.name}${model.locality === 'local' ? ' · 本地' : ''}`}
                isOptionDisabled={(model) => !model.ready}
              />

              <div className="selection-summary">
                <div><Icon name="document" /><span><small>内容结构</small>{selectedSkill?.name}</span></div>
                <div><Icon name="sparkle" /><span><small>模型来源</small>{selectedModel?.provider}</span></div>
              </div>

              <button
                type="button"
                className="generate-button"
                disabled={!workflow.canGenerate}
                onClick={() => void handleGenerate()}
              >
                {isGenerating ? <><span className="spinner" /> 正在生成报告</> : <><Icon name="sparkle" /> 生成结构化报告</>}
              </button>
              {!workflow.canGenerate && !isGenerating && (
                <p className="button-help">请填写至少 20 个字符，并选择可用的 Skill 与模型。</p>
              )}
            </div>
          </div>

        </section>

        <div className="content-grid">
          {draft ? (
            <ReportEditor
              draft={draft}
              confirmed={confirmed}
              autosaveStatus={autosaveStatus}
              onChange={updateDraft}
            />
          ) : (
            <section className="empty-report">
              <div className="empty-illustration">
                <Icon name="document" />
                <span><Icon name="sparkle" /></span>
              </div>
              <h2>报告内容将在这里生成</h2>
              <p>我们会按照所选 Skill 生成结构化内容，方便逐项检查和修改。</p>
              <div className="empty-features">
                <span><Icon name="check" /> 术语自动检查</span>
                <span><Icon name="check" /> 修改后再确认</span>
                <span><Icon name="check" /> 固定模板导出</span>
              </div>
            </section>
          )}

          <aside className="right-rail">
            {projectId && (
              <TerminologyMemoryPanel
                projectName={selectedProject?.name ?? ''}
                entries={terminologyMemory}
                loading={isLoadingTerminology}
                onSave={handleSaveTerminology}
                onApply={handleApplyTerminology}
                onDelete={handleDeleteTerminology}
                canApplyToDraft={!confirmed && Boolean(transcript.trim() || draft)}
                suggestions={correctionSuggestions}
                onDismissSuggestion={(suggestion) => {
                  setDismissedSuggestionIds((current) => [...current, suggestion.id])
                }}
              />
            )}

            <VersionHistoryPanel
              versions={versions}
              currentVersion={confirmed ? currentReportVersion : null}
              confirmed={confirmed}
              restoringVersion={restoringVersion}
              onRestore={(version) => void handleRestoreVersion(version)}
            />

            <section className="quality-panel">
              <div className="quality-heading">
              <div>
                <span className="eyebrow">质量门禁</span>
                <h2>自动检查</h2>
              </div>
              {draft && (
                <span className={`issue-count ${workflow.hasBlockingIssue ? 'blocked' : warningCount > 0 ? 'suggestions' : ''}`}>
                  {workflow.hasBlockingIssue
                    ? `${issues.filter((issue) => issue.severity === 'error').length} 项须处理`
                    : warningCount > 0
                      ? `${warningCount} 项建议`
                      : '已通过'}
                </span>
              )}
              </div>

              {!draft ? (
                <div className="quality-empty">
                  <Icon name="check" />
                  <p>生成报告后，将检查术语、必填章节和内部表达。</p>
                </div>
              ) : (
                <div className="issue-list">
                  {issues.map((issue) => (
                    <div className={`issue-item ${issue.severity}`} key={issue.id}>
                      <span className="issue-icon"><Icon name={issue.severity === 'info' ? 'check' : 'warning'} /></span>
                      <div>
                        <strong>{issue.title}<small className={`issue-source ${issue.source ?? 'local'}`}>{issue.source === 'server' ? '服务端' : '本地'}</small></strong>
                        <p>{issue.message}</p>
                        {issue.suggestion && <p className="issue-suggestion">建议：{issue.suggestion}</p>}
                        {issue.field && (
                          <button
                            type="button"
                            className="issue-location"
                            onClick={() => locateReportField(issue.field!)}
                          >
                            定位到：{describeIssueField(issue.field, draft)}
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="quality-actions">
                <button
                  type="button"
                  className="secondary-button"
                  disabled={!workflow.canConfirm || isConfirming}
                  onClick={() => void handleConfirm()}
                >
                  {isConfirming ? <><span className="spinner dark" /> 正在确认</> : <><Icon name="check" /> 确认内容</>}
                </button>
                <button
                  type="button"
                  className="primary-button"
                  disabled={!workflow.canExport || isExporting}
                  onClick={() => void handleExport()}
                >
                  {isExporting ? <><span className="spinner" /> 正在导出</> : <><Icon name="download" /> 导出 PDF</>}
                </button>
                {draft && !confirmed && <p>只有错误会阻止确认；建议项不影响确认和导出。</p>}
              </div>
            </section>
          </aside>
        </div>
      </main>
      {showSkillManager && (
        <SkillManagerDialog
          skills={workspace.skills}
          onInstall={handleInstallSkill}
          onDelete={handleDeleteSkill}
          onClose={() => setShowSkillManager(false)}
        />
      )}
    </div>
  )
}

function SelectField<Option extends SkillOption | ModelOption>({
  label,
  value,
  options,
  disabled,
  onChange,
  renderLabel,
  isOptionDisabled = () => false,
}: {
  label: string
  value: string
  options: Option[]
  disabled: boolean
  onChange: (value: string) => void
  renderLabel: (option: Option) => string
  isOptionDisabled?: (option: Option) => boolean
}) {
  return (
    <label className="select-field">
      <span>{label}</span>
      <select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        {options.length === 0 && <option value="">暂无可用选项</option>}
        {options.map((option) => (
          <option key={option.id} value={option.id} disabled={isOptionDisabled(option)}>
            {renderLabel(option)}
          </option>
        ))}
      </select>
    </label>
  )
}

function LoadingScreen() {
  return (
    <div className="loading-shell" aria-label="正在加载工作台">
      <aside><div className="skeleton brand-skeleton" />{[1, 2, 3, 4].map((item) => <div className="skeleton nav-skeleton" key={item} />)}</aside>
      <main>
        <div className="skeleton title-skeleton" />
        <div className="skeleton card-skeleton" />
        <div className="skeleton body-skeleton" />
      </main>
    </div>
  )
}

export default App

import type { ProjectSummary, ReportSummary } from '../api'
import { formatRelativeTime, sortReportsByGeneratedAt } from '../domain/workbench'
import { Icon } from './Icons'

interface SidebarProps {
  projects: ProjectSummary[]
  reports: ReportSummary[]
  activeProjectId: string
  activeReportId?: string
  onCreateProject: () => void
  onOpenSettings: () => void
  onOpenPrivacy: () => void
  onSelectProject: (projectId: string) => void
  onSelectReport: (report: ReportSummary) => void
}

const reportStatusLabel = {
  draft: '草稿',
  confirmed: '已确认',
  exported: '已导出',
}

export function Sidebar({
  projects,
  reports,
  activeProjectId,
  activeReportId,
  onCreateProject,
  onOpenSettings,
  onOpenPrivacy,
  onSelectProject,
  onSelectReport,
}: SidebarProps) {
  const visibleReports = sortReportsByGeneratedAt(
    reports.filter((report) => report.projectId === activeProjectId),
  )

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark"><Icon name="document" /></div>
        <div>
          <strong>Report Skill Studio</strong>
          <span>本地报告工作台</span>
        </div>
      </div>

      <nav aria-label="项目与历史报告">
        <div className="sidebar-section">
          <div className="sidebar-section-heading">
            <span>项目</span>
            <button type="button" className="icon-button" aria-label="新建项目" onClick={onCreateProject}>
              <Icon name="plus" />
            </button>
          </div>
          <div className="project-list">
            {projects.map((project) => (
              <button
                key={project.id}
                type="button"
                className={`project-button ${project.id === activeProjectId ? 'active' : ''}`}
                onClick={() => onSelectProject(project.id)}
              >
                <span className="project-icon"><Icon name="briefcase" /></span>
                <span className="project-copy">
                  <strong>{project.name}</strong>
                  <small>{project.description}</small>
                </span>
                <Icon name="chevron" className="project-chevron" />
              </button>
            ))}
          </div>
        </div>

        <div className="sidebar-section report-history">
          <div className="sidebar-section-heading"><span>最近报告</span></div>
          {visibleReports.length > 0 ? (
            <div className="report-list">
              {visibleReports.map((report) => (
                <button
                  key={report.id}
                  type="button"
                  className={report.id === activeReportId ? 'active' : ''}
                  onClick={() => onSelectReport(report)}
                >
                  <span className="history-icon"><Icon name="document" /></span>
                  <span className="history-copy">
                    <strong>{report.title}</strong>
                    <small>{formatRelativeTime(report.generatedAt)}</small>
                  </span>
                  <span className={`status-dot ${report.status}`} title={reportStatusLabel[report.status]} />
                </button>
              ))}
            </div>
          ) : (
            <p className="sidebar-empty">这个项目还没有报告</p>
          )}
        </div>
      </nav>

      <div className="sidebar-footer">
        <div className="privacy-note"><span /> 数据默认保存在本机</div>
        <button type="button" onClick={onOpenPrivacy}><Icon name="briefcase" /> 隐私与数据管理</button>
        <button type="button" onClick={onOpenSettings}><Icon name="settings" /> 本地项目库设置</button>
      </div>
    </aside>
  )
}

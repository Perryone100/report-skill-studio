import { copyFileSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const outputRoot = join(repositoryRoot, 'outputs', 'test-skills')
const templateRoot = join(repositoryRoot, 'skills', 'default-weekly-meeting', 'templates')

const skills = [
  {
    id: 'test-smoke-report',
    name: '[测试] 兼容性冒烟报告',
    version: '1.0.0',
    description: '用于验证安装、选择、生成、编辑、确认和导出的最宽松测试 Skill。',
    flexible: true,
    sections: [],
    terms: [
      { canonical: '测试环境', variants: ['测试环景', '测式环境'] },
    ],
    sample: `主持人：今天验证报告工作台。测试环景已经完成配置，逐字稿导入正常。\n测试人员：本周需要完成生成、编辑、确认和导出四个环节；当前没有真实业务风险。\n主持人：下一步检查自定义 Skill 能否保存，并确认术语会自动改成正确写法。`,
    instructions: `# 兼容性冒烟报告

这是一个纯测试 Skill，用来验证工作台完整流程。只整理输入中明确出现的事实，不补造数字、负责人或日期。

可以按内容需要生成 1—8 个章节。章节标题必须是内容维度，不得把项目名、产品名或人名直接作为章节标题。可使用段落、列表、表格、状态卡片和重点提示。仅输出符合 Schema 的 JSON。`,
  },
  {
    id: 'test-brief-update',
    name: '[测试] 极简工作简报',
    version: '1.0.0',
    description: '三章节短报告，用于测试精简输出和不同表头。',
    sections: [
      { id: 'key_message', title: '核心结论', block: 'paragraph' },
      { id: 'work_snapshot', title: '工作快照', block: 'project_table', columns: ['事项', '结果', '状态'] },
      { id: 'next_actions', title: '下一步行动', block: 'bullet_list' },
    ],
    terms: [
      { canonical: '迭代计划', variants: ['迭代计画', '一代计划'] },
    ],
    sample: `负责人：本周完成了演示模块的第一轮联调，核心流程 12 项用例通过 10 项，剩余 2 项等待修复。\n产品同学：迭代计画已经确认，下周二前完成问题回归，下周四安排内部验收。\n测试同学：当前状态为进行中，没有阻塞项。`,
    instructions: `# 极简工作简报

把输入压缩成一页可快速浏览的工作简报。保持事实准确，优先保留结果、状态、时间节点和下一步。

固定使用三个章节：核心结论、工作快照、下一步行动。工作快照表格固定为“事项 / 结果 / 状态”，同一事项只出现一次。项目名只能出现在章节内容中，不能成为章节标题。没有依据的内容写“未提及”，仅输出符合 Schema 的 JSON。`,
  },
  {
    id: 'test-project-retrospective',
    name: '[测试] 项目复盘报告',
    version: '1.0.0',
    description: '五章节复盘报告，覆盖工作台支持的全部五种内容块。',
    sections: [
      { id: 'retrospective_summary', title: '复盘结论', block: 'paragraph' },
      { id: 'goal_results', title: '目标达成情况', block: 'status_cards' },
      { id: 'delivery_review', title: '关键交付复盘', block: 'project_table', columns: ['交付项', '目标', '实际结果', '偏差原因'] },
      { id: 'lessons_and_actions', title: '经验与改进行动', block: 'bullet_list' },
      { id: 'risks_and_follow_up', title: '遗留风险与跟进', block: 'callout' },
    ],
    terms: [
      { canonical: '里程碑', variants: ['里程杯', '里程牌'] },
      { canonical: 'UAT', variants: ['U A T', '优诶替'], caseSensitive: true },
    ],
    sample: `项目负责人：本次完全虚构的“灯塔演示项目”目标是完成核心流程 U A T，并在 8 月 25 日前交付验收说明。实际完成了主流程测试和说明初稿，但异常流程只验证了 70%。\n测试负责人：主流程里程杯按期完成；异常流程延期两天，原因是测试数据准备晚于计划。\n团队成员：做得好的地方是每日同步及时；需要改进的是风险直到验收前才集中暴露。后续由测试组补齐异常数据并在周五回归。\n项目负责人：遗留风险是异常流程仍可能影响验收，需要协调一名业务人员周四参加验证。`,
    instructions: `# 项目复盘报告

围绕目标、实际结果、偏差原因和改进行动整理复盘。不得把计划当结果，不得为了完整而编造目标或数据。

固定使用五个章节。目标达成情况使用状态卡片；关键交付复盘使用“交付项 / 目标 / 实际结果 / 偏差原因”表格；经验与行动必须可执行；遗留风险需说明对象、影响和跟进动作。项目名、团队名和负责人只能作为内容属性，不能成为章节标题。仅输出符合 Schema 的 JSON。`,
  },
  {
    id: 'test-customer-insights',
    name: '[测试] 客户访谈洞察',
    version: '1.0.0',
    description: '将访谈记录整理为证据、洞察、机会和后续验证计划。',
    sections: [
      { id: 'interview_conclusion', title: '访谈结论', block: 'paragraph' },
      { id: 'evidence_log', title: '关键证据', block: 'project_table', columns: ['观察', '原始证据', '置信度'] },
      { id: 'insight_cards', title: '用户洞察', block: 'status_cards' },
      { id: 'validation_plan', title: '验证计划', block: 'bullet_list' },
      { id: 'research_caveats', title: '研究限制', block: 'callout' },
    ],
    terms: [
      { canonical: 'NPS', variants: ['N P S', '恩披艾斯'], caseSensitive: true },
      { canonical: '用户旅程', variants: ['用户旅成', '用户里程'] },
    ],
    sample: `研究员：以下内容是完全虚构的访谈。受访者 A 每周使用两次演示工具，主要任务是整理客户反馈。她认为首次配置步骤太多，但批量导出很省时间。\n受访者 A：如果每次都要重新选择模板，我会觉得麻烦；希望系统能记住上次设置。我的恩披艾斯评分是 7 分。\n研究员：这只是一位受访者，暂时不能代表所有用户。下一步计划再访谈 5 位不同熟练度的用户，并验证“记住上次设置”是否能缩短用户旅成。`,
    instructions: `# 客户访谈洞察

把访谈逐字稿中的事实、原话含义和研究者判断分开。洞察必须能追溯到输入证据，单个受访者观点不能被写成所有用户的结论。

固定使用五个章节。关键证据表格为“观察 / 原始证据 / 置信度”；用户洞察使用状态卡片；验证计划写下一步需要验证的假设；研究限制说明样本、场景或信息缺口。客户名和受访者姓名只能出现在内容中，不得成为章节标题。仅输出符合 Schema 的 JSON。`,
  },
]

function baseDefinitions(tableColumns = undefined) {
  return {
    tone: { type: 'string', enum: ['neutral', 'info', 'success', 'warning', 'danger'] },
    summaryCard: {
      type: 'object', additionalProperties: false, required: ['label', 'value'],
      properties: {
        label: { type: 'string', minLength: 1, maxLength: 40 },
        value: { type: 'string', minLength: 1, maxLength: 240 },
        tone: { $ref: '#/$defs/tone' },
      },
    },
    paragraph: {
      type: 'object', additionalProperties: false, required: ['type', 'text'],
      properties: {
        type: { const: 'paragraph' },
        text: { type: 'string', minLength: 1, maxLength: 4000 },
      },
    },
    bulletList: {
      type: 'object', additionalProperties: false, required: ['type', 'items'],
      properties: {
        type: { const: 'bullet_list' },
        items: { type: 'array', minItems: 1, maxItems: 20, items: { type: 'string', minLength: 1, maxLength: 1000 } },
      },
    },
    projectTable: {
      type: 'object', additionalProperties: false, required: ['type', 'columns', 'rows'],
      properties: {
        type: { const: 'project_table' },
        columns: tableColumns
          ? { const: tableColumns }
          : { type: 'array', minItems: 1, maxItems: 8, items: { type: 'string', minLength: 1, maxLength: 80 } },
        rows: {
          type: 'array', minItems: 1, maxItems: 40,
          items: { type: 'array', minItems: 1, maxItems: 8, items: { type: 'string', minLength: 1, maxLength: 1200 } },
        },
      },
    },
    statusCards: {
      type: 'object', additionalProperties: false, required: ['type', 'cards'],
      properties: {
        type: { const: 'status_cards' },
        cards: {
          type: 'array', minItems: 1, maxItems: 8,
          items: {
            type: 'object', additionalProperties: false, required: ['title', 'status'],
            properties: {
              title: { type: 'string', minLength: 1, maxLength: 120 },
              status: { type: 'string', minLength: 1, maxLength: 80 },
              details: { type: 'array', maxItems: 10, items: { type: 'string', minLength: 1, maxLength: 800 } },
            },
          },
        },
      },
    },
    callout: {
      type: 'object', additionalProperties: false, required: ['type', 'text'],
      properties: {
        type: { const: 'callout' },
        title: { type: 'string', minLength: 1, maxLength: 120 },
        text: { type: 'string', minLength: 1, maxLength: 2000 },
        tone: { $ref: '#/$defs/tone' },
      },
    },
  }
}

const blockDefinitionNames = {
  paragraph: 'paragraph',
  bullet_list: 'bulletList',
  project_table: 'projectTable',
  status_cards: 'statusCards',
  callout: 'callout',
}

function reportSchema(skill) {
  const tableColumns = skill.sections.find((section) => section.columns)?.columns
  const definitions = baseDefinitions(tableColumns)
  let sectionsSchema

  if (skill.flexible) {
    definitions.genericSection = {
      type: 'object', additionalProperties: false, required: ['id', 'title', 'blocks'],
      properties: {
        id: { type: 'string', minLength: 1, maxLength: 120 },
        title: { type: 'string', minLength: 1, maxLength: 200 },
        blocks: {
          type: 'array', minItems: 1, maxItems: 8,
          items: {
            oneOf: Object.values(blockDefinitionNames).map((name) => ({ $ref: `#/$defs/${name}` })),
          },
        },
      },
    }
    sectionsSchema = {
      type: 'array', minItems: 1, maxItems: 8, items: { $ref: '#/$defs/genericSection' },
    }
  } else {
    skill.sections.forEach((section, index) => {
      definitions[`section${index + 1}`] = {
        type: 'object', additionalProperties: false, required: ['id', 'title', 'blocks'],
        properties: {
          id: { const: section.id },
          title: { const: section.title },
          blocks: {
            type: 'array', minItems: 1, maxItems: 1,
            prefixItems: [{ $ref: `#/$defs/${blockDefinitionNames[section.block]}` }],
            items: false,
          },
        },
      }
    })
    sectionsSchema = {
      type: 'array', minItems: skill.sections.length, maxItems: skill.sections.length,
      prefixItems: skill.sections.map((_, index) => ({ $ref: `#/$defs/section${index + 1}` })),
      items: false,
    }
  }

  return {
    $schema: 'https://json-schema.org/draft/2020-12/schema',
    $id: `https://report-skill-studio.local/schemas/${skill.id}/${skill.version}`,
    title: skill.name,
    type: 'object',
    additionalProperties: false,
    required: ['title', 'meeting_date', 'executive_summary', 'summary_cards', 'sections'],
    properties: {
      title: { type: 'string', minLength: 1, maxLength: 160 },
      meeting_date: { type: 'string', pattern: '^\\d{4}-\\d{2}-\\d{2}$' },
      executive_summary: { type: 'string', minLength: 1, maxLength: 1200 },
      summary_cards: {
        type: 'array', minItems: 1, maxItems: 4, items: { $ref: '#/$defs/summaryCard' },
      },
      sections: sectionsSchema,
    },
    $defs: definitions,
  }
}

function prompt(skill) {
  return `你正在生成“${skill.name}”的待确认草稿。\n\n仅输出符合给定 JSON Schema 的 JSON 对象，不要输出 Markdown、HTML、解释或 PDF 布局。所有事实必须来自输入；无法确认时明确写“未提及”或“需确认”。\n\n<report_date>\n{{report_date}}\n</report_date>\n\n<project_memory>\n{{project_memory}}\n</project_memory>\n\n<confirmed_terminology>\n{{confirmed_terminology}}\n</confirmed_terminology>\n\n<transcript>\n{{transcript}}\n</transcript>\n\n生成前检查章节、块类型、日期格式、术语、事实和状态是否满足 Schema 与写作规则。\n`
}

function terminologyYaml(skill) {
  const entries = skill.terms.map((term) => [
    `  - canonical: ${JSON.stringify(term.canonical)}`,
    `    variants: ${JSON.stringify(term.variants)}`,
    '    layer: fixed',
    '    confirmed: true',
    ...(term.caseSensitive ? ['    case_sensitive: true'] : []),
    '    note: 完全虚构的测试术语，仅用于验证纠错流程。',
  ].join('\n'))
  return `schema_version: "0.1"\nterms:\n${entries.join('\n')}\n`
}

function validationYaml(skill) {
  const requiredSections = skill.flexible
    ? 'required_sections: []'
    : `required_sections:\n${skill.sections.map((section) => `  - id: ${section.id}\n    title: ${JSON.stringify(section.title)}`).join('\n')}`
  return `schema_version: "0.1"\n${requiredSections}\nallow_additional_sections: ${skill.flexible ? 'true' : 'false'}\nforbidden_phrases: []\nterminology:\n  enabled: true\n  severity: warning\n  confirmed_only: true\n`
}

function manifest(skill) {
  return `schema_version: "0.1"\nid: ${skill.id}\nname: ${JSON.stringify(skill.name)}\nversion: ${skill.version}\ndescription: ${JSON.stringify(skill.description)}\nlocale: zh-CN\nfiles:\n  instructions: instructions.md\n  prompt: prompts/generate.md\n  report_schema: schemas/report.schema.json\n  terms: memory/default-terms.yaml\n  validation: validators/rules.yaml\n  templates:\n    html: templates/report.html\n    css: templates/report.css\n`
}

mkdirSync(outputRoot, { recursive: true })
for (const skill of skills) {
  const skillRoot = join(outputRoot, skill.id)
  const zipPath = join(outputRoot, `${skill.id}.zip`)
  rmSync(skillRoot, { recursive: true, force: true })
  rmSync(zipPath, { force: true })
  for (const directory of ['prompts', 'schemas', 'memory', 'validators', 'templates']) {
    mkdirSync(join(skillRoot, directory), { recursive: true })
  }
  writeFileSync(join(skillRoot, 'skill.yaml'), manifest(skill), 'utf8')
  writeFileSync(join(skillRoot, 'instructions.md'), `${skill.instructions}\n`, 'utf8')
  writeFileSync(join(skillRoot, 'prompts', 'generate.md'), prompt(skill), 'utf8')
  writeFileSync(join(skillRoot, 'schemas', 'report.schema.json'), `${JSON.stringify(reportSchema(skill), null, 2)}\n`, 'utf8')
  writeFileSync(join(skillRoot, 'memory', 'default-terms.yaml'), terminologyYaml(skill), 'utf8')
  writeFileSync(join(skillRoot, 'validators', 'rules.yaml'), validationYaml(skill), 'utf8')
  copyFileSync(join(templateRoot, 'report.html'), join(skillRoot, 'templates', 'report.html'))
  copyFileSync(join(templateRoot, 'report.css'), join(skillRoot, 'templates', 'report.css'))

  const zipped = spawnSync('/usr/bin/zip', ['-q', '-r', `${skill.id}.zip`, skill.id], {
    cwd: outputRoot,
    encoding: 'utf8',
  })
  if (zipped.status !== 0) {
    throw new Error(`无法打包 ${skill.id}: ${zipped.stderr || zipped.stdout}`)
  }
}

const readme = `测试 Skill 包\n\n1. test-smoke-report.zip：先用它验证安装和完整流程；兼容本地 mock 模型。\n2. test-brief-update.zip：三章节极简工作简报。\n3. test-project-retrospective.zip：五章节项目复盘，覆盖全部五种块。\n4. test-customer-insights.zip：五章节客户访谈洞察。\n\n全部内容和术语均为虚构测试数据。请在工作台“管理与安装 Skill”中逐个上传 ZIP。固定结构的后三个 Skill 建议使用已配置的云端写作模型；本地 mock 模型只保证兼容第一个冒烟 Skill。\n`
writeFileSync(join(outputRoot, '使用说明.txt'), readme, 'utf8')
for (const skill of skills) {
  writeFileSync(join(outputRoot, `示例逐字稿-${skill.id}.txt`), `${skill.sample}\n`, 'utf8')
}

console.log(`已生成 ${skills.length} 个测试 Skill：${outputRoot}`)

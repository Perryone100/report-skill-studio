你正在为本地周报工作台生成一份“待用户确认”的结构化周会纪要。

请遵守写作规则，并仅输出符合给定 JSON Schema 的 JSON 对象。不要输出 Markdown 代码块，不要解释生成过程，不要生成 HTML 或 PDF 布局。

<report_date>
{{report_date}}
</report_date>

<project_memory>
{{project_memory}}
</project_memory>

<confirmed_terminology>
{{confirmed_terminology}}
</confirmed_terminology>

<transcript>
{{transcript}}
</transcript>

生成前请在内部检查：

1. 事实是否来自逐字稿或项目记忆；
2. 状态、风险和下周动作是否被正确区分；
3. 所有已确认术语是否采用标准写法；
4. 必填章节是否齐全；
5. 是否只使用四个固定章节，且没有把项目名、产品名、客户名、部门名或负责人姓名写成章节标题；
6. “本周工作进展”是否只有一个四列表格，同一工作项是否已经合并；
7. 是否把内容来源、汇报口径或输出形式写成页面标签；业务事实中的“AI 生成”不得因此被删除；
8. 是否包含无信息量的套话。

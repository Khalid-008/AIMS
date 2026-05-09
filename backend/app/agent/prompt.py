REPORT_CONTEXT_SECTION_EN = """\

--- REPORT CONTEXT (the user is viewing this report on the same page) ---
{report_context}
--- END REPORT CONTEXT ---

CONTEXT USAGE RULES:
- If the user's question can be answered from the REPORT CONTEXT above, answer directly from it WITHOUT calling any tool.
- If the question requires data NOT present in the report context (e.g., raw submission details, different date ranges, specific respondent data, cross-tabulations not shown), then call the appropriate tool to fetch it.
- When referencing report data, you can say things like "As shown in your report..." to make the connection clear.
"""

SYSTEM_EN = """\
You are a survey analytics assistant. You have been given access to survey data tools \
scoped exclusively to survey {survey_number}.

Rules you MUST follow:
- You may ONLY call tools that are provided to you.
- Every tool call MUST use the pre-bound survey scope. Never attempt to access another survey.
- If the user asks about a different survey, politely refuse and explain you are scoped to {survey_number}.
- For any factual or data question about this survey (counts, percentages, answers, options, timelines, keywords), you MUST call the appropriate tool first. Never invent numbers or answers.
- Answer in the same language the user used (English in this case).
- Be concise but informative. Include numbers where relevant.
- If a tool returns an error, tell the user clearly.
{report_context_block}"""

REPORT_CONTEXT_SECTION_AR = """\

--- سياق التقرير (المستخدم يشاهد هذا التقرير في نفس الصفحة) ---
{report_context}
--- نهاية سياق التقرير ---

قواعد استخدام السياق:
- إذا كان سؤال المستخدم يمكن الإجابة عليه من سياق التقرير أعلاه، فأجب مباشرة منه دون استدعاء أي أداة.
- إذا كان السؤال يتطلب بيانات غير موجودة في سياق التقرير (مثل تفاصيل إرسالات خام، نطاقات زمنية مختلفة، بيانات مستجيبين محددين)، فاستدعي الأداة المناسبة لجلبها.
- عند الإشارة إلى بيانات التقرير، يمكنك قول أشياء مثل "كما هو موضح في تقريرك..." لجعل الربط واضحًا.
"""

SYSTEM_AR = """\
أنت مساعد تحليل استبيانات. لديك أدوات وصول إلى بيانات مقيّدة حصريًا بالاستبيان {survey_number}.

قواعد يجب الالتزام بها:
- يمكنك فقط استخدام الأدوات المتاحة لك.
- جميع الأدوات مرتبطة مسبقًا بنطاق الاستبيان الصحيح. لا تحاول الوصول إلى استبيان آخر.
- إذا طلب المستخدم معلومات عن استبيان آخر، ارفض بلطف واشرح أنك مقيّد بالاستبيان {survey_number}.
- لأي سؤال واقعي أو متعلق بالبيانات عن هذا الاستبيان (عدد، نسب مئوية، إجابات، خيارات، جداول زمنية، كلمات مفتاحية) يجب أن تستدعي الأداة المناسبة أولاً. لا تخترع أرقامًا أو إجابات.
- أجب دائمًا بالعربية.
- كن موجزًا لكنك مفيدًا. اذكر الأرقام عند الضرورة.
- إذا أعادت أداة ما خطأً، أخبر المستخدم بوضوح.
{report_context_block}"""


def _serialize_report_context(report_context: dict | None) -> str:
    """Serialize report payload into a concise text block for the system prompt."""
    if not report_context:
        return ""

    parts: list[str] = []

    # Executive summary
    synthesis = report_context.get("synthesis") or {}
    if synthesis.get("executive_summary"):
        parts.append(f"Executive Summary:\n{synthesis['executive_summary']}")

    # Key metrics
    if synthesis.get("key_metrics"):
        metrics = synthesis["key_metrics"]
        if isinstance(metrics, list):
            lines = [f"  - {m}" for m in metrics if m]
            if lines:
                parts.append(f"Key Metrics:\n{''.join(lines)}")
        elif isinstance(metrics, str):
            parts.append(f"Key Metrics:\n{metrics}")

    # Detailed analysis
    if synthesis.get("detailed_analysis"):
        parts.append(f"Detailed Analysis:\n{synthesis['detailed_analysis']}")

    # Recommendations
    if synthesis.get("recommendations"):
        recs = synthesis["recommendations"]
        if isinstance(recs, list):
            lines = [f"  - {r}" for r in recs if r]
            if lines:
                parts.append(f"Recommendations:\n{''.join(lines)}")
        elif isinstance(recs, str):
            parts.append(f"Recommendations:\n{recs}")

    _sep = "---\n"

    # Per-question SQL data
    sql_questions = report_context.get("sql") or []
    if sql_questions:
        sql_parts = []
        for q in sql_questions:
            qid = q.get("question_id", "?")
            qtext = q.get("question_text", "")
            analysis = q.get("analysis", "")
            sql_parts.append(f"Q{qid}: {qtext}\n{analysis}")
        if sql_parts:
            parts.append(f"SQL Question Analysis:\n{_sep.join(sql_parts)}")

    # Per-question NLP data
    nlp_questions = report_context.get("nlp") or []
    if nlp_questions:
        nlp_parts = []
        for q in nlp_questions:
            qid = q.get("question_id", "?")
            qtext = q.get("question_text", "")
            clusters = q.get("clusters", [])
            summary = q.get("summary", "")
            cluster_lines = []
            for c in clusters:
                label = c.get("label", "")
                count = c.get("count", "")
                cluster_lines.append(f"  - {label} ({count} responses)")
            nlp_parts.append(f"Q{qid}: {qtext}\n{''.join(cluster_lines)}\n{summary}")
        if nlp_parts:
            parts.append(f"NLP Question Analysis:\n{_sep.join(nlp_parts)}")

    # Meta info
    if report_context.get("submissions_limit"):
        parts.append(f"Submissions Limit: {report_context['submissions_limit']}")

    date_from = report_context.get("date_from", "")
    date_to = report_context.get("date_to", "")
    if date_from or date_to:
        parts.append(f"Date Range: {date_from or '...'} to {date_to or '...'}")

    return "\n\n".join(parts)


def build_system_prompt(
    survey_number: str,
    language: str,
    report_context: dict | None = None,
) -> str:
    serialized = _serialize_report_context(report_context)

    if language == "ar":
        template = SYSTEM_AR
        if serialized:
            context_block = REPORT_CONTEXT_SECTION_AR.format(report_context=serialized)
        else:
            context_block = ""
    else:
        template = SYSTEM_EN
        if serialized:
            context_block = REPORT_CONTEXT_SECTION_EN.format(report_context=serialized)
        else:
            context_block = ""

    return template.format(
        survey_number=survey_number,
        report_context_block=context_block,
    )

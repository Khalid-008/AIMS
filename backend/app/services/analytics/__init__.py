"""Survey analytics report pipeline (backend-only).

Pipeline: analysis (per-answer LLM) -> clustering (cross-lingual cluster) ->
aggregation (pure-Python aggregate) -> summarization (per-question narrative LLM) ->
synthesis (final report-level LLM). SQL branch runs in parallel.
"""

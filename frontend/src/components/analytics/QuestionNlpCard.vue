<template>
  <article class="nlp-card">
    <header class="nlp-head">
      <span class="q-type-badge">TEXT</span>
      <h3 class="q-title">{{ q.question_text }}</h3>
      <div class="chips">
        <span class="chip">
          {{ language === 'ar' ? 'إجابات صالحة' : 'Valid' }}: {{ q.valid_count }}
        </span>
        <span v-if="q.sarcastic_count > 0" class="chip chip-warn">
          {{ language === 'ar' ? 'تهكمية' : 'Sarcastic' }}: {{ q.sarcastic_count }}
        </span>
        <span v-if="q.partial" class="chip chip-warn">
          {{ language === 'ar' ? 'جزئي' : 'Partial' }}
        </span>
      </div>
    </header>

    <div class="nlp-body">
      <div class="nlp-col col-sentiment">
        <h4 class="block-title">{{ language === 'ar' ? 'توزيع المشاعر' : 'Sentiment' }}</h4>
        <SentimentDonut :distribution="q.sentiment_distribution" :language="language" />
      </div>

      <div class="nlp-col col-topics">
        <h4 class="block-title">
          {{ language === 'ar' ? 'أبرز المواضيع' : 'Top Topics' }}
          <span class="cap-hint">({{ q.top_topics.length }})</span>
        </h4>
        <TopTopicsBar :topics="q.top_topics" :language="language" />
      </div>
    </div>

    <div v-if="q.top_entities.length" class="entities-block">
      <h4 class="block-title">{{ language === 'ar' ? 'الكيانات البارزة' : 'Top Entities' }}</h4>
      <div class="entity-pills">
        <span v-for="(e, i) in q.top_entities" :key="i" class="entity-pill">
          <span class="entity-name">{{ e.name }}</span>
          <span class="entity-type">{{ e.type }}</span>
          <span class="entity-count">{{ e.count }}</span>
        </span>
      </div>
    </div>

    <div v-if="q.narrative_summary" class="narrative-block">
      <h4 class="block-title">{{ language === 'ar' ? 'الملخص السردي' : 'Narrative Summary' }}</h4>
      <p class="narrative-text">{{ q.narrative_summary }}</p>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { QuestionNlpResult } from '@/api/client'
import SentimentDonut from './SentimentDonut.vue'
import TopTopicsBar from './TopTopicsBar.vue'

defineProps<{
  q: QuestionNlpResult
  language?: 'en' | 'ar'
}>()
</script>

<style scoped>
.nlp-card {
  background: #fff;
  border: 1px solid #e0e4f0;
  border-radius: 12px;
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  box-shadow: 0 1px 6px rgba(15, 23, 42, 0.04);
}
.nlp-head { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.q-type-badge {
  font-size: 0.68rem;
  font-weight: 700;
  background: #ddd6fe;
  color: #5b21b6;
  padding: 3px 10px;
  border-radius: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.q-title { flex: 1; font-size: 1rem; font-weight: 600; color: #1a1a2e; line-height: 1.4; margin: 0; min-width: 200px; }

.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip {
  font-size: 0.72rem;
  background: #eef2ff;
  color: #3730a3;
  padding: 3px 10px;
  border-radius: 10px;
  font-weight: 500;
}
.chip-warn { background: #fef3c7; color: #92400e; }

.nlp-body {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) 2fr;
  gap: 22px;
  align-items: start;
}
@media (max-width: 720px) {
  .nlp-body { grid-template-columns: 1fr; }
}

.nlp-col { display: flex; flex-direction: column; gap: 8px; }

.block-title {
  font-size: 0.78rem;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}
.cap-hint { font-weight: 500; color: #94a3b8; text-transform: none; letter-spacing: 0; }

.entities-block { display: flex; flex-direction: column; gap: 8px; }
.entity-pills { display: flex; flex-wrap: wrap; gap: 8px; }
.entity-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.8rem;
}
.entity-name { font-weight: 500; color: #1a1a2e; }
.entity-type { font-size: 0.68rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em; }
.entity-count { color: #4361ee; font-weight: 600; font-variant-numeric: tabular-nums; }

.narrative-block {
  background: #f8fafc;
  border-left: 3px solid #4361ee;
  padding: 12px 16px;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
[dir="rtl"] .narrative-block { border-left: none; border-right: 3px solid #4361ee; }
.narrative-text {
  font-size: 0.92rem;
  line-height: 1.65;
  color: #1a1a2e;
  margin: 0;
  white-space: pre-wrap;
}
</style>

<template>
  <div class="topics-list" :dir="language === 'ar' ? 'rtl' : 'ltr'">
    <div v-for="(t, i) in sorted" :key="i" class="topic-row">
      <div class="topic-meta">
        <span class="topic-subtopic">{{ t.subtopic }}</span>
        <span class="topic-category">{{ t.category }}</span>
      </div>
      <div class="bar-track">
        <div
          class="bar-fill"
          :style="{ width: percentOf(t.count) + '%', background: sentimentColor(t.dominant_sentiment) }"
        />
      </div>
      <span class="topic-count">{{ t.count }}</span>
    </div>
    <p v-if="!sorted.length" class="empty">
      {{ language === 'ar' ? 'لا توجد مواضيع' : 'No topics' }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TopTopic, Sentiment } from '@/api/client'

const props = defineProps<{
  topics: TopTopic[]
  language?: 'en' | 'ar'
}>()

const SENTIMENT_COLORS: Record<Sentiment, string> = {
  positive: '#06d6a0',
  neutral: '#94a3b8',
  negative: '#ef476f',
  mixed: '#f59e0b',
}

function sentimentColor(s: Sentiment): string {
  return SENTIMENT_COLORS[s] ?? '#94a3b8'
}

const sorted = computed(() => [...props.topics].sort((a, b) => b.count - a.count))

const maxCount = computed(() => sorted.value.reduce((m, t) => Math.max(m, t.count), 0) || 1)

function percentOf(n: number): number {
  return Math.round((n / maxCount.value) * 100)
}
</script>

<style scoped>
.topics-list { display: flex; flex-direction: column; gap: 8px; }
.topic-row { display: grid; grid-template-columns: minmax(140px, 30%) 1fr 50px; gap: 12px; align-items: center; }
.topic-meta { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.topic-subtopic { font-weight: 500; font-size: 0.88rem; color: #1a1a2e; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.topic-category {
  font-size: 0.7rem;
  color: #6366f1;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.bar-track { height: 14px; background: #eef0fa; border-radius: 7px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 7px; transition: width 0.4s ease; }
.topic-count { font-variant-numeric: tabular-nums; font-size: 0.85rem; color: #475569; text-align: end; }
.empty { color: #94a3b8; font-size: 0.85rem; text-align: center; padding: 14px; margin: 0; }
</style>

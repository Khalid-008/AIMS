<template>
  <section class="progress-card">
    <header class="progress-head">
      <div class="spinner" />
      <div>
        <h2 class="progress-title">
          {{ language === 'ar' ? 'جاري إنشاء التقرير…' : 'Generating report…' }}
        </h2>
        <p class="progress-sub">
          {{ language === 'ar'
            ? 'قد تستغرق هذه العملية بضع دقائق بحسب حجم البيانات.'
            : 'This may take a few minutes depending on data volume.' }}
        </p>
      </div>
    </header>

    <ol class="step-list">
      <li
        v-for="step in steps"
        :key="step.key"
        class="step"
        :class="{ done: step.status === 'done', active: step.status === 'active', pending: step.status === 'pending' }"
      >
        <span class="step-icon">
          <span v-if="step.status === 'done'">✓</span>
          <span v-else-if="step.status === 'active'" class="step-spinner" />
          <span v-else>•</span>
        </span>
        <div class="step-body">
          <div class="step-title">{{ stepLabel(step.key) }}</div>
          <div v-if="step.detail" class="step-detail">{{ step.detail }}</div>
          <div v-if="step.progress !== undefined && step.progress !== null" class="step-bar">
            <div class="step-bar-fill" :style="{ width: step.progress + '%' }" />
          </div>
        </div>
      </li>
    </ol>

    <p v-if="trimmedNotice" class="trim-notice">
      {{ language === 'ar'
        ? 'تم تقليص حجم المدخلات لتناسب حدود الرموز.'
        : 'Input was trimmed to fit the token budget.' }}
    </p>
  </section>
</template>

<script setup lang="ts">
import type { ProgressStep } from './progressTypes'

const props = defineProps<{
  steps: ProgressStep[]
  trimmedNotice?: boolean
  language?: 'en' | 'ar'
}>()

const LABELS_EN: Record<string, string> = {
  analysis: 'Per-answer analysis',
  clustering: 'Topic clustering',
  aggregation: 'Aggregation',
  summarization: 'Per-question summaries',
  synthesis: 'Executive synthesis',
  sql: 'SQL aggregations',
}
const LABELS_AR: Record<string, string> = {
  analysis: 'تحليل الإجابات',
  clustering: 'تجميع المواضيع',
  aggregation: 'التجميع',
  summarization: 'ملخصات الأسئلة',
  synthesis: 'التركيب التنفيذي',
  sql: 'التجميعات الإحصائية',
}

function stepLabel(key: string): string {
  return (props.language === 'ar' ? LABELS_AR : LABELS_EN)[key] ?? key
}
</script>

<style scoped>
.progress-card {
  background: #fff;
  border: 1px solid #e0e4f0;
  border-radius: 14px;
  padding: 28px 32px;
  display: flex;
  flex-direction: column;
  gap: 22px;
  box-shadow: 0 2px 14px rgba(15, 23, 42, 0.05);
}
.progress-head { display: flex; align-items: center; gap: 16px; }
.progress-title { font-size: 1.1rem; margin: 0 0 4px 0; color: #1a1a2e; }
.progress-sub { margin: 0; color: #6b7280; font-size: 0.85rem; }

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #eef0fa;
  border-top-color: #4361ee;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

.step-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.step {
  display: flex;
  gap: 14px;
  padding: 10px 14px;
  border-radius: 8px;
  background: #f8fafc;
  transition: background 0.2s;
}
.step.done { background: #ecfdf5; }
.step.active { background: #eef2ff; }
.step.pending { opacity: 0.65; }

.step-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 0.85rem;
  font-weight: 700;
}
.step.done .step-icon { background: #06d6a0; color: #fff; }
.step.active .step-icon { background: #4361ee; color: #fff; }
.step.pending .step-icon { background: #e2e8f0; color: #94a3b8; }

.step-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.step-body { flex: 1; min-width: 0; }
.step-title { font-size: 0.92rem; font-weight: 600; color: #1a1a2e; }
.step-detail { font-size: 0.78rem; color: #6b7280; margin-top: 2px; }

.step-bar {
  margin-top: 6px;
  height: 6px;
  background: rgba(255,255,255,0.6);
  border-radius: 3px;
  overflow: hidden;
}
.step-bar-fill { height: 100%; background: #4361ee; transition: width 0.3s ease; }

.trim-notice {
  margin: 0;
  font-size: 0.8rem;
  color: #92400e;
  background: #fef3c7;
  border-radius: 8px;
  padding: 8px 12px;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>

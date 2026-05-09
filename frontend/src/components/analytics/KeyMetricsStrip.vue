<template>
  <section class="metrics-section">
    <h2 class="section-title">
      <span class="title-bar" />
      {{ language === 'ar' ? 'المؤشرات الرئيسية' : 'Key Metrics' }}
    </h2>
    <div class="metrics-grid">
      <div v-for="(m, i) in metrics" :key="i" class="metric-card" :class="`accent-${i % 4}`">
        <div class="metric-value">{{ m.value }}</div>
        <div class="metric-label">{{ m.label }}</div>
        <div v-if="m.context" class="metric-context">{{ m.context }}</div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { KeyMetric } from '@/api/client'

defineProps<{
  metrics: KeyMetric[]
  language?: 'en' | 'ar'
}>()
</script>

<style scoped>
.metrics-section { display: flex; flex-direction: column; gap: 14px; }
.section-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 1rem;
  font-weight: 700;
  color: #1a1a2e;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0;
}
.title-bar { width: 4px; height: 18px; background: #4361ee; border-radius: 2px; }

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
}

.metric-card {
  position: relative;
  background: #fff;
  border: 1px solid #e0e4f0;
  border-radius: 12px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  box-shadow: 0 1px 6px rgba(15, 23, 42, 0.04);
  transition: transform 0.2s, box-shadow 0.2s;
}
.metric-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  border-radius: 12px 0 0 12px;
}
[dir="rtl"] .metric-card::before { left: auto; right: 0; border-radius: 0 12px 12px 0; }
.metric-card:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08); }

.metric-card.accent-0::before { background: #4361ee; }
.metric-card.accent-1::before { background: #06d6a0; }
.metric-card.accent-2::before { background: #f59e0b; }
.metric-card.accent-3::before { background: #7209b7; }

.metric-value {
  font-size: 1.7rem;
  font-weight: 700;
  color: #1a1a2e;
  line-height: 1.1;
}
.metric-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #475569;
}
.metric-context {
  font-size: 0.78rem;
  color: #6b7280;
  line-height: 1.4;
}
</style>

<template>
  <section class="recs-section">
    <h2 class="section-title">
      <span class="title-bar" />
      {{ language === 'ar' ? 'التوصيات' : 'Recommendations' }}
    </h2>
    <ol class="recs-list">
      <li v-for="(r, i) in items" :key="i" class="rec-item">
        <span class="rec-number">{{ i + 1 }}</span>
        <span class="rec-text">{{ r }}</span>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  items: string[]
  language?: 'en' | 'ar'
}>()
</script>

<style scoped>
.recs-section { display: flex; flex-direction: column; gap: 14px; }
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

.recs-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rec-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 18px;
  background: #fff;
  border: 1px solid #e0e4f0;
  border-radius: 10px;
  transition: transform 0.2s, box-shadow 0.2s;
}
.rec-item:hover { transform: translateX(4px); box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06); }
[dir="rtl"] .rec-item:hover { transform: translateX(-4px); }

.rec-number {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  background: #4361ee;
  color: #fff;
  font-size: 0.85rem;
  font-weight: 700;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.rec-text { font-size: 0.95rem; line-height: 1.6; color: #1a1a2e; }
</style>

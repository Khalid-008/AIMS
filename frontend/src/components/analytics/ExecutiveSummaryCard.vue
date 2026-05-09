<template>
  <section class="exec-card">
    <h2 class="section-title">
      <span class="title-bar" />
      {{ language === 'ar' ? 'الملخص التنفيذي' : 'Executive Summary' }}
    </h2>
    <p class="exec-text">{{ text }}</p>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  text: string
  language?: 'en' | 'ar'
}>()
</script>

<style scoped>
.exec-card {
  background: linear-gradient(135deg, #f8f9ff 0%, #fff 100%);
  border: 1px solid #e0e4f0;
  border-radius: 14px;
  padding: 28px 32px;
  box-shadow: 0 2px 14px rgba(15, 23, 42, 0.05);
}
.section-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 1rem;
  font-weight: 700;
  color: #1a1a2e;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0 0 14px 0;
}
.title-bar { width: 4px; height: 18px; background: #4361ee; border-radius: 2px; }

.exec-text {
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 1.15rem;
  line-height: 1.7;
  color: #1a1a2e;
  margin: 0;
  white-space: pre-wrap;
}
</style>

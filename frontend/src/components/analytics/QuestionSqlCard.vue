<template>
  <article class="sql-card">
    <header class="sql-head">
      <span class="q-type-badge">{{ q.type }}</span>
      <h3 class="q-title">{{ q.question_text }}</h3>
      <span v-if="totalLabel" class="chip">{{ totalLabel }}</span>
    </header>

    <div class="sql-body">
      <p v-if="errorMessage" class="error-msg">{{ errorMessage }}</p>

      <template v-else-if="q.type === 'MULTIPLE_CHOICE'">
        <PieChart
          v-if="choiceLabels.length <= 4"
          :labels="choiceLabels"
          :values="choiceValues"
        />
        <BarChart v-else :labels="choiceLabels" :values="choiceValues" :language="language" />
      </template>

      <BarChart
        v-else-if="q.type === 'DROPDOWN'"
        :labels="dropdownLabels"
        :values="dropdownValues"
        :language="language"
      />

      <DoughnutChart
        v-else-if="q.type === 'YES_NO'"
        :yes="(q.results.yes as number) ?? 0"
        :no="(q.results.no as number) ?? 0"
        :yes-percent="(q.results.yesPercent as number) ?? 0"
        :no-percent="(q.results.noPercent as number) ?? 0"
        :language="language"
      />

      <EmojiHistogram
        v-else-if="q.type === 'EMOJIS'"
        :data="emojiData"
      />
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { QuestionSqlResult } from '@/api/client'
import BarChart from '../charts/BarChart.vue'
import PieChart from '../charts/PieChart.vue'
import DoughnutChart from '../charts/DoughnutChart.vue'
import EmojiHistogram from '../charts/EmojiHistogram.vue'

const props = defineProps<{
  q: QuestionSqlResult
  language?: 'en' | 'ar'
}>()

interface McOption { optionId: number; labelEn: string; labelAr: string; count: number; percent: number; submissionPercent: number }
interface DropdownOption { label: string; count: number; percent: number }
interface EmojiOption { emoji: string; count: number; percent: number }

const errorMessage = computed(() => (props.q.results?.error as string) || '')

const mcOptions = computed<McOption[]>(() => (props.q.results?.options as McOption[]) ?? [])
const choiceLabels = computed(() => mcOptions.value.map((o) =>
  props.language === 'ar' ? (o.labelAr || o.labelEn) : (o.labelEn || o.labelAr)
))
const choiceValues = computed(() => mcOptions.value.map((o) => o.count))

const dropdownOptions = computed<DropdownOption[]>(() => (props.q.results?.options as DropdownOption[]) ?? [])
const dropdownLabels = computed(() => dropdownOptions.value.map((o) => o.label))
const dropdownValues = computed(() => dropdownOptions.value.map((o) => o.count))

const emojiData = computed<EmojiOption[]>(() => (props.q.results?.options as EmojiOption[]) ?? [])

const totalLabel = computed(() => {
  const r = props.q.results
  if (!r) return ''
  if (props.q.type === 'YES_NO' || props.q.type === 'DROPDOWN') {
    const total = r.total as number | undefined
    if (typeof total !== 'number') return ''
    return props.language === 'ar' ? `الإجمالي: ${total}` : `Total: ${total}`
  }
  if (props.q.type === 'MULTIPLE_CHOICE') {
    const subs = r.distinctSubmissions as number | undefined
    if (typeof subs !== 'number') return ''
    return props.language === 'ar' ? `إرسالات: ${subs}` : `Submissions: ${subs}`
  }
  return ''
})
</script>

<style scoped>
.sql-card {
  background: #fff;
  border: 1px solid #e0e4f0;
  border-radius: 12px;
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  box-shadow: 0 1px 6px rgba(15, 23, 42, 0.04);
}
.sql-head { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.q-type-badge {
  font-size: 0.68rem;
  font-weight: 700;
  background: #e0e7ff;
  color: #3730a3;
  padding: 3px 10px;
  border-radius: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.q-title { flex: 1; font-size: 1rem; font-weight: 600; color: #1a1a2e; line-height: 1.4; margin: 0; min-width: 200px; }
.chip {
  font-size: 0.72rem;
  background: #eef2ff;
  color: #3730a3;
  padding: 3px 10px;
  border-radius: 10px;
  font-weight: 500;
}

.sql-body { min-height: 200px; }

.error-msg {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 0.85rem;
}
</style>

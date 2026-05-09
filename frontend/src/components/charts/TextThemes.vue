<template>
  <div class="text-themes">
    <template v-if="wordData.length">
      <!-- Arabic text: horizontal bar (canvas word-cloud has unreliable RTL shaping) -->
      <v-chart v-if="isArabic" :option="barOption" autoresize style="height: 220px" />
      <!-- Other languages: ECharts word cloud -->
      <v-chart v-else :option="cloudOption" autoresize style="height: 220px" />
    </template>
    <div v-else class="empty">
      {{ language === 'ar' ? 'لا توجد كلمات مفتاحية' : 'No keywords found' }}
    </div>
    <p class="total">
      {{ language === 'ar' ? 'إجمالي الإجابات:' : 'Total answers:' }}
      <strong>{{ data.totalAnswers ?? 0 }}</strong>
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart as EBarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import 'echarts-wordcloud'

use([CanvasRenderer, EBarChart, GridComponent, TooltipComponent])

interface TokenItem { token: string; count: number }
interface TextData { topTokens?: TokenItem[]; totalAnswers?: number }

const props = defineProps<{ data: TextData; language?: 'en' | 'ar' }>()

const PALETTE = [
  '#4361ee', '#7209b7', '#f72585', '#ef476f', '#118ab2',
  '#06d6a0', '#ffd166', '#3a0ca3', '#4cc9f0', '#073b4c',
]

const wordData = computed(() =>
  [...(props.data.topTokens ?? [])]
    .sort((a, b) => b.count - a.count)
    .map((t, i) => ({ name: t.token, value: t.count, textStyle: { color: PALETTE[i % PALETTE.length] } }))
)

// Detect Arabic content by checking for Arabic Unicode block characters
const isArabic = computed(() =>
  wordData.value.some((w) => /[؀-ۿ]/.test(w.name))
)

// Horizontal bar chart for Arabic keywords
const barOption = computed(() => {
  const items = wordData.value.slice(0, 15)
  const reversed = [...items].reverse()
  return {
    tooltip: { trigger: 'axis' },
    grid: { containLabel: true, left: 8, right: 32, top: 8, bottom: 8 },
    xAxis: { type: 'value', minInterval: 1 },
    yAxis: {
      type: 'category',
      data: reversed.map((w) => w.name),
      axisLabel: { fontFamily: 'Tahoma, Arial, sans-serif', fontSize: 12 },
    },
    series: [{
      type: 'bar',
      data: reversed.map((w, i) => ({
        value: w.value,
        itemStyle: { color: PALETTE[(items.length - 1 - i) % PALETTE.length] },
      })),
      label: { show: true, position: 'right', fontSize: 11 },
    }],
  }
})

// Word cloud for non-Arabic
const cloudOption = computed((): any => ({
  tooltip: { show: true },
  series: [{
    type: 'wordCloud',
    shape: 'circle',
    sizeRange: [14, 52],
    rotationRange: [0, 0],
    gridSize: 10,
    drawOutOfBound: false,
    textStyle: { fontFamily: 'Arial, sans-serif' },
    data: wordData.value,
  }],
}))
</script>

<style scoped>
.text-themes { display: flex; flex-direction: column; gap: 10px; }
.total { font-size: 0.8rem; color: #888; }
.empty { color: #aaa; font-size: 0.875rem; text-align: center; padding: 20px; }
</style>

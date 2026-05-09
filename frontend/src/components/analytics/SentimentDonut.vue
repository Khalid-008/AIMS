<template>
  <v-chart :option="option" autoresize style="height: 200px" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { PieChart as EPieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([CanvasRenderer, EPieChart, TooltipComponent, LegendComponent])

const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#06d6a0',
  neutral: '#94a3b8',
  negative: '#ef476f',
  mixed: '#f59e0b',
}

const LABELS_EN: Record<string, string> = {
  positive: 'Positive',
  neutral: 'Neutral',
  negative: 'Negative',
  mixed: 'Mixed',
}
const LABELS_AR: Record<string, string> = {
  positive: 'إيجابي',
  neutral: 'محايد',
  negative: 'سلبي',
  mixed: 'مختلط',
}

const props = defineProps<{
  distribution: Record<string, number>
  language?: 'en' | 'ar'
}>()

const option = computed(() => {
  const labelMap = props.language === 'ar' ? LABELS_AR : LABELS_EN
  const order = ['positive', 'neutral', 'negative', 'mixed']
  const data = order
    .filter((k) => (props.distribution[k] ?? 0) > 0)
    .map((k) => ({
      name: labelMap[k],
      value: props.distribution[k],
      itemStyle: { color: SENTIMENT_COLORS[k] },
    }))
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['52%', '74%'],
      center: ['50%', '44%'],
      data,
      label: { formatter: '{d}%', fontSize: 11 },
    }],
  }
})
</script>

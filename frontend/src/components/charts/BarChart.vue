<template>
  <v-chart :option="option" autoresize style="height: 240px" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart as EBarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([CanvasRenderer, EBarChart, GridComponent, TooltipComponent])

const COLORS = [
  '#4361ee', '#3a0ca3', '#7209b7', '#f72585', '#4cc9f0',
  '#06d6a0', '#ffd166', '#ef476f', '#118ab2', '#073b4c',
]

const props = defineProps<{
  labels: string[]
  values: number[]
  language?: 'en' | 'ar'
}>()

const option = computed(() => {
  const horizontal = props.labels.length > 5
  const coloredData = props.values.map((v, i) => ({
    value: v,
    itemStyle: { color: COLORS[i % COLORS.length] },
  }))
  return {
    tooltip: { trigger: 'axis' },
    grid: { containLabel: true, left: 8, right: 16, top: 8, bottom: 8 },
    xAxis: horizontal
      ? { type: 'value' }
      : { type: 'category', data: props.labels, axisLabel: { rotate: props.labels.length > 4 ? 15 : 0 } },
    yAxis: horizontal
      ? { type: 'category', data: props.labels }
      : { type: 'value' },
    series: [{
      type: 'bar',
      data: coloredData,
      label: { show: true, position: horizontal ? 'right' : 'top', fontSize: 11 },
    }],
  }
})
</script>

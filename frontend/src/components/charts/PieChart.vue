<template>
  <v-chart :option="option" autoresize style="height: 240px" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { PieChart as EPieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([CanvasRenderer, EPieChart, TooltipComponent, LegendComponent])

const COLORS = ['#4361ee', '#7209b7', '#f72585', '#4cc9f0', '#06d6a0', '#ffd166', '#ef476f']

const props = defineProps<{
  labels: string[]
  values: number[]
}>()

const option = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0, type: 'scroll', textStyle: { fontSize: 11 } },
  series: [{
    type: 'pie',
    radius: ['0%', '62%'],
    center: ['50%', '44%'],
    data: props.labels.map((l, i) => ({
      name: l,
      value: props.values[i],
      itemStyle: { color: COLORS[i % COLORS.length] },
    })),
    label: { show: false },
    emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.4)' } },
  }],
}))
</script>

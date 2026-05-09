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

const props = defineProps<{
  yes: number
  no: number
  yesPercent: number
  noPercent: number
  language?: 'en' | 'ar'
}>()

const option = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0, textStyle: { fontSize: 11 } },
  series: [{
    type: 'pie',
    radius: ['50%', '72%'],
    center: ['50%', '44%'],
    data: [
      { name: props.language === 'ar' ? 'نعم' : 'Yes', value: props.yes, itemStyle: { color: '#06d6a0' } },
      { name: props.language === 'ar' ? 'لا' : 'No', value: props.no, itemStyle: { color: '#ef476f' } },
    ],
    label: { formatter: '{b}: {d}%', fontSize: 11 },
  }],
}))
</script>

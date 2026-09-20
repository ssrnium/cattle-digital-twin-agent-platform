<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{ values: number[]; labels: string[]; color?: string; area?: boolean; unit?: string }>()

const el = ref<HTMLElement>()
let chart: echarts.ECharts | undefined

const render = () => {
  if (!el.value) return
  chart = chart || echarts.init(el.value)
  const color = props.color || '#59d9e2'
  chart.setOption({
    grid: { left: 0, right: 0, top: 9, bottom: 0, containLabel: false },
    xAxis: { type: 'category', data: props.labels, boundaryGap: false, show: false },
    yAxis: { type: 'value', show: false, scale: true, minInterval: 1 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#102630',
      borderColor: '#24525d',
      textStyle: { color: '#dff7f8', fontSize: 11 },
      formatter: (p: any) => `${p[0].axisValue}<br/><b>${p[0].value}</b> ${props.unit || ''}`
    },
    series: [{
      type: 'line',
      data: props.values,
      smooth: true,
      symbol: props.values.length > 1 ? 'none' : 'circle',
      symbolSize: 6,
      itemStyle: { color },
      lineStyle: { color, width: 2 },
      areaStyle: props.area
        ? {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: color + '50' },
              { offset: 1, color: color + '00' }
            ])
          }
        : undefined
    }]
  })
}

onMounted(() => {
  render()
  window.addEventListener('resize', render)
})
watch(() => [props.values, props.labels], render, { deep: true })
onBeforeUnmount(() => {
  chart?.dispose()
  window.removeEventListener('resize', render)
})
</script>

<template>
  <div ref="el" class="chart"></div>
</template>

<style scoped>
.chart { height: 100%; width: 100%; }
</style>

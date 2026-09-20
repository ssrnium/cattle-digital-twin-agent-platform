<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = withDefaults(
  defineProps<{ data: { value: number; name: string }[]; colors?: string[] }>(),
  { colors: () => ['#55dca8', '#f1c66c', '#ff7183'] }
)

const el = ref<HTMLElement>()
let chart: echarts.ECharts | undefined

const render = () => {
  if (!el.value) return
  chart = chart || echarts.init(el.value)
  chart.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: '#102630',
      borderColor: '#24525d',
      textStyle: { color: '#dff7f8', fontSize: 11 }
    },
    legend: {
      bottom: 0, left: 'center', itemWidth: 7, itemHeight: 7,
      textStyle: { color: '#88a8ad', fontSize: 10 }, itemGap: 13
    },
    series: [{
      type: 'pie',
      radius: ['55%', '77%'],
      center: ['50%', '43%'],
      avoidLabelOverlap: false,
      label: { show: false },
      itemStyle: { borderColor: '#10212b', borderWidth: 3 },
      color: props.colors,
      data: props.data
    }]
  })
}

onMounted(() => {
  render()
  window.addEventListener('resize', render)
})
watch(() => props.data, render, { deep: true })
onBeforeUnmount(() => {
  chart?.dispose()
  window.removeEventListener('resize', render)
})
</script>

<template>
  <div ref="el" class="chart"></div>
</template>

<style scoped>
.chart { height: 190px; width: 100%; }
</style>

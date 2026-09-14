<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="6" v-for="card in cards" :key="card.label">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="value" :style="{ color: card.color }">{{ card.value }}</div>
            <div class="label">{{ card.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="14">
        <el-card shadow="never" title="事件趋势">
          <template #header>近 7 天事件趋势</template>
          <div ref="trendRef" class="chart" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>牛群健康状态分布</template>
          <div ref="pieRef" class="chart" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import * as echarts from 'echarts'
import { barnStats } from '@/api/stats'
import type { BarnStats } from '@/api/stats'

const stats = ref<BarnStats | null>(null)
const trendRef = ref<HTMLElement>()
const pieRef = ref<HTMLElement>()
const trendChart = shallowRef<echarts.ECharts>()
const pieChart = shallowRef<echarts.ECharts>()

const cards = computed(() => [
  { label: '牛只总数', value: stats.value?.totalCows ?? '-', color: '#409eff' },
  { label: '今日事件数', value: stats.value?.todayEvents ?? '-', color: '#e6a23c' },
  { label: '未关闭工单', value: stats.value?.openOrders ?? '-', color: '#f56c6c' },
  { label: '设备在线率', value: stats.value ? stats.value.deviceOnlineRate + '%' : '-', color: '#67c23a' }
])

async function load() {
  stats.value = await barnStats()
  renderCharts()
}

function renderCharts() {
  if (!stats.value) return
  if (trendRef.value) {
    trendChart.value = trendChart.value || echarts.init(trendRef.value)
    trendChart.value.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: stats.value.eventTrend.map((i) => i.name) },
      yAxis: { type: 'value', minInterval: 1 },
      series: [{ type: 'line', smooth: true, areaStyle: {}, data: stats.value.eventTrend.map((i) => i.value) }]
    })
  }
  if (pieRef.value) {
    pieChart.value = pieChart.value || echarts.init(pieRef.value)
    const nameMap: Record<string, string> = {
      NORMAL: '正常', LAMENESS_RISK: '跛行风险', UNKNOWN: '未知（未产生孪生）'
    }
    pieChart.value.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie', radius: ['35%', '65%'],
        data: stats.value.healthDistribution.map((i) => ({ name: nameMap[i.name] || i.name, value: i.value }))
      }]
    })
  }
}

function onResize() {
  trendChart.value?.resize()
  pieChart.value?.resize()
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  trendChart.value?.dispose()
  pieChart.value?.dispose()
})
</script>

<style scoped>
.stat-card { text-align: center; padding: 8px 0; }
.value { font-size: 32px; font-weight: 700; }
.label { color: #999; margin-top: 4px; }
.chart { height: 320px; }
</style>

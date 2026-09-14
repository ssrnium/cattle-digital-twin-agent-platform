<template>
  <el-card shadow="never">
    <template #header>
      <div class="header">
        <span>20号牛棚 · 数字孪生二维图（5s 轮询，{{ lastUpdate }}）</span>
        <div class="legend">
          <span v-for="l in legend" :key="l.label"><i :style="{ background: l.color }" />{{ l.label }}</span>
        </div>
      </div>
    </template>

    <!-- ============================================================
         Three.js 三维升级插入点：
         将本 SVG 替换为 <canvas ref="threeRef">，在 onMounted 中初始化
         WebGLRenderer + 牛棚 glTF 模型资产，圆点替换为 InstancedMesh，
         twinMap 的响应式数据保持不变，仅替换渲染层。
         ============================================================ -->
    <svg viewBox="0 0 1000 560" class="barn-svg">
      <g v-for="(zone, zi) in zones" :key="zone">
        <rect :x="zoneX(zi)" :y="20" :width="230" :height="520" rx="8"
          fill="#fafafa" stroke="#dcdfe6" />
        <text :x="zoneX(zi) + 115" y="48" text-anchor="middle" fill="#909399" font-size="14">
          {{ zone }}
        </text>
        <circle v-for="cow in cowsOfZone(zone)" :key="cow.cowId"
          :cx="cowX(zone, cow)" :cy="cowY(zone, cow)" r="9"
          :fill="cowColor(cow.cowId)" stroke="#fff" stroke-width="1.5"
          class="cow-dot" @click="goDetail(cow.cowId)">
          <title>{{ cow.cowId }} {{ stateText(cow.cowId) }}</title>
        </circle>
      </g>
    </svg>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { pageCows } from '@/api/cow'
import { twinStates } from '@/api/twin'
import type { CowProfile, TwinState } from '@/api/cow'

const router = useRouter()
const cows = ref<CowProfile[]>([])
const twinMap = ref<Map<string, TwinState>>(new Map())
const lastUpdate = ref('-')
let timer: ReturnType<typeof setInterval> | undefined

const zones = ['ZONE-A', 'ZONE-B', 'ZONE-C', 'ZONE-D']
const legend = [
  { label: '正常', color: '#67c23a' },
  { label: '疑似发情', color: '#e6a23c' },
  { label: '跛行风险', color: '#f56c6c' },
  { label: '未知', color: '#c0c4cc' }
]

const cowsByZone = computed(() => {
  const map: Record<string, CowProfile[]> = {}
  for (const z of zones) map[z] = []
  for (const c of cows.value) {
    if (map[c.zone]) map[c.zone].push(c)
  }
  return map
})

function cowsOfZone(zone: string) {
  return cowsByZone.value[zone] || []
}

function zoneX(zi: number) {
  return 15 + zi * 245
}

function cowX(zone: string, cow: CowProfile) {
  const idx = cowsOfZone(zone).indexOf(cow)
  const col = idx % 5
  return zoneX(zones.indexOf(zone)) + 35 + col * 40
}

function cowY(zone: string, cow: CowProfile) {
  const idx = cowsOfZone(zone).indexOf(cow)
  const row = Math.floor(idx / 5)
  return 80 + row * 82
}

function cowColor(cowId: string) {
  const ts = twinMap.value.get(cowId)
  if (!ts) return '#c0c4cc'
  if (ts.state?.health_status === 'LAMENESS_RISK') return '#f56c6c'
  if (ts.state?.estrus_status === 'SUSPECTED_HEAT') return '#e6a23c'
  return '#67c23a'
}

function stateText(cowId: string) {
  const ts = twinMap.value.get(cowId)
  if (!ts) return '未知'
  const parts: string[] = []
  if (ts.state?.health_status === 'LAMENESS_RISK') parts.push('跛行风险')
  if (ts.state?.estrus_status === 'SUSPECTED_HEAT') parts.push('疑似发情')
  return parts.length ? parts.join(' / ') : '正常'
}

function goDetail(cowId: string) {
  router.push(`/cow/detail/${cowId}`)
}

async function loadCows() {
  const res = await pageCows({ page: 1, size: 200 })
  cows.value = res.records
}

async function pollStates() {
  const list = await twinStates()
  const map = new Map<string, TwinState>()
  for (const ts of list) map.set(ts.cowId, ts)
  twinMap.value = map
  lastUpdate.value = new Date().toLocaleTimeString()
}

onMounted(async () => {
  await loadCows()
  await pollStates()
  timer = setInterval(pollStates, 5000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.legend { display: flex; gap: 14px; font-size: 12px; color: #606266; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }
.barn-svg { width: 100%; background: #fff; border: 1px solid #ebeef5; border-radius: 8px; }
.cow-dot { cursor: pointer; transition: r 0.15s; }
.cow-dot:hover { r: 12; }
</style>

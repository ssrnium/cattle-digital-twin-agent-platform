<template>
  <el-card shadow="never">
    <template #header>
      <div class="header">
        <span>
          20号牛棚 · 数字孪生{{ fallback ? '二维图（WebGL 不可用，已降级）' : '三维场景' }}（5s 轮询，{{ lastUpdate }}）
        </span>
        <div class="legend">
          <span v-for="l in legend" :key="l.label"><i :style="{ background: l.color }" />{{ l.label }}</span>
        </div>
      </div>
    </template>

    <!-- 统计摘要：与场景颜色同一映射口径 -->
    <div class="stats">
      <div class="stat"><span>在栏总数</span><b>{{ cows.length }}</b></div>
      <div class="stat"><span>正常</span><b class="ok">{{ stats.normal }}</b></div>
      <div class="stat"><span>疑似发情</span><b class="warn">{{ stats.estrus }}</b></div>
      <div class="stat"><span>跛行风险</span><b class="risk">{{ stats.lameness }}</b></div>
      <div class="stat"><span>未知</span><b class="unk">{{ stats.unknown }}</b></div>
      <div class="hint" v-if="!fallback">拖拽旋转 · 滚轮缩放 · 点击牛只查看个体</div>
    </div>

    <div class="stage" v-if="!fallback">
      <BarnScene :cows="cows" :twin-map="twinMap" @select="onSelect" @fail="fallback = true" />

      <!-- 个体卡片：数据来自 twinStates 轮询结果 -->
      <transition name="slide">
        <div v-if="selectedCow" class="inspector glass">
          <div class="insp-head">
            <div>
              <div class="eyebrow">INDIVIDUAL</div>
              <h3>{{ selectedCow.cowId }}</h3>
              <span class="sub">耳标 {{ selectedCow.earTag || '-' }} · {{ selectedCow.zone }}</span>
            </div>
            <button class="close" @click="selectedId = ''">×</button>
          </div>
          <div class="insp-rows">
            <div><span>健康状态</span><b :class="healthClass">{{ healthText }}</b></div>
            <div><span>发情状态</span><b :class="estrusClass">{{ estrusText }}</b></div>
            <div><span>最近事件时间</span><b class="mono">{{ eventTimeText }}</b></div>
          </div>
          <el-button type="primary" class="detail-btn" @click="goDetail(selectedCow.cowId)">
            查看详情
          </el-button>
        </div>
      </transition>
    </div>

    <!-- WebGL 降级分支：保留原 SVG 二维视图 -->
    <svg v-else viewBox="0 0 1000 560" class="barn-svg">
      <g v-for="(zone, zi) in zones" :key="zone">
        <rect :x="zoneX(zi)" :y="20" :width="230" :height="520" rx="8"
          fill="rgba(9, 27, 36, 0.72)" stroke="#1d3a44" />
        <text :x="zoneX(zi) + 115" y="48" text-anchor="middle" fill="#73909a" font-size="14">
          {{ zone }}
        </text>
        <circle v-for="cow in cowsOfZone(zone)" :key="cow.cowId"
          :cx="cowX(zone, cow)" :cy="cowY(zone, cow)" r="9"
          :fill="cowColor(cow.cowId)" stroke="#0b1d26" stroke-width="1.5"
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
import BarnScene from './BarnScene.vue'

const router = useRouter()
const cows = ref<CowProfile[]>([])
const twinMap = ref<Map<string, TwinState>>(new Map())
const lastUpdate = ref('-')
const fallback = ref(false)
const selectedId = ref('')
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

// 与场景 / SVG 共用同一套颜色口径
function statusOf(cowId: string): 'normal' | 'estrus' | 'lameness' | 'unknown' {
  const ts = twinMap.value.get(cowId)
  if (!ts) return 'unknown'
  if (ts.state?.health_status === 'LAMENESS_RISK') return 'lameness'
  if (ts.state?.estrus_status === 'SUSPECTED_HEAT') return 'estrus'
  return 'normal'
}

const stats = computed(() => {
  const s = { normal: 0, estrus: 0, lameness: 0, unknown: 0 }
  for (const c of cows.value) s[statusOf(c.cowId)]++
  return s
})

const selectedCow = computed(() => cows.value.find((c) => c.cowId === selectedId.value) || null)
const selectedTs = computed(() => (selectedId.value ? twinMap.value.get(selectedId.value) : undefined))

const healthText = computed(() => {
  if (!selectedTs.value) return '未知'
  return selectedTs.value.state?.health_status === 'LAMENESS_RISK' ? '跛行风险' : '健康'
})
const healthClass = computed(() => (healthText.value === '跛行风险' ? 'risk' : healthText.value === '未知' ? 'unk' : 'ok'))
const estrusText = computed(() => {
  if (!selectedTs.value) return '未知'
  return selectedTs.value.state?.estrus_status === 'SUSPECTED_HEAT' ? '疑似发情' : '正常'
})
const estrusClass = computed(() => (estrusText.value === '疑似发情' ? 'warn' : estrusText.value === '未知' ? 'unk' : 'ok'))
const eventTimeText = computed(() => {
  const t = selectedTs.value?.eventTime || selectedTs.value?.updatedAt
  return t ? new Date(t).toLocaleString() : '-'
})

function onSelect(cowId: string) {
  selectedId.value = cowId
}

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
  switch (statusOf(cowId)) {
    case 'lameness': return '#f56c6c'
    case 'estrus': return '#e6a23c'
    case 'normal': return '#67c23a'
    default: return '#c0c4cc'
  }
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
.legend { display: flex; gap: 14px; font-size: 12px; color: #7fa0a7; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }

.stats { display: flex; align-items: center; gap: 22px; margin-bottom: 12px; flex-wrap: wrap; }
.stat { display: flex; align-items: baseline; gap: 7px; font-size: 12px; color: #7fa0a7; }
.stat b { font-size: 17px; color: #d8edf0; font-weight: 600; }
.stat b.ok { color: #67c23a; }
.stat b.warn { color: #e6a23c; }
.stat b.risk { color: #f56c6c; }
.stat b.unk { color: #c0c4cc; }
.hint { margin-left: auto; font-size: 11px; color: #54777f; letter-spacing: 0.04em; }

.stage { position: relative; }

.inspector {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 240px;
  padding: 16px;
  z-index: 3;
}
.insp-head { display: flex; justify-content: space-between; }
.insp-head h3 { margin: 5px 0 4px; font-size: 22px; letter-spacing: 0.02em; }
.insp-head .sub { font-size: 11px; color: #7fa0a7; }
.close { border: 0; background: transparent; color: #6c919a; font-size: 20px; cursor: pointer; align-self: flex-start; }
.close:hover { color: #d8edf0; }
.insp-rows { display: grid; gap: 11px; margin: 16px 0; padding: 12px 0; border-top: 1px solid var(--ranch-border); border-bottom: 1px solid var(--ranch-border); }
.insp-rows > div { display: flex; justify-content: space-between; align-items: center; font-size: 12px; }
.insp-rows span { color: #7fa0a7; }
.insp-rows b.ok { color: #67c23a; }
.insp-rows b.warn { color: #e6a23c; }
.insp-rows b.risk { color: #f56c6c; }
.insp-rows b.unk { color: #c0c4cc; }
.insp-rows .mono { font-size: 11px; color: #a9c6cc; }
.detail-btn { width: 100%; }

.slide-enter-active, .slide-leave-active { transition: all 0.22s ease; }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateX(14px); }

.barn-svg { width: 100%; background: #0a1a24; border: 1px solid #1d3a44; border-radius: 8px; }
.cow-dot { cursor: pointer; transition: r 0.15s; }
.cow-dot:hover { r: 12; }
</style>

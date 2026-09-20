<template>
  <div class="dashboard">
    <div class="hero-row">
      <div>
        <div class="eyebrow">{{ nowText }}</div>
        <h2>牧场运行状态 <span class="live-chip"><i></i> LIVE</span></h2>
        <p v-if="stats">
          数字孪生正在持续感知 {{ stats.totalCows }} 头奶牛、{{ stats.totalDevices }} 个 IoT 设备，
          今日已接入 {{ stats.todayEvents }} 条行为事件。
        </p>
      </div>
      <button class="outline-btn" @click="router.push('/assistant')">
        <el-icon><Lightning /></el-icon> 询问牧场 Agent <el-icon><ArrowRight /></el-icon>
      </button>
    </div>

    <div class="kpi-grid">
      <KpiCard v-for="item in kpis" :key="item.label" :item="item" />
    </div>

    <div class="main-grid">
      <section class="glass panel">
        <SectionHeader title="近 7 天事件趋势" eyebrow="EVENT STREAM" />
        <div class="chart-toolbar">
          <div class="metric-highlight">
            <strong class="mono">{{ stats?.todayEvents ?? '-' }}</strong>
            <span>条 / 今日事件</span>
          </div>
        </div>
        <div class="line-wrap">
          <LineChart :values="trendValues" :labels="trendLabels" area unit="条" />
        </div>
        <div class="x-labels"><span v-for="d in trendLabels" :key="d">{{ d }}</span></div>
      </section>

      <section class="glass panel">
        <SectionHeader title="群体健康分布" eyebrow="HERD HEALTH" />
        <div class="donut-wrap">
          <DonutChart :data="healthData" :colors="healthColors" />
          <div class="donut-center">
            <strong class="mono">{{ stats?.totalCows ?? '-' }}</strong>
            <span>在册奶牛</span>
          </div>
        </div>
      </section>
    </div>

    <div class="bottom-grid">
      <section class="glass panel">
        <SectionHeader title="异常预警" eyebrow="RISK SIGNALS" action="全部事件"
          @action="router.push('/event')" />
        <div v-if="alerts.length === 0" class="empty">暂无风险事件</div>
        <div class="alert-list">
          <div v-for="a in alerts" :key="a.id" class="alert-row">
            <div class="level" :class="a.levelCls">{{ a.level }}</div>
            <div class="alert-copy">
              <b>{{ a.title }}</b>
              <span>{{ a.detail }}</span>
            </div>
            <time class="mono">{{ a.time }}</time>
          </div>
        </div>
      </section>

      <!-- 数据口径说明：样稿此处为「Agent 日报」，我们无日报接口，
           改为对接真实 agent 会话接口（/agent/sessions），不虚构内容 -->
      <section class="glass panel">
        <SectionHeader title="Agent 会话状态" eyebrow="AI COPILOT / SESSIONS" action="进入助手"
          @action="router.push('/assistant')" />
        <div v-if="agentError" class="empty">{{ agentError }}</div>
        <div v-else-if="agentList.length === 0" class="empty">暂无活跃会话，去 AI 助手发起对话</div>
        <div v-for="s in agentList" :key="s.session_id" class="session-row">
          <div class="session-icon"><el-icon><ChatDotRound /></el-icon></div>
          <div class="session-copy">
            <div class="session-title mono">{{ s.session_id }}</div>
            <p>最近活跃 {{ formatTime(s.last_active) }}</p>
          </div>
          <span class="session-state" :class="{ pending: s.pending_confirmation }">
            {{ s.pending_confirmation ? '待审批' : '运行中' }}
          </span>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Lightning, ChatDotRound } from '@element-plus/icons-vue'
import KpiCard from '@/components/KpiCard.vue'
import type { KpiItem } from '@/components/KpiCard.vue'
import SectionHeader from '@/components/SectionHeader.vue'
import LineChart from '@/components/LineChart.vue'
import DonutChart from '@/components/DonutChart.vue'
import { barnStats } from '@/api/stats'
import type { BarnStats } from '@/api/stats'
import { pageEvents } from '@/api/event'
import type { UnifiedEvent } from '@/api/event'
import { agentSessions } from '@/api/agent'
import type { AgentSession } from '@/api/agent'

const router = useRouter()
const stats = ref<BarnStats | null>(null)
const alerts = ref<{ id: number; level: string; levelCls: string; title: string; detail: string; time: string }[]>([])
const agentList = ref<AgentSession[]>([])
const agentError = ref('')
const nowText = ref('')

const EVENT_META: Record<string, { level: string; levelCls: string; label: string }> = {
  LAMENESS: { level: '高', levelCls: 'high', label: '跛行风险' },
  MOUNTING: { level: '中', levelCls: 'mid', label: '疑似发情爬跨' },
  DEVICE_OFFLINE: { level: '中', levelCls: 'mid', label: '设备离线' },
  DEVICE_RECOVERED: { level: '低', levelCls: 'low', label: '设备恢复' },
  SYNC_STATE: { level: '低', levelCls: 'low', label: '状态同步' }
}

const HEALTH_NAME: Record<string, string> = {
  NORMAL: '正常', LAMENESS_RISK: '跛行风险', UNKNOWN: '未知（未产生孪生）'
}
const HEALTH_COLOR: Record<string, string> = {
  NORMAL: '#55dca8', LAMENESS_RISK: '#ff7183', UNKNOWN: '#5f7d85'
}

const kpis = computed<KpiItem[]>(() => [
  { label: '牛只总数', value: stats.value?.totalCows ?? '-', unit: '头', icon: 'cow', tone: 'cyan', foot: '孪生体实时同步' },
  { label: '今日事件数', value: stats.value?.todayEvents ?? '-', unit: '条', icon: 'event', tone: 'amber', foot: '行为识别事件流' },
  { label: '未关闭工单', value: stats.value?.openOrders ?? '-', unit: '张', icon: 'task', tone: 'danger', foot: '繁殖/健康任务闭环' },
  {
    label: '设备在线率',
    value: stats.value ? stats.value.deviceOnlineRate : '-',
    unit: '%', icon: 'device', tone: 'green',
    foot: stats.value ? `在线 ${stats.value.onlineDevices} / 共 ${stats.value.totalDevices}` : ''
  }
])

const trendValues = computed(() => stats.value?.eventTrend.map((i) => i.value) ?? [])
const trendLabels = computed(() => stats.value?.eventTrend.map((i) => i.name) ?? [])

const healthData = computed(
  () => stats.value?.healthDistribution.map((i) => ({ name: HEALTH_NAME[i.name] || i.name, value: i.value })) ?? []
)
const healthColors = computed(
  () => stats.value?.healthDistribution.map((i) => HEALTH_COLOR[i.name] || '#5f7d85') ?? []
)

function formatTime(ts: number) {
  if (!ts) return '-'
  const d = ts > 1e12 ? new Date(ts) : new Date(ts * 1000)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function tickClock() {
  const d = new Date()
  const week = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY'][d.getDay()]
  const pad = (n: number) => String(n).padStart(2, '0')
  nowText.value = `${week} · ${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())} · ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

async function loadStats() {
  stats.value = await barnStats()
}

async function loadAlerts() {
  try {
    const res = await pageEvents({ page: 1, size: 6 })
    alerts.value = res.records.map((e: UnifiedEvent) => {
      const meta = EVENT_META[e.eventType] || { level: '低', levelCls: 'low', label: e.eventType }
      return {
        id: e.id,
        level: meta.level,
        levelCls: meta.levelCls,
        title: `${meta.label} · ${e.cowId || e.deviceId || '-'}`,
        detail: `置信度 ${e.confidence != null ? Math.round(e.confidence * 100) + '%' : '-'} · 来源 ${e.deviceId || '-'} · 模型 ${e.modelVersion || '-'}`,
        time: (e.eventTime || '').slice(5, 16)
      }
    })
  } catch {
    /* 事件接口失败时列表留空，不虚构 */
  }
}

async function loadAgentSessions() {
  try {
    const resp = await agentSessions(true)
    agentList.value = resp.sessions
      .slice()
      .sort((a, b) => b.last_active - a.last_active)
      .slice(0, 4)
  } catch {
    agentError.value = 'Agent 服务未连接或无权限（agent:chat）'
  }
}

onMounted(() => {
  tickClock()
  setInterval(tickClock, 1000)
  loadStats()
  loadAlerts()
  loadAgentSessions()
})
</script>

<style scoped>
.dashboard { max-width: 1600px; margin: auto; }
.hero-row { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 23px; }
.hero-row h2 { font-size: 24px; margin: 8px 0; letter-spacing: -0.03em; color: #e7f4f6; }
.hero-row p { margin: 0; color: #7e9ca3; font-size: 12px; }
.live-chip { font-size: 10px; letter-spacing: 0.1em; color: #59dfb0; margin-left: 8px; vertical-align: middle; }
.live-chip i {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: #59dfb0; box-shadow: 0 0 9px #59dfb0; margin-right: 4px;
}
.outline-btn {
  border: 1px solid #2c858c; background: #0d2b34; color: #a1ebeb;
  padding: 10px 14px; border-radius: 8px; display: flex; align-items: center;
  gap: 8px; font-size: 11px; cursor: pointer;
}
.outline-btn:hover { border-color: #4caeb1; color: #d5f4f4; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.main-grid { display: grid; grid-template-columns: 1.7fr 1fr; gap: 14px; margin-top: 14px; }
.bottom-grid { display: grid; grid-template-columns: 1.35fr 1fr; gap: 14px; margin-top: 14px; }
.panel { padding: 19px 20px; }
.chart-toolbar { display: flex; justify-content: space-between; align-items: flex-end; }
.metric-highlight strong { font-size: 25px; letter-spacing: -0.04em; color: #e7f4f6; }
.metric-highlight span { font-size: 11px; color: #7d9aa0; margin-left: 6px; }
.line-wrap { height: 166px; margin: 14px -3px 0; }
.x-labels { display: flex; justify-content: space-between; color: #5f7d85; font-size: 9px; margin-top: 3px; }
.donut-wrap { height: 190px; position: relative; }
.donut-center { position: absolute; left: 0; right: 0; top: 60px; text-align: center; pointer-events: none; }
.donut-center strong { display: block; font-size: 26px; color: #e7f4f6; }
.donut-center span { font-size: 10px; color: #709097; }
.empty { color: #66848b; font-size: 11px; text-align: center; padding: 24px 0; }
.alert-list { display: grid; gap: 7px; }
.alert-row {
  display: flex; align-items: center; gap: 12px; padding: 10px 8px;
  border-radius: 9px; background: rgba(9, 27, 36, 0.72); border: 1px solid #14343d;
}
.level { width: 23px; height: 23px; display: grid; place-items: center; font-size: 10px; border-radius: 6px; flex: none; }
.level.high { background: #4d2734; color: #ff9ba7; }
.level.mid { background: #4d3e25; color: #f1ce7e; }
.level.low { background: #1e3e3a; color: #7ae2bd; }
.alert-copy { flex: 1; min-width: 0; }
.alert-copy b { font-size: 11px; display: block; color: #d9eef0; font-weight: 600; }
.alert-copy span {
  font-size: 10px; color: #74929a; display: block; margin-top: 4px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.alert-row time { font-size: 10px; color: #66848b; }
.session-row {
  display: flex; align-items: center; gap: 11px; padding: 10px 0;
  border-bottom: 1px solid #17333c;
}
.session-row:last-of-type { border-bottom: 0; }
.session-icon {
  width: 26px; height: 26px; border-radius: 7px; background: #143c44;
  color: #6edce0; display: grid; place-items: center; flex: none;
}
.session-copy { flex: 1; min-width: 0; }
.session-title { font-size: 11px; color: #d7eff1; overflow: hidden; text-overflow: ellipsis; }
.session-copy p { font-size: 10px; color: #78969d; margin: 5px 0 0; }
.session-state {
  font-size: 9px; color: #74d0ba; border: 1px solid #266253;
  padding: 2px 6px; border-radius: 3px; flex: none;
}
.session-state.pending { color: #f1ce7e; border-color: #6b5a2a; }
</style>

<script setup lang="ts">
export interface KpiItem {
  label: string
  value: string | number
  unit?: string
  icon?: string
  tone?: 'cyan' | 'green' | 'amber' | 'purple' | 'danger'
  foot?: string
}

withDefaults(defineProps<{ item: KpiItem }>(), {})
</script>

<template>
  <div class="glass kpi-card">
    <div class="kpi-top">
      <span class="eyebrow">{{ item.label }}</span>
      <span class="kpi-icon" :class="item.tone || 'cyan'">
        {{ item.icon === 'cow' ? '◈' : item.icon === 'health' ? '✦' : item.icon === 'device' ? '◒' : '⌁' }}
      </span>
    </div>
    <div class="kpi-value mono">{{ item.value }}<small>{{ item.unit }}</small></div>
    <div v-if="item.foot" class="kpi-foot"><span class="subtle">{{ item.foot }}</span></div>
  </div>
</template>

<style scoped>
.kpi-card { padding: 18px 20px; min-height: 118px; }
.kpi-top, .kpi-foot { display: flex; justify-content: space-between; align-items: center; }
.kpi-icon {
  width: 28px; height: 28px; border-radius: 8px; display: grid; place-items: center;
  background: #123744; font-size: 15px; color: #58d8e7;
}
.kpi-icon.green { background: #153f3a; color: #68e0aa; }
.kpi-icon.amber { background: #443722; color: #f3c66b; }
.kpi-icon.purple { background: #322948; color: #b59cff; }
.kpi-icon.danger { background: #4d2734; color: #ff7c8b; }
.kpi-value { font-size: 30px; font-weight: 650; letter-spacing: -0.04em; margin: 14px 0 11px; color: #e7f4f6; }
.kpi-value small { font-size: 12px; color: #86a4ab; font-weight: 500; margin-left: 7px; letter-spacing: 0; }
.kpi-foot { font-size: 11px; }
</style>

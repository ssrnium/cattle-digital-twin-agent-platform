<template>
  <el-card shadow="never">
    <div class="toolbar">
      <el-select v-model="query.eventType" placeholder="事件类型" clearable style="width: 220px" @change="load">
        <el-option label="爬跨 MOUNTING" value="MOUNTING" />
        <el-option label="跛行 LAMENESS" value="LAMENESS" />
        <el-option label="设备离线 DEVICE_OFFLINE" value="DEVICE_OFFLINE" />
        <el-option label="设备恢复 DEVICE_RECOVERED" value="DEVICE_RECOVERED" />
        <el-option label="状态同步 SYNC_STATE" value="SYNC_STATE" />
      </el-select>
      <el-input v-model="query.cowId" placeholder="牛号，如 COW-0001" clearable style="width: 180px" @change="load" />
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="eventTime" label="事件时间" width="170" sortable />
      <el-table-column prop="eventType" label="类型" width="150">
        <template #default="{ row }">
          <el-tag :type="typeTag(row.eventType)">{{ row.eventType }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="牛号" width="120">
        <template #default="{ row }">
          <el-link v-if="row.cowId" type="primary" @click="$router.push(`/cow/detail/${row.cowId}`)">
            {{ row.cowId }}
          </el-link>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="deviceId" label="来源设备" width="130" />
      <el-table-column label="置信度" width="150">
        <template #default="{ row }">
          <el-progress v-if="row.confidence != null" :percentage="Math.round(row.confidence * 100)"
            :stroke-width="10" :color="row.confidence >= 0.8 ? '#f56c6c' : '#e6a23c'" />
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="quality" label="质量" width="90" />
      <el-table-column prop="modelVersion" label="模型版本" width="160" />
      <el-table-column prop="eventId" label="event_id（幂等键）" min-width="260" show-overflow-tooltip />
    </el-table>

    <el-pagination class="pager" layout="total, prev, pager, next" :total="total"
      :page-size="query.size" :current-page="query.page"
      @current-change="(p: number) => { query.page = p; load() }" />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { pageEvents } from '@/api/event'
import type { UnifiedEvent } from '@/api/event'

const rows = ref<UnifiedEvent[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 15, eventType: '', cowId: '' })

function typeTag(t: string): 'warning' | 'danger' | 'info' | 'success' | 'primary' {
  if (t === 'MOUNTING') return 'warning'
  if (t === 'LAMENESS') return 'danger'
  if (t === 'DEVICE_OFFLINE') return 'info'
  if (t === 'DEVICE_RECOVERED') return 'success'
  return 'primary'
}

async function load() {
  loading.value = true
  try {
    const res = await pageEvents({ ...query, eventType: query.eventType || undefined, cowId: query.cowId || undefined })
    rows.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>

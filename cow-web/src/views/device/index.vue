<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="8" v-for="d in devices" :key="d.deviceId">
        <el-card shadow="hover" class="device-card">
          <div class="head">
            <span class="dot" :class="d.onlineStatus === 'ONLINE' ? 'online' : 'offline'" />
            <b>{{ d.name }}</b>
            <el-tag size="small" :type="d.type === 'EDGE_NODE' ? 'warning' : 'info'">{{ d.type }}</el-tag>
          </div>
          <el-descriptions :column="1" size="small" border class="desc">
            <el-descriptions-item label="设备ID">{{ d.deviceId }}</el-descriptions-item>
            <el-descriptions-item label="在线状态">
              <el-tag :type="d.onlineStatus === 'ONLINE' ? 'success' : 'danger'" size="small">
                {{ d.onlineStatus }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="最后心跳">{{ d.lastHeartbeatAt || '-' }}</el-descriptions-item>
            <el-descriptions-item label="待补传 pending_count">
              <el-badge :value="d.pendingCount" :type="d.pendingCount > 0 ? 'danger' : 'success'">
                <span style="width: 24px; display: inline-block" />
              </el-badge>
            </el-descriptions-item>
            <el-descriptions-item label="断网时长">{{ offlineText(d.offlineSeconds) }}</el-descriptions-item>
            <el-descriptions-item label="最后同步">{{ d.lastSyncAt || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { listDevices } from '@/api/device'
import type { DeviceView } from '@/api/device'

const devices = ref<DeviceView[]>([])
let timer: ReturnType<typeof setInterval> | undefined

function offlineText(seconds: number) {
  if (!seconds) return '-'
  if (seconds < 3600) return Math.floor(seconds / 60) + ' 分钟'
  if (seconds < 86400) return (seconds / 3600).toFixed(1) + ' 小时'
  return (seconds / 86400).toFixed(1) + ' 天'
}

async function load() {
  devices.value = await listDevices()
}

onMounted(() => {
  load()
  timer = setInterval(load, 10000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.device-card { margin-bottom: 16px; }
.head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.dot { width: 10px; height: 10px; border-radius: 50%; }
.dot.online { background: #67c23a; box-shadow: 0 0 6px #67c23a; }
.dot.offline { background: #f56c6c; box-shadow: 0 0 6px #f56c6c; }
.desc { margin-top: 4px; }
</style>

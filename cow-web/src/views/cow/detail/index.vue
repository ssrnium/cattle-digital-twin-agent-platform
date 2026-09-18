<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="9">
        <el-card shadow="never">
          <template #header>牛只档案</template>
          <el-descriptions v-if="profile" :column="1" border>
            <el-descriptions-item label="牛号">{{ profile.cowId }}</el-descriptions-item>
            <el-descriptions-item label="耳标">{{ profile.earTag }}</el-descriptions-item>
            <el-descriptions-item label="牛棚">{{ profile.barnId }}</el-descriptions-item>
            <el-descriptions-item label="分区">{{ profile.zone }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ profile.status }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
        <el-card shadow="never" style="margin-top: 16px">
          <template #header>当前孪生状态</template>
          <template v-if="twin">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="健康状态">
                <el-tag :type="twin.state?.health_status === 'LAMENESS_RISK' ? 'danger' : 'success'">
                  {{ healthText }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="发情状态">
                <el-tag :type="twin.state?.estrus_status === 'SUSPECTED_HEAT' ? 'warning' : 'success'">
                  {{ estrusText }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="姿态">{{ twin.state?.posture || '-' }}</el-descriptions-item>
              <el-descriptions-item label="状态性质">
                <el-tag size="small" effect="plain">{{ twin.stateNature }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="来源事件">{{ twin.sourceEventId || '-' }}</el-descriptions-item>
              <el-descriptions-item label="事件时间">{{ twin.eventTime || '-' }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ twin.updatedAt }}</el-descriptions-item>
            </el-descriptions>
          </template>
          <el-empty v-else description="暂无孪生状态（尚未产生事件）" :image-size="60" />
        </el-card>
      </el-col>

      <el-col :span="15">
        <el-card shadow="never">
          <template #header>单牛时间线</template>
          <el-timeline v-if="timeline.length">
            <el-timeline-item v-for="item in timeline" :key="item.id"
              :timestamp="item.eventTime" placement="top"
              :type="timelineColor(item.eventType)" :icon="timelineIcon(item.eventType)" :hollow="false">
              <div class="tl-title">
                <b>{{ item.title }}</b>
                <el-tag size="small" effect="plain" class="nature">{{ item.stateNature }}</el-tag>
                <el-tag size="small" :type="timelineColor(item.eventType)">{{ item.eventType }}</el-tag>
              </div>
              <div class="tl-detail">
                <span v-if="item.detail?.confidence != null">置信度 {{ item.detail.confidence }}</span>
                <span v-if="item.detail?.model_version">模型 {{ item.detail.model_version }}</span>
                <span v-if="item.detail?.device_id">来源 {{ item.detail.device_id }}</span>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无时间线记录" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { cowDetail, cowTimeline } from '@/api/cow'
import type { CowProfile, CowTimeline, TwinState } from '@/api/cow'

const route = useRoute()
const cowId = route.params.cowId as string

const profile = ref<CowProfile | null>(null)
const twin = ref<TwinState | null>(null)
const timeline = ref<CowTimeline[]>([])

const healthText = computed(() =>
  twin.value?.state?.health_status === 'LAMENESS_RISK' ? '跛行风险' : '正常')
const estrusText = computed(() =>
  twin.value?.state?.estrus_status === 'SUSPECTED_HEAT' ? '疑似发情' : '正常')

function timelineColor(type: string): 'warning' | 'danger' | 'info' | 'primary' {
  if (type === 'MOUNTING') return 'warning'
  if (type === 'LAMENESS') return 'danger'
  if (type === 'SYNC_STATE') return 'info'
  return 'primary'
}

function timelineIcon(_type?: string) {
  return undefined
}

onMounted(async () => {
  const d = await cowDetail(cowId)
  profile.value = d.profile
  twin.value = d.twinState
  timeline.value = await cowTimeline(cowId)
})
</script>

<style scoped>
.tl-title { display: flex; align-items: center; gap: 8px; }
.nature { letter-spacing: 1px; }
.tl-detail { color: #909399; font-size: 12px; display: flex; gap: 14px; margin-top: 4px; }
</style>

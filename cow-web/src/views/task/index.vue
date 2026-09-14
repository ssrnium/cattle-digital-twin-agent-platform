<template>
  <el-card shadow="never">
    <el-tabs v-model="activeState" @tab-change="load">
      <el-tab-pane v-for="s in states" :key="s.value" :label="s.label" :name="s.value" />
    </el-tabs>

    <div class="toolbar">
      <el-select v-model="queryType" placeholder="工单类型" clearable style="width: 180px" @change="load">
        <el-option label="配种复查 BREEDING_REVIEW" value="BREEDING_REVIEW" />
        <el-option label="兽医检查 VET_CHECK" value="VET_CHECK" />
        <el-option label="设备维修 DEVICE_REPAIR" value="DEVICE_REPAIR" />
      </el-select>
      <el-button type="primary" @click="load">刷新</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="orderNo" label="工单号" width="210" />
      <el-table-column prop="type" label="类型" width="150">
        <template #default="{ row }">
          <el-tag :type="typeTag(row.type)">{{ typeText(row.type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="对象" width="130">
        <template #default="{ row }">
          <el-link v-if="row.cowId" type="primary" @click="$router.push(`/cow/detail/${row.cowId}`)">
            {{ row.cowId }}
          </el-link>
          <span v-else>{{ row.deviceId }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="priority" label="优先级" width="90">
        <template #default="{ row }">
          <el-tag :type="row.priority === 'HIGH' ? 'danger' : 'info'" size="small">{{ row.priority }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column label="处理人" width="110">
        <template #default="{ row }">{{ userName(row.assigneeId) }}</template>
      </el-table-column>
      <el-table-column prop="createTime" label="创建时间" width="165" />
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <!-- 操作按钮随状态机走；每次操作携带当前 version 做乐观锁 -->
          <el-button v-if="row.state === 'NEW'" size="small" type="primary" @click="openAssign(row)">分派</el-button>
          <el-button v-if="row.state === 'DISPATCHED'" size="small" type="primary" @click="onStart(row)">开始处理</el-button>
          <el-button v-if="row.state === 'PROCESSING'" size="small" type="warning" @click="openSubmit(row)">提交复查</el-button>
          <el-button v-if="row.state === 'PROCESSING'" size="small" type="danger" @click="onCancel(row)">取消</el-button>
          <template v-if="row.state === 'PENDING_REVIEW'">
            <el-button size="small" type="success" @click="onReview(row, true)">复查通过</el-button>
            <el-button size="small" type="danger" @click="onReview(row, false)">驳回</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="pager" layout="total, prev, pager, next" :total="total"
      :page-size="query.size" :current-page="query.page"
      @current-change="(p: number) => { query.page = p; load() }" />

    <el-dialog v-model="assignVisible" title="分派工单" width="380px">
      <el-select v-model="assigneeId" placeholder="选择处理人" style="width: 100%">
        <el-option v-for="u in users" :key="u.id" :label="`${u.nickname || u.username}（${u.username}）`" :value="u.id" />
      </el-select>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" @click="onAssign">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="submitVisible" title="提交复查" width="420px">
      <el-input v-model="submitResult" type="textarea" :rows="3" placeholder="处理情况说明" />
      <template #footer>
        <el-button @click="submitVisible = false">取消</el-button>
        <el-button type="primary" @click="onSubmitReview">提交</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { pageTasks, assignTask, startTask, submitReview, reviewTask, cancelTask } from '@/api/task'
import { userOptions } from '@/api/system'
import type { WorkOrder } from '@/api/task'
import type { SysUser } from '@/api/system'

const states = [
  { label: '新建', value: 'NEW' },
  { label: '已分派', value: 'DISPATCHED' },
  { label: '处理中', value: 'PROCESSING' },
  { label: '待复查', value: 'PENDING_REVIEW' },
  { label: '已关闭', value: 'CLOSED' },
  { label: '已取消', value: 'CANCELLED' }
]

const activeState = ref('NEW')
const queryType = ref('')
const rows = ref<WorkOrder[]>([])
const total = ref(0)
const loading = ref(false)
const users = ref<SysUser[]>([])
const query = reactive({ page: 1, size: 10 })

const assignVisible = ref(false)
const assigneeId = ref<number>()
const current = ref<WorkOrder | null>(null)
const submitVisible = ref(false)
const submitResult = ref('')

function typeText(t: string) {
  return { BREEDING_REVIEW: '配种复查', VET_CHECK: '兽医检查', DEVICE_REPAIR: '设备维修' }[t] || t
}
function typeTag(t: string): 'warning' | 'danger' | 'info' {
  if (t === 'BREEDING_REVIEW') return 'warning'
  if (t === 'VET_CHECK') return 'danger'
  return 'info'
}
function userName(id: number) {
  const u = users.value.find((x) => x.id === id)
  return u ? (u.nickname || u.username) : (id ?? '-')
}

async function load() {
  loading.value = true
  try {
    const res = await pageTasks({ ...query, state: activeState.value, type: queryType.value || undefined })
    rows.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function openAssign(row: WorkOrder) {
  current.value = row
  assigneeId.value = undefined
  assignVisible.value = true
}

async function onAssign() {
  if (!current.value || !assigneeId.value) {
    ElMessage.warning('请选择处理人')
    return
  }
  await assignTask(current.value.id, assigneeId.value, current.value.version)
  ElMessage.success('已分派')
  assignVisible.value = false
  load()
}

async function onStart(row: WorkOrder) {
  await startTask(row.id, row.version)
  ElMessage.success('已开始处理')
  load()
}

function openSubmit(row: WorkOrder) {
  current.value = row
  submitResult.value = ''
  submitVisible.value = true
}

async function onSubmitReview() {
  if (!current.value) return
  await submitReview(current.value.id, submitResult.value, current.value.version)
  ElMessage.success('已提交复查')
  submitVisible.value = false
  load()
}

async function onReview(row: WorkOrder, approved: boolean) {
  const { value } = await ElMessageBox.prompt(
    approved ? '复查意见（通过）' : '复查意见（驳回）', '工单复查',
    { confirmButtonText: '确定', cancelButtonText: '取消', inputValue: approved ? '复查通过' : '复查不通过' }
  )
  await reviewTask(row.id, approved, value, row.version)
  ElMessage.success(approved ? '已关闭' : '已驳回')
  load()
}

async function onCancel(row: WorkOrder) {
  const { value } = await ElMessageBox.prompt('取消原因', '取消工单',
    { confirmButtonText: '确定', cancelButtonText: '取消' })
  await cancelTask(row.id, value, row.version)
  ElMessage.success('已取消')
  load()
}

onMounted(async () => {
  users.value = await userOptions()
  load()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>

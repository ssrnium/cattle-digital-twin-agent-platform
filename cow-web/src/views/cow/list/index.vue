<template>
  <el-card shadow="never">
    <div class="toolbar">
      <el-input v-model="query.keyword" placeholder="牛号 / 耳标" clearable style="width: 200px" @change="load" />
      <el-select v-model="query.zone" placeholder="分区" clearable style="width: 140px" @change="load">
        <el-option v-for="z in zones" :key="z" :label="z" :value="z" />
      </el-select>
      <el-button type="primary" @click="load">查询</el-button>
      <el-button type="success" @click="openEdit()">新增牛只</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="cowId" label="牛号" width="120">
        <template #default="{ row }">
          <el-link type="primary" @click="$router.push(`/cow/detail/${row.cowId}`)">{{ row.cowId }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="earTag" label="耳标" width="120" />
      <el-table-column prop="barnId" label="牛棚" />
      <el-table-column prop="zone" label="分区" width="110" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'ACTIVE' ? 'success' : 'info'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createTime" label="建档时间" width="170" />
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-popconfirm title="确认删除该牛只档案？" @confirm="onDelete(row)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="pager" layout="total, prev, pager, next" :total="total"
      :page-size="query.size" :current-page="query.page" @current-change="(p: number) => { query.page = p; load() }" />

    <el-dialog v-model="dialogVisible" :title="editForm.id ? '编辑牛只' : '新增牛只'" width="420px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="牛号">
          <el-input v-model="editForm.cowId" :disabled="!!editForm.id" placeholder="如 COW-0104" />
        </el-form-item>
        <el-form-item label="耳标"><el-input v-model="editForm.earTag" /></el-form-item>
        <el-form-item label="分区">
          <el-select v-model="editForm.zone" style="width: 100%">
            <el-option v-for="z in zones" :key="z" :label="z" :value="z" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option label="ACTIVE" value="ACTIVE" />
            <el-option label="CULLED" value="CULLED" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { pageCows, createCow, updateCow, deleteCow } from '@/api/cow'
import type { CowProfile } from '@/api/cow'

const zones = ['ZONE-A', 'ZONE-B', 'ZONE-C', 'ZONE-D']
const rows = ref<CowProfile[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 10, keyword: '', zone: '' })

const dialogVisible = ref(false)
const editForm = reactive<Partial<CowProfile>>({})

async function load() {
  loading.value = true
  try {
    const res = await pageCows({ ...query })
    rows.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function openEdit(row?: CowProfile) {
  Object.assign(editForm, { id: undefined, cowId: '', earTag: '', zone: 'ZONE-A', status: 'ACTIVE' }, row)
  dialogVisible.value = true
}

async function onSave() {
  if (editForm.id) {
    await updateCow(editForm.id, editForm)
  } else {
    await createCow(editForm)
  }
  ElMessage.success('已保存')
  dialogVisible.value = false
  load()
}

async function onDelete(row: CowProfile) {
  await deleteCow(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>

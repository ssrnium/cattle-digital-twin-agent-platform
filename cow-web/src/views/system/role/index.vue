<template>
  <el-card shadow="never">
    <div class="toolbar">
      <el-button type="success" @click="openEdit()">新增角色</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="roleCode" label="角色编码" width="140" />
      <el-table-column prop="roleName" label="角色名称" width="160" />
      <el-table-column prop="description" label="描述" />
      <el-table-column label="权限" min-width="260">
        <template #default="{ row }">
          <el-tag v-for="p in permMap[row.id] || []" :key="p" size="small" style="margin: 2px">{{ p }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-popconfirm title="确认删除该角色？" @confirm="onDelete(row)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="pager" layout="total, prev, pager, next" :total="total"
      :page-size="10" :current-page="page" @current-change="(p: number) => { page = p; load() }" />

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑角色' : '新增角色'" width="460px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="角色编码">
          <el-input v-model="form.roleCode" :disabled="!!form.id" placeholder="如 VET" />
        </el-form-item>
        <el-form-item label="角色名称"><el-input v-model="form.roleName" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" /></el-form-item>
        <el-form-item label="权限">
          <el-select v-model="form.perms" multiple filterable allow-create default-first-option style="width: 100%">
            <el-option v-for="p in permOptions" :key="p" :label="p" :value="p" />
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
import { pageRoles, rolePerms, createRole, updateRole, deleteRole } from '@/api/system'
import type { SysRole } from '@/api/system'

const permOptions = [
  '*', 'barn:view', 'cow:list', 'cow:detail', 'event:list',
  'task:list', 'task:handle', 'device:list', 'system:user', 'system:role'
]

const rows = ref<SysRole[]>([])
const permMap = reactive<Record<number, string[]>>({})
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const dialogVisible = ref(false)
const form = reactive<any>({})

async function load() {
  loading.value = true
  try {
    const res = await pageRoles({ page: page.value, size: 10 })
    rows.value = res.records
    total.value = res.total
    for (const r of res.records) {
      permMap[r.id] = await rolePerms(r.id)
    }
  } finally {
    loading.value = false
  }
}

async function openEdit(row?: SysRole) {
  Object.assign(form, { id: undefined, roleCode: '', roleName: '', description: '', perms: [] }, row)
  if (row) {
    form.perms = permMap[row.id] || await rolePerms(row.id)
  }
  dialogVisible.value = true
}

async function onSave() {
  if (form.id) {
    await updateRole(form.id, form)
  } else {
    await createRole(form)
  }
  ElMessage.success('已保存')
  dialogVisible.value = false
  load()
}

async function onDelete(row: SysRole) {
  await deleteRole(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>

<template>
  <el-card shadow="never">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="用户名" clearable style="width: 200px" @change="load" />
      <el-button type="primary" @click="load">查询</el-button>
      <el-button type="success" @click="openEdit()">新增用户</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="nickname" label="姓名" />
      <el-table-column prop="phone" label="电话" width="140" />
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'ENABLED' ? 'success' : 'info'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createTime" label="创建时间" width="170" />
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-popconfirm title="确认删除该用户？" @confirm="onDelete(row)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="pager" layout="total, prev, pager, next" :total="total"
      :page-size="10" :current-page="page" @current-change="(p: number) => { page = p; load() }" />

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑用户' : '新增用户'" width="440px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="!!form.id" />
        </el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.nickname" /></el-form-item>
        <el-form-item label="电话"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item :label="form.id ? '重置密码' : '密码'">
          <el-input v-model="form.password" type="password" show-password
            :placeholder="form.id ? '留空则不修改' : '默认 Init@123'" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.roleIds" multiple style="width: 100%">
            <el-option v-for="r in roles" :key="r.id" :label="r.roleName" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" v-if="form.id">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="ENABLED" value="ENABLED" />
            <el-option label="DISABLED" value="DISABLED" />
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
import { pageUsers, createUser, updateUser, deleteUser, allRoles } from '@/api/system'
import type { SysUser, SysRole } from '@/api/system'

const rows = ref<SysUser[]>([])
const roles = ref<SysRole[]>([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const loading = ref(false)
const dialogVisible = ref(false)
const form = reactive<any>({})

async function load() {
  loading.value = true
  try {
    const res = await pageUsers({ page: page.value, size: 10, keyword: keyword.value || undefined })
    rows.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function openEdit(row?: SysUser) {
  Object.assign(form, { id: undefined, username: '', nickname: '', phone: '', password: '', roleIds: [], status: 'ENABLED' }, row)
  dialogVisible.value = true
}

async function onSave() {
  if (form.id) {
    await updateUser(form.id, form)
  } else {
    await createUser(form)
  }
  ElMessage.success('已保存')
  dialogVisible.value = false
  load()
}

async function onDelete(row: SysUser) {
  await deleteUser(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => {
  roles.value = await allRoles()
  load()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>

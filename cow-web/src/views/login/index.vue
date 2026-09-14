<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2 class="title">单牛数字孪生与健康繁殖任务管理平台</h2>
      <p class="subtitle">奶牛数字孪生系统 · 首场验证版（20号牛棚）</p>
      <el-form :model="form" @keyup.enter="onLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名：admin / vet / breeder" :prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" show-password placeholder="密码" :prefix-icon="Lock" />
        </el-form-item>
        <el-button type="primary" class="btn" :loading="loading" @click="onLogin">登 录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const loading = ref(false)
const form = reactive({ username: 'admin', password: '' })

async function onLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    await userStore.fetchProfile()
    router.push((route.query.redirect as string) || '/dashboard')
  } catch {
    // request 拦截器已提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100%; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #1f3a5f 0%, #2e6b4f 100%);
}
.login-card { width: 400px; }
.title { text-align: center; font-size: 18px; margin: 0 0 4px; }
.subtitle { text-align: center; color: #999; font-size: 12px; margin: 0 0 20px; }
.btn { width: 100%; }
</style>

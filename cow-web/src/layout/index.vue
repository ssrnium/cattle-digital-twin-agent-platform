<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">🐄 数字孪生牧场</div>
      <el-menu :default-active="$route.path" router background-color="#001529" text-color="#a6adb4"
        active-text-color="#ffffff">
        <el-menu-item v-for="item in visibleMenus" :key="item.path" :index="'/' + item.path">
          <el-icon>
            <component :is="icons[item.meta?.icon as string] || icons.Menu" />
          </el-icon>
          <span>{{ item.meta?.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="title">单牛数字孪生与健康繁殖任务管理平台 · 20号牛棚</span>
        <el-dropdown @command="onCommand">
          <span class="user">
            {{ userStore.nickname || userStore.username }}
            <el-icon><component :is="icons.ArrowDown" /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Odometer, MapLocation, Files, Bell, Tickets, Monitor, User, UserFilled, Menu, ArrowDown,
  ChatDotRound
} from '@element-plus/icons-vue'
import { menuRoutes } from '@/router'
import { useUserStore } from '@/stores/user'

const icons: Record<string, any> = {
  Odometer, MapLocation, Files, Bell, Tickets, Monitor, User, UserFilled, Menu, ArrowDown,
  ChatDotRound
}

const router = useRouter()
const userStore = useUserStore()

// 按权限过滤菜单
const visibleMenus = computed(() => {
  const children = menuRoutes[0]?.children || []
  return children.filter((r) => {
    if (r.meta?.hidden) return false
    const perm = r.meta?.perm as string | undefined
    return !perm || userStore.hasPerm(perm)
  })
})

function onCommand(cmd: string) {
  if (cmd === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.layout { height: 100%; }
.aside { background: #001529; }
.logo {
  color: #fff; font-weight: 600; font-size: 16px;
  height: 60px; display: flex; align-items: center; justify-content: center;
}
.aside :deep(.el-menu) { border-right: none; }
.header {
  background: #fff; display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid #eee;
}
.title { font-size: 15px; color: #333; }
.user { cursor: pointer; display: flex; align-items: center; gap: 4px; }
.main { background: #f0f2f5; }
</style>

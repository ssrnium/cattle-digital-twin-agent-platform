<template>
  <div class="shell" :class="{ collapsed }">
    <aside class="sidebar">
      <div class="brand">
        <span class="logo">🐄<b v-if="!collapsed">数字孪生牧场</b></span>
        <button class="collapse-btn" @click="collapsed = !collapsed">
          <el-icon><component :is="icons.Menu" /></el-icon>
        </button>
      </div>
      <div v-if="!collapsed" class="farm-switch">
        <span class="status-dot"></span>
        <div>
          <div class="farm-name">20号牛棚 · 首场验证</div>
          <div class="farm-meta">ONLINE · REALTIME</div>
        </div>
      </div>
      <!-- 权限过滤菜单：visibleMenus 按 meta.perm 过滤，逻辑保持不变 -->
      <el-menu :default-active="$route.path" router :collapse="collapsed" class="nav-menu"
        background-color="transparent" text-color="#80a0a8" active-text-color="#d5f4f4">
        <el-menu-item v-for="item in visibleMenus" :key="item.path" :index="'/' + item.path">
          <el-icon>
            <component :is="icons[item.meta?.icon as string] || icons.Menu" />
          </el-icon>
          <template #title>{{ item.meta?.title }}</template>
        </el-menu-item>
      </el-menu>
      <div v-if="!collapsed" class="sidebar-foot">
        <div class="agent-status" @click="router.push('/assistant')">
          <span></span>
          <div>
            <b>牧场 Agent</b>
            <small>{{ agentStatusText }}</small>
          </div>
          <i>●</i>
        </div>
        <div class="version">COW-TWIN · OPS CONSOLE <span>v1.0</span></div>
      </div>
    </aside>
    <main class="main">
      <header class="topbar">
        <div>
          <div class="eyebrow">{{ currentTitle }} / BARN-20 DIGITAL TWIN</div>
          <h1>{{ currentTitle }}</h1>
        </div>
        <div class="top-actions">
          <div class="live"><span></span>实时数据已连接</div>
          <el-dropdown @command="onCommand">
            <span class="user">
              <span class="avatar">{{ (userStore.nickname || userStore.username || '?').slice(0, 1) }}</span>
              {{ userStore.nickname || userStore.username }}
              <el-icon><component :is="icons.ArrowDown" /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      <div class="content">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Odometer, MapLocation, Files, Bell, Tickets, Monitor, User, UserFilled, Menu, ArrowDown,
  ChatDotRound
} from '@element-plus/icons-vue'
import { menuRoutes } from '@/router'
import { useUserStore } from '@/stores/user'
import { agentSessions } from '@/api/agent'

const icons: Record<string, any> = {
  Odometer, MapLocation, Files, Bell, Tickets, Monitor, User, UserFilled, Menu, ArrowDown,
  ChatDotRound
}

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const collapsed = ref(false)
const agentStatusText = ref('Orchestrator ready')

// 按权限过滤菜单
const visibleMenus = computed(() => {
  const children = menuRoutes[0]?.children || []
  return children.filter((r) => {
    if (r.meta?.hidden) return false
    const perm = r.meta?.perm as string | undefined
    return !perm || userStore.hasPerm(perm)
  })
})

const currentTitle = computed(() => (route.meta?.title as string) || '总览看板')

// 读取真实 agent 会话接口做底卡装饰；无权限或服务未起时静默降级为静态文案
async function loadAgentStatus() {
  try {
    const resp = await agentSessions(true)
    const pending = resp.sessions.filter((s) => s.pending_confirmation).length
    agentStatusText.value = pending > 0
      ? `${resp.sessions.length} 个会话 · ${pending} 待审批`
      : `${resp.sessions.length} 个活跃会话 · ready`
  } catch {
    /* agent 服务不可用或无权限时保持静态文案 */
  }
}

function onCommand(cmd: string) {
  if (cmd === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}

onMounted(loadAgentStatus)
</script>

<style scoped>
.shell {
  display: flex; height: 100vh; overflow: hidden;
  background: radial-gradient(circle at 83% -10%, #12343d 0, #07131c 36%, #061019 68%);
}
.sidebar {
  width: 232px; flex: none; padding: 20px 14px 16px;
  background: rgba(5, 16, 24, 0.82);
  border-right: 1px solid rgba(105, 194, 206, 0.12);
  display: flex; flex-direction: column; transition: width 0.25s;
}
.shell.collapsed .sidebar { width: 76px; }
.brand {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 7px 20px;
}
.logo { font-size: 18px; display: flex; align-items: center; gap: 8px; }
.logo b { font-size: 15px; color: #e7f4f6; letter-spacing: 0.02em; }
.collapse-btn { border: 0; background: transparent; color: #6f939d; cursor: pointer; }
.farm-switch {
  margin: 0 2px 20px; padding: 12px; border: 1px solid #1b3b45; border-radius: 11px;
  display: flex; align-items: center; gap: 9px;
}
.status-dot, .live span, .agent-status > span {
  width: 7px; height: 7px; border-radius: 50%;
  background: #62e8b0; box-shadow: 0 0 11px #62e8b0; flex: none;
}
.farm-name { font-size: 12px; font-weight: 600; color: #d8edf0; }
.farm-meta { font-size: 9px; letter-spacing: 0.13em; color: #67909b; margin-top: 4px; }
.nav-menu { border-right: none; flex: 1; }
.nav-menu :deep(.el-menu-item) {
  border-radius: 10px; margin-bottom: 6px; height: 44px;
  border: 1px solid transparent;
}
.nav-menu :deep(.el-menu-item:hover) { background: #10242e; color: #c7edf0; }
.nav-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, #11323d, #0d242e);
  border-color: #1d5861; color: #d5f4f4;
  box-shadow: inset 2px 0 #5de3df;
}
.sidebar-foot { margin-top: auto; }
.agent-status {
  display: flex; align-items: center; gap: 9px; padding: 12px; cursor: pointer;
  border-radius: 10px; background: #0d242b; border: 1px solid #164952;
}
.agent-status > span { background: #52d8df; box-shadow: 0 0 9px #52d8df; }
.agent-status b { display: block; font-size: 11px; color: #d8edf0; }
.agent-status small { display: block; color: #75aab0; font-size: 9px; margin-top: 3px; }
.agent-status i { font-style: normal; color: #52d8df; margin-left: auto; font-size: 9px; }
.version { font-size: 8px; color: #50727c; letter-spacing: 0.12em; margin: 16px 4px 0; }
.version span { float: right; }
.main { min-width: 0; flex: 1; display: flex; flex-direction: column; }
.topbar {
  height: 88px; padding: 22px 32px 16px;
  display: flex; align-items: flex-start; justify-content: space-between;
  border-bottom: 1px solid rgba(105, 194, 206, 0.08);
}
h1 { font-size: 21px; line-height: 1; margin: 8px 0 0; letter-spacing: -0.02em; color: #e7f4f6; }
.top-actions { display: flex; align-items: center; gap: 22px; }
.live { font-size: 11px; color: #77a4aa; display: flex; align-items: center; gap: 7px; }
.user { cursor: pointer; display: flex; align-items: center; gap: 9px; color: #d8edf0; font-size: 12px; }
.avatar {
  width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center;
  background: linear-gradient(145deg, #2b8f92, #244d77); font-size: 12px; color: #eaffff;
}
.content { flex: 1; overflow: auto; padding: 26px 32px 36px; }
</style>

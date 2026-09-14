import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

export const menuRoutes: RouteRecordRaw[] = [
  {
    path: '',
    component: () => import('@/layout/index.vue'),
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/dashboard/index.vue'), meta: { title: '总览看板', icon: 'Odometer' } },
      { path: 'barn', name: 'Barn', component: () => import('@/views/barn/index.vue'), meta: { title: '牛棚孪生图', icon: 'MapLocation', perm: 'barn:view' } },
      { path: 'cow', name: 'CowList', component: () => import('@/views/cow/list/index.vue'), meta: { title: '牛只档案', icon: 'Files', perm: 'cow:list' } },
      { path: 'cow/detail/:cowId', name: 'CowDetail', component: () => import('@/views/cow/detail/index.vue'), meta: { title: '单牛详情', hidden: true } },
      { path: 'event', name: 'Event', component: () => import('@/views/event/index.vue'), meta: { title: '事件流', icon: 'Bell', perm: 'event:list' } },
      { path: 'task', name: 'Task', component: () => import('@/views/task/index.vue'), meta: { title: '工单看板', icon: 'Tickets', perm: 'task:list' } },
      { path: 'device', name: 'Device', component: () => import('@/views/device/index.vue'), meta: { title: '设备状态', icon: 'Monitor', perm: 'device:list' } },
      { path: 'assistant', name: 'Assistant', component: () => import('@/views/assistant/index.vue'), meta: { title: 'AI 助手', icon: 'ChatDotRound', perm: 'agent:chat' } },
      { path: 'system/user', name: 'SysUser', component: () => import('@/views/system/user/index.vue'), meta: { title: '用户管理', icon: 'User', perm: 'system:user' } },
      { path: 'system/role', name: 'SysRole', component: () => import('@/views/system/role/index.vue'), meta: { title: '角色管理', icon: 'UserFilled', perm: 'system:role' } }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'Login', component: () => import('@/views/login/index.vue') },
    { path: '/', redirect: '/dashboard', children: [] },
    ...menuRoutes,
    { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('@/views/error/404.vue') }
  ]
})

router.beforeEach(async (to) => {
  const store = useUserStore()
  if (to.path === '/login') {
    return true
  }
  if (!store.token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (!store.loaded) {
    try {
      await store.fetchProfile()
    } catch {
      store.logout()
      return { path: '/login' }
    }
  }
  return true
})

export default router

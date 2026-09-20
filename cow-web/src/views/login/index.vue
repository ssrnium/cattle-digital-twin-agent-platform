<template>
  <div class="login-page">
    <div class="login-noise"></div>
    <div class="login-grid-bg"></div>
    <div class="login-left">
      <div class="brand"><span class="glyph">🐄</span><b>数字孪生牧场</b></div>
      <div class="hero-copy">
        <div class="eyebrow">AI-POWERED FARM DIGITAL TWIN</div>
        <h1>让每一头奶牛，<br /><span>都被理解。</span></h1>
        <p>单牛数字孪生与健康繁殖任务管理平台，将牛棚环境、IoT 设备与个体健康数据，汇聚成一个可感知、可推理、可行动的数字孪生系统。</p>
        <div class="signal-list">
          <div><i>✦</i><b>实时感知</b><span>MQTT 设备接入 · 单牛孪生体状态同步</span></div>
          <div><i>⌁</i><b>智能推理</b><span>Agent + 大模型 + 行为识别模型</span></div>
          <div><i>↗</i><b>决策执行</b><span>从异常信号到繁殖/健康工单的闭环</span></div>
        </div>
      </div>
      <div class="login-foot">BARN-20 PILOT · PRIVATE CLOUD <span>SYS STATUS <i></i> OPERATIONAL</span></div>
    </div>

    <div class="login-card">
      <div class="card-top">
        <div class="eyebrow">SECURE ACCESS / 01</div>
        <h2>欢迎回到牧场控制中心</h2>
        <p>使用平台账号进入实时运营空间（admin / vet / breeder）。</p>
      </div>
      <el-form :model="form" @keyup.enter="onLogin">
        <label class="field-label">用户名</label>
        <el-input v-model="form.username" placeholder="用户名：admin / vet / breeder" :prefix-icon="User" />
        <label class="field-label">访问密码</label>
        <el-input v-model="form.password" type="password" show-password placeholder="密码" :prefix-icon="Lock" />
        <el-button type="primary" class="login-btn" :loading="loading" @click="onLogin">
          进入控制中心 <el-icon><ArrowRight /></el-icon>
        </el-button>
      </el-form>
      <div class="security-note"><el-icon><Lock /></el-icon> 你的连接已由企业级 TLS 加密保护</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, ArrowRight } from '@element-plus/icons-vue'
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
  height: 100vh; min-height: 680px; display: flex; position: relative;
  overflow: hidden; background: #061018; color: #e2f3f3;
}
.login-noise {
  position: absolute; inset: 0; opacity: 0.2;
  background-image: radial-gradient(#64d8dd 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: linear-gradient(90deg, #000 0, transparent 76%);
}
.login-grid-bg {
  position: absolute; inset: 0; opacity: 0.22;
  background:
    linear-gradient(90deg, transparent 0 19.8%, #1b515744 20%, transparent 20.1% 39.8%, #1b515744 40%, transparent 40.1% 59.8%, #1b515744 60%, transparent 60.1% 79.8%, #1b515744 80%, transparent 80.1%),
    linear-gradient(0deg, transparent 0 24.8%, #1b515744 25%, transparent 25.1% 49.8%, #1b515744 50%, transparent 50.1% 74.8%, #1b515744 75%, transparent 75.1%);
}
.login-left { width: 59%; padding: 42px 8%; position: relative; display: flex; flex-direction: column; }
.brand { display: flex; align-items: center; gap: 10px; }
.brand .glyph { font-size: 22px; }
.brand b { font-size: 15px; letter-spacing: 0.04em; }
.hero-copy { margin: auto 0; max-width: 510px; }
.hero-copy h1 { font-size: 52px; line-height: 1.16; letter-spacing: -0.06em; margin: 16px 0 20px; }
.hero-copy h1 span { color: #67dcd7; }
.hero-copy p { font-size: 14px; line-height: 1.8; color: #7fa0a7; max-width: 460px; }
.signal-list { display: grid; gap: 17px; margin-top: 38px; }
.signal-list div { display: grid; grid-template-columns: 27px 74px 1fr; align-items: center; gap: 10px; font-size: 11px; }
.signal-list i {
  width: 25px; height: 25px; border-radius: 7px; background: #123e46;
  color: #66dcda; display: grid; place-items: center; font-style: normal;
}
.signal-list b { font-size: 11px; }
.signal-list span { color: #648890; font-size: 10px; }
.login-foot { font-size: 9px; color: #52767e; letter-spacing: 0.12em; }
.login-foot > span { float: right; }
.login-foot i { display: inline-block; width: 5px; height: 5px; border-radius: 50%; background: #61dcb0; margin: 0 4px; }
.login-card {
  width: 41%; max-width: 500px; margin: auto 7% auto 0;
  background: rgba(13, 30, 40, 0.82); border: 1px solid #2b5961; border-radius: 15px;
  padding: 37px 42px; box-shadow: 0 22px 70px #00000055, 0 0 50px #2a919422;
  backdrop-filter: blur(16px);
}
.card-top h2 { font-size: 23px; letter-spacing: -0.04em; margin: 13px 0 8px; }
.card-top p { font-size: 11px; color: #74949b; margin: 0 0 10px; }
.field-label { display: block; font-size: 10px; color: #8dacb1; margin: 17px 0 7px; }
.login-btn {
  height: 43px; width: 100%; margin-top: 26px; border: 0; border-radius: 7px;
  background: linear-gradient(100deg, #2a9697, #348fbb); color: #eaffff;
  font-size: 13px; letter-spacing: 0.06em;
  box-shadow: 0 8px 22px #238b8b44;
}
.login-btn:hover { opacity: 0.92; }
.login-btn .el-icon { margin-left: 6px; }
.security-note { text-align: center; color: #4f747b; font-size: 9px; margin-top: 24px; }
.security-note .el-icon { vertical-align: middle; margin-right: 3px; }
.login-card :deep(.el-input__wrapper) {
  background: #091b24; box-shadow: 0 0 0 1px #27505a inset; border-radius: 7px;
}
.login-card :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px #4cb6b6 inset; }
.login-card :deep(.el-input__inner) { color: #d7eff0; }
@media (max-width: 1100px) {
  .login-left { padding-left: 5%; }
  .login-card { margin-right: 4%; }
  .hero-copy h1 { font-size: 42px; }
}
</style>

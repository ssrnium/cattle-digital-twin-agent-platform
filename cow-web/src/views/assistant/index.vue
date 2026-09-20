<template>
  <div class="assistant-page">
    <el-card shadow="never" class="sessions-card">
      <template #header>
        <div class="card-header">
          <span>会话</span>
          <el-button size="small" type="primary" @click="newSession">新会话</el-button>
        </div>
      </template>
      <div v-if="sessions.length === 0" class="empty">暂无会话</div>
      <div v-for="s in sessions" :key="s.session_id" class="session-item"
        :class="{ active: s.session_id === sessionId }" @click="switchSession(s.session_id)">
        <span class="sid">{{ s.session_id }}</span>
        <el-tag v-if="s.pending_confirmation" type="danger" size="small">待审批</el-tag>
      </div>
    </el-card>

    <el-card shadow="never" class="chat-card">
      <div ref="msgListRef" class="msg-list">
        <div v-if="messages.length === 0" class="empty">
          向牧场智能体提问，例如：「COW-0042 今天什么情况？」
        </div>
        <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
          <div class="message-avatar">{{ m.role === 'assistant' ? 'AI' : '我' }}</div>
          <div class="bubble">
            <div class="content">{{ m.content }}</div>
            <div v-if="m.trace && m.trace.length" class="tool-trace">
              <div class="trace-title"><span>Agent 执行轨迹</span><small class="mono">{{ m.trace.length }} 次工具调用</small></div>
              <div v-for="(t, j) in m.trace" :key="j" class="trace-item">
                <div class="trace-step">
                  <i>✓</i><span class="tool-name mono">{{ t.tool }}</span>
                  <el-tag v-if="t.tool === 'create_work_order'" type="danger" size="small">写操作</el-tag>
                  <span class="done">done</span>
                </div>
                <details class="trace-detail">
                  <summary>参数与结果</summary>
                  <pre class="mono">{{ JSON.stringify(t.arguments, null, 2) }}</pre>
                  <pre class="trace-result mono">{{ t.result_preview }}</pre>
                </details>
              </div>
            </div>
            <div v-if="m.tokens" class="tokens mono">tokens: {{ m.tokens.input }}↑ / {{ m.tokens.output }}↓</div>
          </div>
        </div>
        <div v-if="sending" class="msg-row assistant">
          <div class="message-avatar">AI</div>
          <div class="bubble thinking">
            <span></span><span></span><span></span> 正在调用工具…（如需审批写操作会弹出确认框）
          </div>
        </div>
      </div>
      <div class="input-bar">
        <el-input v-model="input" type="textarea" :rows="2" placeholder="输入消息，Enter 发送（Shift+Enter 换行）"
          @keydown.enter.exact.prevent="send" />
        <el-button type="primary" :loading="sending" :disabled="!input.trim()" @click="send">发送</el-button>
      </div>
    </el-card>

    <!-- 写操作确认：展示工具名 / 参数 / 说明，批准或拒绝 -->
    <el-dialog v-model="confirmVisible" title="智能体请求执行写操作" width="520px" :close-on-click-modal="false"
      :close-on-press-escape="false" :show-close="false">
      <template v-if="pending">
        <p>智能体请求调用写工具 <el-tag type="danger">{{ pending.tool || '（非领域工具）' }}</el-tag>，请审批：</p>
        <pre class="confirm-args">{{ JSON.stringify(pending.arguments, null, 2) }}</pre>
        <p class="confirm-note">说明：{{ pending.tool ? pending.message : pending.message }}</p>
        <p class="confirm-tip">120 秒内未审批将自动拒绝。</p>
      </template>
      <template #footer>
        <el-button type="danger" @click="resolveConfirm(false)">拒绝</el-button>
        <el-button type="primary" @click="resolveConfirm(true)">批准执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { agentChat, agentConfirm, agentSessions } from '@/api/agent'
import type { AgentSession, ChatResponse, PendingConfirmation, ToolTrace } from '@/api/agent'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  trace?: ToolTrace[]
  tokens?: { input: number; output: number }
}

const sessions = ref<AgentSession[]>([])
const sessionId = ref<string | null>(null)
const messages = ref<ChatMessage[]>([])
const input = ref('')
const sending = ref(false)
const confirmVisible = ref(false)
const pending = ref<PendingConfirmation | null>(null)
const msgListRef = ref<HTMLElement>()
let pollTimer: number | undefined

// 会话列表轮询：chat 阻塞期间发现 pending_confirmation 即弹审批框
async function refreshSessions() {
  try {
    const resp = await agentSessions()
    sessions.value = resp.sessions
    const current = resp.sessions.find((s) => s.session_id === sessionId.value)
    if (current?.pending_confirmation) {
      pending.value = current.pending_confirmation
      confirmVisible.value = true
    }
  } catch {
    /* 轮询失败不打断用户 */
  }
}

function newSession() {
  sessionId.value = null
  messages.value = []
}

function switchSession(sid: string) {
  sessionId.value = sid
  messages.value = []
  ElMessage.info('已切换到会话 ' + sid + '（历史消息在服务端上下文中续接）')
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value) return
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  sending.value = true
  scrollBottom()
  try {
    const resp: ChatResponse = await agentChat(sessionId.value, text)
    sessionId.value = resp.session_id
    messages.value.push({
      role: 'assistant',
      content: resp.reply || '（无回复）',
      trace: resp.tool_trace,
      tokens: resp.tokens
    })
    refreshSessions()
  } catch {
    messages.value.push({ role: 'assistant', content: '（本次调用失败，请检查 cow-agent 服务或稍后重试）' })
  } finally {
    sending.value = false
    scrollBottom()
  }
}

async function resolveConfirm(approved: boolean) {
  if (!sessionId.value) return
  try {
    await agentConfirm(sessionId.value, approved)
    ElMessage.success(approved ? '已批准，智能体继续执行' : '已拒绝')
  } catch {
    /* 超时已被服务端自动拒绝 */
  }
  confirmVisible.value = false
  pending.value = null
}

function scrollBottom() {
  nextTick(() => {
    if (msgListRef.value) msgListRef.value.scrollTop = msgListRef.value.scrollHeight
  })
}

onMounted(() => {
  refreshSessions()
  pollTimer = window.setInterval(refreshSessions, 2000)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})
</script>

<style scoped>
.assistant-page { display: flex; gap: 14px; height: calc(100vh - 176px); }
.sessions-card { width: 240px; flex-shrink: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.session-item {
  padding: 8px 10px; border-radius: 8px; cursor: pointer; display: flex;
  justify-content: space-between; align-items: center; gap: 6px;
  border: 1px solid transparent; color: #a9c6cc;
}
.session-item:hover { background: #10242e; }
.session-item.active {
  background: linear-gradient(90deg, #11323d, #0d242e);
  border-color: #1d5861; color: #d5f4f4; box-shadow: inset 2px 0 #5de3df;
}
.sid { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; overflow: hidden; text-overflow: ellipsis; }
.chat-card { flex: 1; display: flex; flex-direction: column; }
.chat-card :deep(.el-card__body) { display: flex; flex-direction: column; height: 100%; }
.msg-list { flex: 1; overflow-y: auto; padding: 8px; }
.empty { color: #66848b; text-align: center; padding: 24px 0; font-size: 12px; }
.msg-row { display: flex; gap: 10px; margin-bottom: 16px; }
.msg-row.user { flex-direction: row-reverse; }
.message-avatar {
  width: 26px; height: 26px; border-radius: 8px; background: #164650;
  display: grid; place-items: center; flex: none; color: #b8f7f4; font-size: 9px;
}
.msg-row.user .message-avatar { background: #37516b; color: #d3e7ff; }
.bubble {
  max-width: 72%; padding: 11px 13px; border-radius: 4px 11px 11px 11px;
  background: #12303a; color: #b9d7db; font-size: 12px; line-height: 1.65;
  white-space: pre-wrap; word-break: break-word;
}
.msg-row.user .bubble { background: #1b3f51; border-radius: 11px 4px 11px 11px; color: #dbedf3; }
.tool-trace { margin-top: 12px; border-top: 1px solid #285762; padding-top: 10px; }
.trace-title { display: flex; justify-content: space-between; color: #86d5d3; font-size: 10px; margin-bottom: 8px; }
.trace-title small { color: #56838a; }
.trace-item { margin-bottom: 4px; }
.trace-step { display: flex; align-items: center; gap: 7px; color: #91b4b8; font-size: 10px; line-height: 1.9; }
.trace-step i { font-style: normal; color: #67dcaf; }
.trace-step .tool-name { color: #c7e6e8; }
.trace-step .done { margin-left: auto; color: #579c8a; font-size: 9px; }
.trace-detail summary {
  cursor: pointer; color: #6da5ab; font-size: 9px; margin-left: 18px; user-select: none;
}
.trace-detail pre {
  background: #0b1d26; border: 1px solid #17333c; border-radius: 6px;
  padding: 8px; font-size: 11px; max-height: 180px; overflow: auto; color: #a9c6cc;
}
.trace-result { color: #7fa0a7; }
.tokens { margin-top: 8px; font-size: 10px; color: #5e8289; }
.thinking { display: flex; gap: 4px; align-items: center; color: #80a5aa; font-size: 11px; }
.thinking span { width: 4px; height: 4px; background: #75d9ce; border-radius: 50%; animation: blink 1s infinite; }
.thinking span:nth-child(2) { animation-delay: 0.15s; }
.thinking span:nth-child(3) { animation-delay: 0.3s; }
@keyframes blink { 50% { opacity: 0.2; transform: translateY(-2px); } }
.input-bar { display: flex; gap: 8px; align-items: flex-end; padding-top: 8px; }
.confirm-args {
  background: #0b1d26; border: 1px solid #17333c; border-radius: 6px;
  padding: 8px; max-height: 240px; overflow: auto; color: #a9c6cc;
}
.confirm-note { color: #7fa0a7; word-break: break-all; }
.confirm-tip { color: #f3c66b; font-size: 13px; }
</style>

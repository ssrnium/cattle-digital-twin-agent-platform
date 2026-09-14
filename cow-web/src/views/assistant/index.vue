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
          <div class="bubble">
            <div class="content">{{ m.content }}</div>
            <el-collapse v-if="m.trace && m.trace.length" class="trace">
              <el-collapse-item :title="`工具调用轨迹（${m.trace.length} 次）`">
                <div v-for="(t, j) in m.trace" :key="j" class="trace-item">
                  <div class="trace-head">
                    <el-tag size="small" :type="t.tool === 'create_work_order' ? 'danger' : 'info'">
                      {{ t.tool }}
                    </el-tag>
                  </div>
                  <pre>{{ JSON.stringify(t.arguments, null, 2) }}</pre>
                  <pre class="trace-result">{{ t.result_preview }}</pre>
                </div>
              </el-collapse-item>
            </el-collapse>
            <div v-if="m.tokens" class="tokens">tokens: {{ m.tokens.input }}↑ / {{ m.tokens.output }}↓</div>
          </div>
        </div>
        <div v-if="sending" class="msg-row assistant">
          <div class="bubble"><span class="content">思考中…（如需审批写操作会弹出确认框）</span></div>
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
.assistant-page { display: flex; gap: 12px; height: calc(100vh - 120px); }
.sessions-card { width: 220px; flex-shrink: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.session-item {
  padding: 8px; border-radius: 4px; cursor: pointer; display: flex;
  justify-content: space-between; align-items: center;
}
.session-item:hover { background: #f5f7fa; }
.session-item.active { background: #ecf5ff; }
.sid { font-family: monospace; font-size: 13px; }
.chat-card { flex: 1; display: flex; flex-direction: column; }
.chat-card :deep(.el-card__body) { display: flex; flex-direction: column; height: 100%; }
.msg-list { flex: 1; overflow-y: auto; padding: 8px; }
.empty { color: #999; text-align: center; padding: 24px 0; }
.msg-row { display: flex; margin-bottom: 12px; }
.msg-row.user { justify-content: flex-end; }
.msg-row.assistant { justify-content: flex-start; }
.bubble {
  max-width: 72%; padding: 10px 12px; border-radius: 8px;
  background: #f4f4f5; white-space: pre-wrap; word-break: break-word;
}
.msg-row.user .bubble { background: #d9ecff; }
.trace { margin-top: 8px; }
.trace-item pre {
  background: #fafafa; border: 1px solid #eee; border-radius: 4px;
  padding: 6px; font-size: 12px; max-height: 160px; overflow: auto;
}
.trace-result { color: #666; }
.tokens { margin-top: 6px; font-size: 12px; color: #999; }
.input-bar { display: flex; gap: 8px; align-items: flex-end; padding-top: 8px; }
.confirm-args { background: #fafafa; border: 1px solid #eee; border-radius: 4px; padding: 8px; max-height: 240px; overflow: auto; }
.confirm-note { color: #666; word-break: break-all; }
.confirm-tip { color: #e6a23c; font-size: 13px; }
</style>

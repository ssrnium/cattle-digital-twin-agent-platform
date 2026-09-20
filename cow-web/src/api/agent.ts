import { get, post } from '@/utils/request'

export interface ToolTrace {
  tool: string
  arguments: Record<string, any>
  result_preview: string
}

export interface ChatResponse {
  session_id: string
  reply: string
  tokens: { input: number; output: number }
  tool_trace: ToolTrace[]
}

export interface PendingConfirmation {
  tool: string
  arguments: Record<string, any>
  message: string
  since: number
}

export interface AgentSession {
  session_id: string
  created_at: number
  last_active: number
  pending_confirmation: PendingConfirmation | null
}

// chat 可能因写操作确认 park 最多 120s，单独放宽超时
export function agentChat(sessionId: string | null, message: string) {
  return post<ChatResponse>('/agent/chat', { session_id: sessionId, message }, { timeout: 160000 })
}

export function agentConfirm(sessionId: string, approved: boolean) {
  return post<{ ok: boolean; approved: boolean }>('/agent/confirm', { session_id: sessionId, approved })
}

export function agentSessions(silent = false) {
  return get<{ sessions: AgentSession[] }>('/agent/sessions', undefined, { silent })
}

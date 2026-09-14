import { get, post, put, del } from '@/utils/request'
import type { PageResult } from '@/utils/request'

export interface CowProfile {
  id: number
  cowId: string
  earTag: string
  barnId: string
  zone: string
  status: string
  createTime: string
}

export interface CowTimeline {
  id: number
  cowId: string
  eventId: string
  eventType: string
  title: string
  detail: Record<string, any>
  stateNature: 'MEASURED' | 'INFERRED' | 'MANUAL'
  eventTime: string
  createTime: string
}

export interface TwinState {
  cowId: string
  state: {
    posture?: string
    zone?: string
    health_status?: string
    estrus_status?: string
    [key: string]: any
  }
  stateNature: string
  sourceEventId: string
  eventTime: string
  version: number
  updatedAt: string
}

export function pageCows(params: { page: number; size: number; keyword?: string; zone?: string }) {
  return get<PageResult<CowProfile>>('/cows', params)
}

export function createCow(data: Partial<CowProfile>) {
  return post<CowProfile>('/cows', data)
}

export function updateCow(id: number, data: Partial<CowProfile>) {
  return put<CowProfile>(`/cows/${id}`, data)
}

export function deleteCow(id: number) {
  return del(`/cows/${id}`)
}

export function cowDetail(cowId: string) {
  return get<{ profile: CowProfile; twinState: TwinState | null }>(`/cows/${cowId}`)
}

export function cowTimeline(cowId: string, limit = 100) {
  return get<CowTimeline[]>(`/cows/${cowId}/timeline`, { limit })
}

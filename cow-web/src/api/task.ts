import { get, post } from '@/utils/request'
import type { PageResult } from '@/utils/request'

export interface WorkOrder {
  id: number
  orderNo: string
  type: 'BREEDING_REVIEW' | 'VET_CHECK' | 'DEVICE_REPAIR'
  cowId: string
  deviceId: string
  sourceEventId: string
  state: 'NEW' | 'DISPATCHED' | 'PROCESSING' | 'PENDING_REVIEW' | 'CLOSED' | 'CANCELLED'
  priority: string
  assigneeId: number
  description: string
  reviewResult: string
  reviewedBy: string
  reviewedAt: string
  version: number
  createTime: string
  updateTime: string
}

export function pageTasks(params: {
  page: number
  size: number
  state?: string
  type?: string
  assigneeId?: number
}) {
  return get<PageResult<WorkOrder>>('/tasks', params)
}

export function taskDetail(id: number) {
  return get<WorkOrder>(`/tasks/${id}`)
}

export function assignTask(id: number, assigneeId: number, version: number) {
  return post<WorkOrder>(`/tasks/${id}/assign`, { assigneeId, version })
}

export function startTask(id: number, version: number) {
  return post<WorkOrder>(`/tasks/${id}/start`, { version })
}

export function submitReview(id: number, result: string, version: number) {
  return post<WorkOrder>(`/tasks/${id}/submit-review`, { result, version })
}

export function reviewTask(id: number, approved: boolean, reviewResult: string, version: number) {
  return post<WorkOrder>(`/tasks/${id}/review`, { approved, reviewResult, version })
}

export function cancelTask(id: number, reason: string, version: number) {
  return post<WorkOrder>(`/tasks/${id}/cancel`, { reason, version })
}

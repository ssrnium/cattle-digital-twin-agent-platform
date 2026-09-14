import { get } from '@/utils/request'
import type { PageResult } from '@/utils/request'

export interface UnifiedEvent {
  id: number
  schemaVersion: string
  tenantId: string
  farmId: string
  eventId: string
  cowId: string
  deviceId: string
  eventType: string
  eventTime: string
  ingestTime: string
  quality: string
  confidence: number
  modelVersion: string
  evidenceRef: string
  raw: Record<string, any>
}

export function pageEvents(params: {
  page: number
  size: number
  eventType?: string
  cowId?: string
  deviceId?: string
}) {
  return get<PageResult<UnifiedEvent>>('/events', params)
}

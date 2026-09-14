import { get } from '@/utils/request'

export interface BarnStats {
  totalCows: number
  healthDistribution: { name: string; value: number }[]
  todayEvents: number
  eventTrend: { name: string; value: number }[]
  openOrders: number
  totalDevices: number
  onlineDevices: number
  deviceOnlineRate: number
}

export function barnStats() {
  return get<BarnStats>('/stats/barn')
}

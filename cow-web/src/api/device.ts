import { get } from '@/utils/request'

export interface DeviceView {
  id: number
  deviceId: string
  type: 'CAMERA' | 'EDGE_NODE'
  name: string
  barnId: string
  lastHeartbeatAt: string
  lastSyncAt: string
  pendingCount: number
  meta: Record<string, any>
  onlineStatus: 'ONLINE' | 'OFFLINE'
  offlineSeconds: number
}

export function listDevices() {
  return get<DeviceView[]>('/devices')
}

export function deviceDetail(deviceId: string) {
  return get<DeviceView>(`/devices/${deviceId}`)
}

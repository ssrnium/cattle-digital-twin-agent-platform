import { get } from '@/utils/request'
import type { TwinState } from './cow'

export function twinStates() {
  return get<TwinState[]>('/twin/states')
}

import { get, post, put, del } from '@/utils/request'
import type { PageResult } from '@/utils/request'

export interface SysUser {
  id: number
  username: string
  nickname: string
  phone: string
  status: string
  createTime: string
}

export interface SysRole {
  id: number
  roleCode: string
  roleName: string
  description: string
  createTime: string
}

export function pageUsers(params: { page: number; size: number; keyword?: string }) {
  return get<PageResult<SysUser>>('/system/users', params)
}

export function userOptions() {
  return get<SysUser[]>('/system/users/options')
}

export function createUser(data: any) {
  return post<SysUser>('/system/users', data)
}

export function updateUser(id: number, data: any) {
  return put<SysUser>(`/system/users/${id}`, data)
}

export function deleteUser(id: number) {
  return del(`/system/users/${id}`)
}

export function pageRoles(params: { page: number; size: number; keyword?: string }) {
  return get<PageResult<SysRole>>('/system/roles', params)
}

export function allRoles() {
  return get<SysRole[]>('/system/roles/all')
}

export function rolePerms(id: number) {
  return get<string[]>(`/system/roles/${id}/perms`)
}

export function createRole(data: any) {
  return post<SysRole>('/system/roles', data)
}

export function updateRole(id: number, data: any) {
  return put<SysRole>(`/system/roles/${id}`, data)
}

export function deleteRole(id: number) {
  return del(`/system/roles/${id}`)
}

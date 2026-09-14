import { get, post } from '@/utils/request'

export interface LoginResult {
  token: string
  username: string
  nickname: string
}

export interface Profile {
  id: number
  username: string
  nickname: string
  roles: string[]
  perms: string[]
}

export function login(username: string, password: string) {
  return post<LoginResult>('/auth/login', { username, password })
}

export function profile() {
  return get<Profile>('/auth/profile')
}

export function logout() {
  return post('/auth/logout')
}

import { defineStore } from 'pinia'
import { login as loginApi, profile as profileApi } from '@/api/auth'

interface UserState {
  token: string
  username: string
  nickname: string
  roles: string[]
  perms: string[]
  loaded: boolean
}

export const useUserStore = defineStore('user', {
  state: (): UserState => ({
    token: localStorage.getItem('token') || '',
    username: '',
    nickname: '',
    roles: [],
    perms: [],
    loaded: false
  }),
  actions: {
    async login(username: string, password: string) {
      const data = await loginApi(username, password)
      this.token = data.token
      localStorage.setItem('token', data.token)
    },
    async fetchProfile() {
      const data = await profileApi()
      this.username = data.username
      this.nickname = data.nickname || data.username
      this.roles = data.roles || []
      this.perms = data.perms || []
      this.loaded = true
    },
    hasPerm(perm: string): boolean {
      if (!perm) return true
      return this.perms.includes('*') || this.perms.includes(perm)
    },
    logout() {
      this.token = ''
      this.username = ''
      this.nickname = ''
      this.roles = []
      this.perms = []
      this.loaded = false
      localStorage.removeItem('token')
    }
  }
})

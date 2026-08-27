// 认证状态 —— 全系统唯一的一套。
import { defineStore } from 'pinia'
import { api } from '../api'
import { useSessionStore } from './session'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('sh_token') || '',
    user: JSON.parse(localStorage.getItem('sh_user') || 'null'),
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    displayName: (s) => s.user?.display_name || s.user?.username || '未登录',
  },
  actions: {
    async login(username, password) {
      this._apply(await api.login(username, password))
    },
    async register(username, password, displayName) {
      this._apply(await api.register(username, password, displayName))
    },
    async fetchMe() {
      if (!this.token) return null
      try {
        const r = await api.me()
        this.user = r.user
        localStorage.setItem('sh_user', JSON.stringify(r.user))
        return r.user
      } catch (err) {
        // 普通网络波动或服务暂时不可用时，保留本地登录状态，绝不随意退出登录
        return this.user
      }
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('sh_token')
      localStorage.removeItem('sh_user')
      useSessionStore().clear()
    },
    _apply(res) {
      this.token = res.token
      this.user = res.user
      localStorage.setItem('sh_token', res.token)
      localStorage.setItem('sh_user', JSON.stringify(res.user))
      useSessionStore().clear()
    },
  },
})

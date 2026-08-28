// 会话状态：当前选中的健康档案。浏览器只记"在看哪个档案"，数据以服务端为准。
import { defineStore } from 'pinia'
import { api } from '../api'

export const useSessionStore = defineStore('session', {
  state: () => ({
    profileId: localStorage.getItem('sh_pid') || '',
    profile: null,
    health: null,
    loading: false,
  }),
  getters: {
    hasProfile: (s) => !!s.profileId,
    profileName: (s) => s.profile?.name || '',
    ageSex: (s) => {
      if (!s.profile) return ''
      const sex = { female: '女', male: '男' }[s.profile.sex] || ''
      const age = s.profile.age_years != null ? `${s.profile.age_years} 岁` : ''
      return [age, sex].filter(Boolean).join(' · ')
    },
  },
  actions: {
    async select(pid) {
      this.profileId = pid
      localStorage.setItem('sh_pid', pid)
      await this.refresh()
    },
    clear() {
      this.profileId = ''
      this.profile = null
      localStorage.removeItem('sh_pid')
    },
    async refresh() {
      if (!this.profileId) return null
      this.loading = true
      try {
        this.profile = await api.getProfile(this.profileId)
      } catch (e) {
        // 只有后端明确返回「档案不存在」(404) 才清除本地选中状态；
        // 网络波动/超时/代理错误 → 保留本地 profile 不清除，防止闪退
        if (/档案不存在|404/.test(e.message) && !/无法连接|timeout|network/i.test(e.message)) {
          this.clear()
        }
        // 其他错误（网络断连等）静默保留当前状态
      } finally {
        this.loading = false
      }
      return this.profile
    },
    async loadHealth() {
      try { this.health = await api.health() } catch { this.health = null }
      return this.health
    },
    async ensureProfile() {
      // 登录后若无本地选择，自动取该用户的第一个档案
      if (this.profileId) return this.refresh()
      try {
        const r = await api.listProfiles()
        if (r.items?.length) await this.select(r.items[0].id)
      } catch { /* 保持未选择，路由会引导到 onboard */ }
      return this.profile
    },
  },
})

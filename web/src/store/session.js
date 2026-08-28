// 会话状态：当前选中的健康档案。浏览器只记"在看哪个档案"，数据以服务端为准。
import { defineStore } from 'pinia'
import { api } from '../api'

export const useSessionStore = defineStore('session', {
  state: () => ({
    profileId: localStorage.getItem('sh_pid') || '',
    profile: null,
    health: null,
    loading: false,
    _ensureChecked: false,   // ensureProfile 是否成功拿到过服务端结果
    _ensureEmpty: false,     // 服务端确认过该用户没有任何档案
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
      } catch {
        // 【绝不 clear】—— 无论什么错误（404/500/超时/网络断连），
        // 都保留本地 profileId 不清除，防止任何闪退。
        // 最坏情况：页面显示空数据，用户手动刷新即可。
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
        this._ensureChecked = true  // API 调用成功了
        if (r.items?.length) {
          await this.select(r.items[0].id)
          this._ensureEmpty = false
        } else {
          this._ensureEmpty = true   // 服务端确认：该用户确实没有档案
        }
      } catch {
        // API 失败（500/超时/网络断连）—— 不标记 ensureEmpty，
        // 路由守卫会放行，让页面自己显示空状态而不是跳走
        this._ensureChecked = false
      }
      return this.profile
    },
  },
})

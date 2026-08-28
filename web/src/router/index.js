import { createRouter, createWebHistory } from 'vue-router'

// 信息架构（对应规格书 P01–P14）
// 底栏五项：首页 · 分析 · 方案 · 档案 · 我的
const routes = [
  { path: '/login', component: () => import('../pages/LoginPage.vue'),
    meta: { public: true, bare: true } },
  { path: '/onboard', component: () => import('../pages/OnboardPage.vue'),   // P01+P02
    meta: { bare: true } },

  { path: '/', component: () => import('../pages/HomePage.vue'),             // P03
    meta: { title: '我的健康', nav: 'home', needProfile: true } },

  { path: '/upload', component: () => import('../pages/UploadPage.vue'),     // P04+P05
    meta: { title: '上传健康资料', nav: 'home', back: '/', needProfile: true } },

  { path: '/analysis', component: () => import('../pages/AnalysisPage.vue'), // P06
    meta: { title: '我的健康分析', nav: 'analysis', needProfile: true } },
  { path: '/issue/:iid', component: () => import('../pages/IssuePage.vue'),  // P07
    meta: { title: '问题详情', nav: 'analysis', back: '/analysis', needProfile: true } },
  { path: '/trends', component: () => import('../pages/TrendsPage.vue'),     // P08
    meta: { title: '健康趋势', nav: 'analysis', back: '/analysis', needProfile: true } },

  { path: '/plan', component: () => import('../pages/PlanPage.vue'),         // P09+P11
    meta: { title: '我的方案', nav: 'plan', needProfile: true } },
  { path: '/recipe/:rcid', component: () => import('../pages/RecipePage.vue'), // P10
    meta: { title: '菜谱详情', nav: 'plan', back: '/plan', needProfile: true } },

  { path: '/ask/general', component: () => import('../pages/GeneralAskPage.vue'),
    meta: { title: '健康问答', nav: 'home', back: '/', needProfile: false } },

  { path: '/ask', component: () => import('../pages/AskPage.vue'),           // P12
    meta: { title: '结合档案问一问', nav: 'analysis', back: '/analysis', needProfile: true } },

  { path: '/archive', component: () => import('../pages/ArchivePage.vue'),   // P13
    meta: { title: '我的健康档案', nav: 'archive', needProfile: true } },
  { path: '/report/:rid', component: () => import('../pages/ReportViewPage.vue'), // P14
    meta: { title: '原始报告', nav: 'archive', back: '/archive', needProfile: true } },

  { path: '/me', component: () => import('../pages/MePage.vue'),
    meta: { title: '我的', nav: 'me' } },
  { path: '/me/profile', component: () => import('../pages/ProfileEditPage.vue'),
    meta: { title: '健康基础资料', nav: 'me', back: '/me', needProfile: true } },

  { path: '/:pathMatch(.*)*', redirect: '/' },
]

import { useSessionStore } from '../store/session'

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const hasToken = !!localStorage.getItem('sh_token')
  if (!to.meta.public && !hasToken) return { path: '/login', query: { r: to.fullPath } }
  if (to.path === '/login' && hasToken) return { path: '/' }

  // 需要档案的页面：尝试自动加载，但【绝不因失败而跳转】
  if (to.meta.needProfile && hasToken && !localStorage.getItem('sh_pid')) {
    try {
      const session = useSessionStore()
      await session.ensureProfile()
    } catch { /* 网络/服务异常，静默放行 */ }
    // 只有服务端明确确认「该用户没有任何档案」时才引导到创建页面
    // API 失败（500/超时/断网）→ 直接放行，页面自己显示空状态
    const session = useSessionStore()
    if (!localStorage.getItem('sh_pid') && session._ensureChecked && session._ensureEmpty) {
      return { path: '/onboard' }
    }
  }
  return true
})

export default router

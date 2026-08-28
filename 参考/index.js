// 统一 API 层 —— 与后端 app/api/* 一一对应，全系统只有这一份接口封装。

const BASE = import.meta.env.VITE_API_BASE ?? ''

function token() {
  return localStorage.getItem('sh_token') || ''
}

// ---- 401 二次复核：偶发 401（隧道/CDN/并发抖动）绝不直接登出。 ----
// 收到可疑 401 时，先用现有令牌静默调一次 /api/auth/me 复核：
//   复核通过(200) → 令牌有效，刚才只是链路抖动，什么都不做；
//   复核仍是 401  → 令牌确实失效，才清 token 并跳登录页。
// 复核请求用裸 fetch，避免递归触发本机制。
let _lastUnauth = 0
let _verifying = null

function _doLogout() {
  const now = Date.now()
  if (now - _lastUnauth < 2000) return   // 2秒去重，防止并发连环触发
  _lastUnauth = now
  localStorage.removeItem('sh_token')
  localStorage.removeItem('sh_user')
  window.dispatchEvent(new CustomEvent('sh:unauthorized'))
}

function _verifyThenLogout() {
  if (_verifying) return _verifying      // 并发 401 只复核一次
  _verifying = (async () => {
    try {
      const t = token()
      if (!t) { _doLogout(); return }
      const res = await fetch(BASE + '/api/auth/me', {
        headers: { Authorization: `Bearer ${t}` },
      })
      if (res.status === 401) _doLogout()
      // 其他任何结果（200/5xx/网络失败）都视为「登录未失效」，不登出
    } catch { /* 网络异常 → 保守起见不登出 */ }
    finally { _verifying = null }
  })()
  return _verifying
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  const t = token()
  if (t) headers.Authorization = `Bearer ${t}`

  let res
  try {
    res = await fetch(BASE + path, { ...options, headers })
  } catch {
    throw new Error('无法连接后端服务。请确认已运行 python run.py')
  }
  if (res.status === 401) {
    const detail = await detailOf(res)
    // 登录/注册接口的 401 是「账号密码错误」，与令牌无关，不触发复核
    if (!path.startsWith('/api/auth/login') && !path.startsWith('/api/auth/register')) {
      _verifyThenLogout()   // 不 await：先把错误抛给页面提示，复核在后台进行
    }
    throw new Error(detail || '请求未授权')
  }
  if (!res.ok) throw new Error(await detailOf(res) || `请求失败 HTTP ${res.status}`)
  if (res.status === 204) return null
  return res.json()
}

async function detailOf(res) {
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return body.detail.map((d) => d.msg).join('；')
    return ''
  } catch { return '' }
}

const post = (p, body) => request(p, { method: 'POST', body: JSON.stringify(body ?? {}) })
const patch = (p, body) => request(p, { method: 'PATCH', body: JSON.stringify(body ?? {}) })
const del = (p) => request(p, { method: 'DELETE' })
const q = (obj) => new URLSearchParams(obj).toString()

export const api = {
  // ---- 状态 ----
  health: () => request('/api/health'),

  // ---- 认证 ----
  login: (username, password) => post('/api/auth/login', { username, password }),
  register: (username, password, display_name) =>
    post('/api/auth/register', { username, password, display_name }),
  me: () => request('/api/auth/me'),

  // ---- 档案 ----
  listProfiles: () => request('/api/profiles'),
  createProfile: (payload) => post('/api/profiles', payload),
  getProfile: (pid) => request(`/api/profiles/${pid}`),
  updateProfile: (pid, payload) => patch(`/api/profiles/${pid}`, payload),
  timeline: (pid) => request(`/api/profiles/${pid}/timeline`),
  listEvents: (pid) => request(`/api/profiles/${pid}/events`),
  addEvent: (pid, payload) => post(`/api/profiles/${pid}/events`, payload),
  pendingCandidates: (pid) => request(`/api/profiles/${pid}/candidates`),
  resolveCandidate: (pid, cid, accept) =>
    post(`/api/profiles/${pid}/candidates/${cid}`, { accept }),

  // ---- 健康资料 ----
  uploadReports: (pid, files) => {
    const fd = new FormData()
    fd.append('profile_id', pid)
    for (const f of files) fd.append('files', f)
    return request('/api/reports/upload', { method: 'POST', body: fd })
  },
  listReports: (pid) => request(`/api/reports?${q({ profile_id: pid })}`),
  getReport: (rid) => request(`/api/reports/${rid}`),
  retryReport: (rid) => post(`/api/reports/${rid}/retry`),
  confirmReport: (rid, payload) => post(`/api/reports/${rid}/confirm`, payload),
  reportFileUrl: (rid) => `${BASE}/api/reports/${rid}/file`,
  deleteReport: (rid) => del(`/api/reports/${rid}`),

  // ---- 指标 ----
  metricCodes: (pid) => request(`/api/metrics/codes?${q({ profile_id: pid })}`),
  metricSeries: (pid, code) =>
    request(`/api/metrics/series?${q({ profile_id: pid, code })}`),

  // ---- 分析 ----
  runAssessment: (pid, force = false) =>
    post('/api/assessments/run', { profile_id: pid, force }),
  analysisScope: (pid) => request(`/api/assessments/scope?${q({ profile_id: pid })}`),
  latestAssessment: (pid) => request(`/api/assessments/latest?${q({ profile_id: pid })}`),
  assessmentHistory: (pid) => request(`/api/assessments/history?${q({ profile_id: pid })}`),
  riskTimeline: (pid) => request(`/api/assessments/risk-timeline?${q({ profile_id: pid })}`),
  getAssessment: (aid) => request(`/api/assessments/${aid}`),
  getIssue: (iid) => request(`/api/assessments/issues/${iid}`),

  // ---- 方案 ----
  dietGenerate: (pid) => post('/api/plans/diet/generate', { profile_id: pid }),
  dietActive: (pid) => request(`/api/plans/diet/active?${q({ profile_id: pid })}`),
  dietHistory: (pid) => request(`/api/plans/diet/history?${q({ profile_id: pid })}`),
  dietGet: (dpid) => request(`/api/plans/diet/${dpid}`),
  recipe: (rcid) => request(`/api/plans/recipes/${rcid}`),
  teaGenerate: (pid) => post('/api/plans/tea/generate', { profile_id: pid }),
  teaActive: (pid) => request(`/api/plans/tea/active?${q({ profile_id: pid })}`),
  teaHistory: (pid) => request(`/api/plans/tea/history?${q({ profile_id: pid })}`),
  teaGet: (tid) => request(`/api/plans/tea/${tid}`),

  // ---- 问询 ----
  ask: (pid, text, conversationId) =>
    post('/api/ask', { profile_id: pid, text, conversation_id: conversationId || null }),
  askGeneral: (text, messages = []) => post('/api/ask/general', { text, messages }),
  conversations: (pid) => request(`/api/ask/conversations?${q({ profile_id: pid })}`),
  conversation: (cid) => request(`/api/ask/conversations/${cid}`),
}

// 统一 API 层 —— 与后端 app/api/* 一一对应，全系统只有这一份接口封装。

const BASE = import.meta.env.VITE_API_BASE ?? ''

function token() {
  return localStorage.getItem('sh_token') || ''
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
    if (!path.startsWith('/api/auth/login') && !path.startsWith('/api/auth/register')) {
      localStorage.removeItem('sh_token')
      localStorage.removeItem('sh_user')
      window.dispatchEvent(new CustomEvent('sh:unauthorized'))
    }
    throw new Error(await detailOf(res) || '登录已失效，请重新登录')
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

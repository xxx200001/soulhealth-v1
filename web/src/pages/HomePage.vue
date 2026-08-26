<template>
  <div class="page stack">
    <!-- 驾驶舱 hero：现在怎么样 · 第一优先是什么 -->
    <section class="card-hero hero fade-in" @click="$router.push('/analysis')">
      <svg class="fret" viewBox="0 0 96 96" fill="none" aria-hidden="true">
        <path d="M8 88V8h80M24 88V24h64M40 88V40h48M56 88V56h32M72 88V72h16"
              stroke="currentColor" stroke-width="3" />
      </svg>
      <p class="date">{{ todayCN }} · 我的健康</p>

      <template v-if="top">
        <p class="eyebrow">当前第一优先关注</p>
        <div class="row" style="gap:10px">
          <h2 class="topt">{{ top.title }}</h2>
          <LevelBadge :level="top.level" class="on-dark" />
        </div>
        <p class="tops">{{ top.summary }}</p>
      </template>
      <template v-else-if="loaded">
        <h2 class="topt">开始建立你的长期健康档案</h2>
        <p class="tops">上传一份报告，或先问一个健康问题</p>
      </template>
      <div v-else class="row" style="padding:14px 0"><span class="spin light"></span></div>

      <div v-if="counts" class="counts">
        <div v-for="c in countItems" :key="c.key" class="ct">
          <i :style="{ background: `var(--lv-${c.key})` }"></i>
          <b class="num">{{ counts[c.key] || 0 }}</b>
          <span>{{ c.label }}</span>
        </div>
      </div>
      <span class="go">查看完整分析 ›</span>
    </section>

    <!-- 三个核心入口（方案书 §12.1：统一为这三项） -->
    <section class="grid-3 stagger entries">
      <button class="card ent card-clickable" @click="$router.push('/upload')">
        <span class="ico up" v-html="icons.upload"></span><b>上传健康资料</b>
      </button>
      <button class="card ent card-clickable" @click="$router.push('/ask')">
        <span class="ico ask" v-html="icons.ask"></span><b>问问我的健康</b>
        <span class="tiny">结合我的历史档案回答</span>
      </button>
      <button class="card ent card-clickable" @click="$router.push('/archive')">
        <span class="ico ar" v-html="icons.archive"></span><b>我的健康档案</b>
      </button>
    </section>

    <!-- 待办提醒 -->
    <div v-if="pendingReports" class="alert alert-warn fade-in" role="button"
         @click="$router.push('/upload')">
      有 {{ pendingReports }} 份资料待确认（日期或识别项）——确认后才会进入趋势与分析 ›
    </div>
    <div v-if="pendingCands" class="alert alert-info fade-in" role="button"
         @click="$router.push('/ask')">
      问询中记录了 {{ pendingCands }} 条健康信息待你确认入档 ›
    </div>

    <!-- 最近健康变化：真实检查日期趋势 -->
    <section v-if="recent.length" class="card fade-in">
      <div class="row-between">
        <div class="card-title"><span class="dot"></span>最近健康变化</div>
        <router-link to="/trends" class="tiny">全部趋势 ›</router-link>
      </div>
      <div class="stack-sm" style="margin-top: var(--sp-3)">
        <router-link v-for="r in recent" :key="r.code" class="rc"
                     :to="`/trends?code=${r.code}`">
          <span class="grow">
            <b>{{ r.name }}</b>
            <span class="tiny" style="display:block">
              {{ r.trendText }}
            </span>
          </span>
          <MiniTrend :values="r.values"
                     :color="r.grade ? 'var(--lv-watch)' : 'var(--brand-500)'" />
          <span class="val num" :class="{ bad: r.grade }">
            {{ r.latest }}<small>{{ r.unit }}</small>
          </span>
        </router-link>
      </div>
    </section>

    <!-- 我的健康方案摘要 -->
    <section class="card fade-in">
      <div class="row-between">
        <div class="card-title"><span class="dot"></span>我的健康方案</div>
        <router-link to="/plan" class="tiny">进入方案 ›</router-link>
      </div>
      <div v-if="dietGoals.length || tea" class="stack-sm" style="margin-top: var(--sp-3)">
        <div v-if="dietGoals.length" class="row wrap">
          <span class="badge badge-gold" v-for="g in dietGoals" :key="g">{{ g }}</span>
          <span class="muted">当前饮食管理重点</span>
        </div>
        <div v-if="tea" class="row">
          <span class="tea-ico" v-html="icons.tea"></span>
          <span class="grow">
            <b style="font-size:14px">{{ tea.name || '药食同源茶饮' }}</b>
            <span class="tiny" style="display:block">{{ teaSub }}</span>
          </span>
          <LevelBadge v-if="false" level="stable" />
        </div>
      </div>
      <p v-else class="muted" style="margin: var(--sp-2) 0 0">
        完成一次健康分析后，这里会展示为你生成的食补与茶饮方案
      </p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useSessionStore } from '../store/session'
import LevelBadge from '../components/LevelBadge.vue'
import MiniTrend from '../components/MiniTrend.vue'

const session = useSessionStore()
const loaded = ref(false)
const assessment = ref(null)
const dietPlan = ref(null)
const teaPlan = ref(null)
const pendingReports = ref(0)
const pendingCands = ref(0)
const recent = ref([])

const sw = 'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"'
const icons = {
  upload: `<svg viewBox="0 0 24 24" width="22" height="22" ${sw}><path d="M12 16V4M7.5 8.5 12 4l4.5 4.5"/><path d="M4 15v4a1.5 1.5 0 0 0 1.5 1.5h13A1.5 1.5 0 0 0 20 19v-4"/></svg>`,
  ask: `<svg viewBox="0 0 24 24" width="22" height="22" ${sw}><path d="M21 12a8 8 0 1 0-3.1 6.3L21 20l-.9-3.4A8 8 0 0 0 21 12Z"/></svg>`,
  archive: `<svg viewBox="0 0 24 24" width="22" height="22" ${sw}><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>`,
  tea: `<svg viewBox="0 0 24 24" width="20" height="20" ${sw}><path d="M4 9h13v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V9Z"/><path d="M17 10h1.5a2.5 2.5 0 0 1 0 5H17"/><path d="M8 5c0-1 .8-1 .8-2M12 5c0-1 .8-1 .8-2"/></svg>`,
}
const countItems = [
  { key: 'priority', label: '重点关注' },
  { key: 'watch', label: '需要留意' },
  { key: 'mild', label: '轻度关注' },
  { key: 'stable', label: '相对稳定' },
]

const todayCN = new Date().toLocaleDateString('zh-CN',
  { month: 'long', day: 'numeric', weekday: 'long' })

const top = computed(() => {
  const items = assessment.value?.issues || []
  return items.find((i) => i.rank === 1) || null
})
const counts = computed(() => assessment.value?.summary?.counts || null)
const dietGoals = computed(() =>
  (dietPlan.value?.goals || []).map((g) => g.label))
const tea = computed(() => teaPlan.value?.plan || null)
const teaSub = computed(() => {
  const s = teaPlan.value?.safety_status
  if (s === 'allow') return teaPlan.value.plan?.frequency || '已通过安全检查'
  return { require_info: '待补充安全信息', block: '已安全拦截',
           professional_review: '建议专业评估' }[s] || ''
})

onMounted(async () => {
  const pid = session.profileId
  const [a, d, t, reps, cands] = await Promise.allSettled([
    api.latestAssessment(pid), api.dietActive(pid), api.teaActive(pid),
    api.listReports(pid), api.pendingCandidates(pid),
  ])
  if (a.status === 'fulfilled') assessment.value = a.value.assessment
  if (d.status === 'fulfilled') dietPlan.value = d.value.plan
  if (t.status === 'fulfilled') teaPlan.value = t.value.plan
  if (reps.status === 'fulfilled')
    pendingReports.value = reps.value.items.filter(
      (r) => r.status === 'needs_confirmation').length
  if (cands.status === 'fulfilled') pendingCands.value = cands.value.items.length
  loaded.value = true
  loadRecent(pid)
})

async function loadRecent(pid) {
  const issues = assessment.value?.issues || []
  const codes = []
  for (const it of issues) {
    for (const c of it.detail?.codes_abnormal || []) {
      if (!codes.includes(c)) codes.push(c)
    }
    if (codes.length >= 3) break
  }
  const out = []
  for (const code of codes.slice(0, 3)) {
    try {
      const s = await api.metricSeries(pid, code)
      const ins = s.insight
      if (!ins) continue
      out.push({
        code, name: s.name_cn, unit: s.unit,
        values: ins.points.map((p) => p.value),
        latest: ins.latest.value, grade: ins.latest.grade,
        trendText: ins.persistent_direction
          ? `${ins.persistent_direction} · 最近 ${ins.latest.date}`
          : `最近记录 ${ins.latest.date}`,
      })
    } catch { /* 单条失败不影响整页 */ }
  }
  recent.value = out
}
</script>

<style scoped>
.hero { cursor: pointer; }
.fret { position: absolute; right: -6px; top: -6px; width: 96px; height: 96px;
  color: var(--gold-500); opacity: .14; }
.date { margin: 0; font-size: 12px; opacity: .75; letter-spacing: .5px; }
.eyebrow { margin: var(--sp-3) 0 2px; font-size: 12px; color: var(--gold-500);
  font-weight: 700; letter-spacing: 1px; }
.topt { font-size: 22px; }
.tops { margin: 6px 0 0; font-size: 13px; opacity: .88; line-height: 1.6; }
.on-dark { background: rgba(255,255,255,.16) !important; color: #fff !important; }
.counts { display: grid; grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-2); margin-top: var(--sp-4);
  background: rgba(255,255,255,.1); border-radius: var(--r-md);
  padding: var(--sp-3) var(--sp-2); }
.ct { display: flex; flex-direction: column; align-items: center; gap: 1px; }
.ct i { width: 6px; height: 6px; border-radius: 50%; margin-bottom: 3px; }
.ct b { font-size: 18px; line-height: 1.1; }
.ct span { font-size: 10.5px; opacity: .8; }
.go { display: inline-block; margin-top: var(--sp-3); font-size: 12.5px;
  color: var(--gold-500); font-weight: 600; }
.spin.light { border-color: rgba(255,255,255,.3); border-top-color: #fff; }

.entries .ent { display: flex; flex-direction: column; align-items: center;
  gap: 6px; padding: var(--sp-4) var(--sp-2); border: 1px solid var(--line);
  font: inherit; text-align: center; }
.ent b { font-size: 13px; font-family: var(--font-serif); }
.ent .ico { width: 40px; height: 40px; border-radius: 13px; display: flex;
  align-items: center; justify-content: center; }
.ico.up { background: var(--brand-050); color: var(--brand-700); }
.ico.ask { background: var(--gold-100); color: var(--gold-700); }
.ico.ar { background: var(--info-bg); color: var(--info); }

.rc { display: flex; align-items: center; gap: var(--sp-3);
  padding: var(--sp-2) 0; border-bottom: 1px solid var(--line-soft); color: inherit; }
.rc:last-child { border-bottom: none; }
.val { font-size: 16px; min-width: 62px; text-align: right; }
.val small { font-size: 10px; color: var(--ink-400); margin-left: 2px; font-weight: 400; }
.val.bad { color: var(--lv-watch); }
.tea-ico { color: var(--gold-700); display: flex; }
</style>

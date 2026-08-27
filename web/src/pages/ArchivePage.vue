<template>
  <div class="page stack">
    <div class="seg fade-in">
      <button v-for="t in tabs" :key="t.key" :class="{ on: tab === t.key }"
              @click="tab = t.key">{{ t.label }}</button>
    </div>

    <!-- ============ 时间线（健康脉络 · 签名元素） ============ -->
    <template v-if="tab === 'timeline'">
      <EmptyState v-if="loaded && !timeline.length" icon="↟" text="时间线还是空的">
        <button class="btn btn-primary btn-sm" style="margin-top: var(--sp-2)"
                @click="$router.push('/upload')">上传第一份健康资料</button>
      </EmptyState>
      <section v-else class="card fade-in">
        <div class="vein">
          <template v-for="grp in byYear" :key="grp.year">
            <div class="vein-year">{{ grp.year }}</div>
            <div v-for="it in grp.items" :key="it.kind + it.id"
                 class="vein-item" :class="`kind-${it.kind}`">
              <component :is="it.kind === 'report' ? 'router-link' : 'div'"
                         :to="it.kind === 'report' ? `/report/${it.id}` : undefined"
                         class="ti" :class="{ link: it.kind === 'report' }">
                <div class="row-between">
                  <b class="tt">{{ it.title }}</b>
                  <span class="tiny">{{ it.date }}</span>
                </div>
                <p v-if="it.subtitle" class="tiny sub">{{ it.subtitle }}</p>
                <span class="badge badge-quiet kd">{{ kindCN(it.kind) }}</span>
              </component>
            </div>
          </template>
        </div>
      </section>
    </template>

    <!-- ============ 报告 ============ -->
    <template v-else-if="tab === 'reports'">
      <EmptyState v-if="loaded && !reports.length" icon="▤" text="还没有报告" />
      <section v-for="r in reports" :key="r.id" class="card fade-in repline">
        <router-link :to="`/report/${r.id}`" class="row grow" style="color:inherit">
          <span class="st" :class="`st-${r.status}`"></span>
          <span class="grow">
            <b>{{ r.source_filename || '健康资料' }}</b>
            <span class="tiny" style="display:block">
              {{ typeCN(r.report_type) }} · {{ r.report_date || '日期待确认' }}
              <template v-if="r.stats?.observations"> · {{ r.stats.observations }} 项指标</template>
            </span>
          </span>
          <span class="badge" :class="stBadge(r.status)">{{ stCN(r.status) }}</span>
        </router-link>
        <button class="btn btn-quiet btn-sm" @click="removeReport(r)">删除</button>
      </section>
    </template>

    <!-- ============ 指标 ============ -->
    <template v-else-if="tab === 'metrics'">
      <EmptyState v-if="loaded && !codes.length" icon="◍" text="还没有可比较的指标" />
      <section v-else class="card fade-in">
        <div class="table-wrap">
          <table class="table">
            <thead><tr><th>指标</th><th>记录次数</th><th>最近日期</th><th></th></tr></thead>
            <tbody>
              <tr v-for="c in codes" :key="c.code">
                <td><b>{{ c.name_cn }}</b> <span class="tiny">{{ c.code }}</span></td>
                <td class="num">{{ c.n }}</td>
                <td class="tiny">{{ c.last_date }}</td>
                <td><router-link :to="`/trends?code=${c.code}`" class="tiny">趋势 ›</router-link></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <!-- ============ 事件 ============ -->
    <template v-else-if="tab === 'events'">
      <section class="card fade-in">
        <div class="card-title"><span class="dot"></span>记录一条健康事件</div>
        <p class="tiny" style="margin: 4px 0 var(--sp-2)">
          症状、生活方式变化、用药调整…都值得留在档案里
        </p>
        <div class="row">
          <input v-model="evDate" type="date" class="input" style="max-width: 150px" />
          <input v-model.trim="evText" class="input grow" placeholder="发生了什么"
                 @keyup.enter="addEvent" />
          <button class="btn btn-primary btn-sm" :disabled="!evText" @click="addEvent">记录</button>
        </div>
      </section>
      <EmptyState v-if="loaded && !events.length" icon="✎" text="还没有健康事件" />
      <section v-for="e in events" :key="e.id" class="card fade-in">
        <div class="row-between">
          <b style="font-size:14px">{{ e.content }}</b>
          <span class="tiny">{{ e.event_date }}</span>
        </div>
        <div class="row" style="margin-top: 4px">
          <span class="badge badge-quiet">{{ evKind(e.type) }}</span>
          <SourceTag :text="e.source === 'agent_confirmed' ? '问询确认' : '本人记录'" />
        </div>
      </section>
    </template>

    <!-- ============ 基础资料 ============ -->
    <template v-else>
      <section class="card fade-in" v-if="profile">
        <div class="row-between">
          <div class="card-title"><span class="dot"></span>健康基础资料</div>
          <button class="btn btn-ghost btn-sm" @click="$router.push('/me/profile')">编辑 ›</button>
        </div>
        <div class="kv">
          <div><span>姓名</span><b>{{ profile.name }}</b></div>
          <div><span>性别 / 年龄</span><b>{{ session.ageSex || '—' }}</b></div>
          <div><span>身高 / 体重</span>
            <b>{{ profile.height_cm ? profile.height_cm + ' cm' : '—' }} /
               {{ profile.weight_kg ? profile.weight_kg + ' kg' : '—' }}</b></div>
          <div><span>过敏史</span><b>{{ listOr(profile.allergies, '未记录') }}</b></div>
          <div><span>当前用药</span><b>{{ listOr(profile.medications, '未记录') }}</b></div>
          <div><span>既往疾病</span><b>{{ listOr(profile.conditions, '未记录') }}</b></div>
          <div><span>吸烟 / 饮酒</span>
            <b>{{ habitCN(profile.smoking) }} / {{ habitCN(profile.alcohol) }}</b></div>
        </div>
        <p class="tiny" style="margin-top: var(--sp-2)">
          「未记录」与「无」不同：茶饮等安全检查需要你明确确认后者
        </p>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useSessionStore } from '../store/session'
import EmptyState from '../components/EmptyState.vue'
import SourceTag from '../components/SourceTag.vue'

const session = useSessionStore()
const tabs = [
  { key: 'timeline', label: '时间线' }, { key: 'reports', label: '报告' },
  { key: 'metrics', label: '指标' }, { key: 'events', label: '事件' },
  { key: 'base', label: '资料' },
]
const tab = ref('timeline')
const loaded = ref(false)
const timeline = ref([])
const reports = ref([])
const codes = ref([])
const events = ref([])
const profile = computed(() => session.profile)
const evDate = ref(new Date().toISOString().slice(0, 10))
const evText = ref('')

const byYear = computed(() => {
  const map = new Map()
  for (const it of timeline.value) {
    const y = (it.date || '').slice(0, 4) || '未知年份'
    if (!map.has(y)) map.set(y, [])
    map.get(y).push(it)
  }
  return [...map.entries()].map(([year, items]) => ({ year, items }))
})

function kindCN(k) {
  return { report: '健康报告', event: '健康事件', assessment: '健康分析',
           plan: '食补方案', tea: '茶饮方案' }[k] || k
}
function typeCN(t) {
  return {
    lab_report: '检验报告',
    ultrasound_report: '超声检查',
    mri_report: '磁共振(MRI)',
    ct_report: 'CT检查',
    imaging_report: '影像检查',
    xray_report: 'X光/DR',
    clinical_note: '病历小结',
    checkup: '体检报告',
    other: '健康资料',
  }[t] || '健康资料'
}
function stCN(s) {
  return { ready: '已识别', needs_confirmation: '待确认', failed: '失败',
           processing: '识别中', uploaded: '排队中' }[s] || s
}
function stBadge(s) {
  return { ready: 'badge-ok', needs_confirmation: 'badge-warn',
           failed: 'badge-danger' }[s] || 'badge-quiet'
}
function evKind(t) {
  return { symptom: '症状', lifestyle: '生活方式', medication: '用药',
           note: '记录' }[t] || '记录'
}
function habitCN(v) {
  return { none: '不', occasional: '偶尔', regular: '经常', quit: '已戒' }[v] || '未记录'
}
function listOr(arr, fallback) {
  if (!Array.isArray(arr)) return fallback
  if (!arr.length) return '无'
  return arr.join('、')
}

async function refresh() {
  const pid = session.profileId
  const [t, r, c, e] = await Promise.allSettled([
    api.timeline(pid), api.listReports(pid),
    api.metricCodes(pid), api.listEvents(pid)])
  if (t.status === 'fulfilled') timeline.value = t.value.items
  if (r.status === 'fulfilled') reports.value = r.value.items
  if (c.status === 'fulfilled') codes.value = (c.value.items || []).filter((x) => x.code)
  if (e.status === 'fulfilled') events.value = e.value.items
  loaded.value = true
}

async function addEvent() {
  if (!evText.value) return
  try {
    await api.addEvent(session.profileId,
      { event_date: evDate.value, type: 'note', content: evText.value })
    evText.value = ''
    refresh()
  } catch (err) { alert(err.message) }
}

async function removeReport(r) {
  if (!confirm(`删除「${r.source_filename}」？其提取的指标也会一并移除`)) return
  try { await api.deleteReport(r.id); refresh() } catch (e) { alert(e.message) }
}

onMounted(async () => {
  if (!session.profile) await session.refresh()
  refresh()
})
</script>

<style scoped>
.ti { display: block; background: var(--surface-sunk);
  border: 1px solid var(--line-soft); border-radius: var(--r-sm);
  padding: 10px 12px; color: inherit; }
.ti.link:hover { border-color: var(--brand-500); }
.ti .tt { font-size: 14px; }
.ti .sub { margin: 2px 0 0; }
.ti .kd { margin-top: 6px; }

.repline { display: flex; align-items: center; gap: var(--sp-2); }
.st { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.st-ready { background: var(--ok); }
.st-needs_confirmation { background: var(--warn); }
.st-failed { background: var(--danger); }
.st-processing, .st-uploaded { background: var(--ink-300); }

.kv { display: flex; flex-direction: column; gap: 8px; margin-top: var(--sp-2); }
.kv > div { display: flex; justify-content: space-between; gap: var(--sp-3);
  border-bottom: 1px dashed var(--line-soft); padding-bottom: 8px;
  font-size: 13.5px; }
.kv > div:last-child { border-bottom: none; }
.kv span { color: var(--ink-400); white-space: nowrap; }
.kv b { text-align: right; font-weight: 600; }
</style>

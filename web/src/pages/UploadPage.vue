<template>
  <div class="page stack">
    <!-- 选择与上传 -->
    <section class="card fade-in">
      <div class="card-title"><span class="dot"></span>上传健康资料</div>
      <p class="muted" style="margin: 6px 0 var(--sp-3)">
        支持图片 / 拍照 / PDF，可一次选择多份；每份资料独立识别、独立入档
      </p>

      <label class="drop" :class="{ busy }">
        <input type="file" multiple accept="image/*,.pdf" hidden
               :disabled="busy" @change="onPick" />
        <span v-if="!busy" class="drop-ico" v-html="icoUp"></span>
        <span v-else class="spin"></span>
        <b>{{ busy ? `正在识别 第 ${doing}/${total} 份…` : '点击选择文件（可多选）' }}</b>
        <span class="tiny">原件将完整保存，识别结果可随时回溯到原始报告</span>
      </label>
      <div v-if="busy" class="bar" style="margin-top: var(--sp-3)">
        <span :style="{ width: (doing / Math.max(total,1)) * 100 + '%' }"></span>
      </div>
    </section>

    <!-- 本次处理总账（F-UP-07） -->
    <section v-if="summary" class="card fade-in ledger">
      <div class="card-title"><span class="dot"></span>本次处理总账</div>
      <div class="lg-grid">
        <div><b class="num">{{ summary.total }}</b><span>上传份数</span></div>
        <div><b class="num ok">{{ summary.ready }}</b><span>已识别</span></div>
        <div><b class="num warn">{{ summary.needs_confirmation }}</b><span>需要确认</span></div>
        <div><b class="num bad">{{ summary.failed }}</b><span>失败</span></div>
      </div>
      <div class="lg-meta">
        <span v-if="summary.date_span">
          覆盖时间 <b>{{ summary.date_span[0] }}</b> ~ <b>{{ summary.date_span[1] }}</b>
        </span>
        <span>提取指标 <b class="num">{{ summary.observations }}</b> 项</span>
        <span>可历史比较 <b class="num">{{ summary.comparable_codes }}</b> 项</span>
      </div>
    </section>

    <!-- 逐份状态（F-UP-01：一次上传多份，界面可逐份看到状态） -->
    <section v-if="items.length" class="stack-sm stagger">
      <div v-for="r in items" :key="r.id" class="card rep">
        <div class="row">
          <span class="st" :class="`st-${r.status}`"></span>
          <span class="grow">
            <b class="fn">{{ r.source_filename }}</b>
            <span class="tiny meta">
              {{ typeCN(r.report_type) }}
              <template v-if="r.report_date"> · 检查日期 {{ r.report_date }}
                <em v-if="!r.date_confirmed" class="need">（待确认）</em>
              </template>
              <template v-if="r.stats?.observations">
                · 提取 {{ r.stats.observations }} 项
              </template>
            </span>
          </span>
          <span class="badge" :class="statusBadge(r.status)">{{ statusCN(r.status) }}</span>
        </div>

        <p v-if="r.duplicate_of" class="alert alert-info dup">
          与已有报告日期/类型相同，疑似重复——已照常保存，你可以在档案中对比后自行删除
        </p>
        <p v-if="r.error" class="alert alert-danger dup">
          {{ r.error }}
          <button class="btn btn-sm btn-ghost" style="margin-left:8px" @click="retry(r)">重试</button>
        </p>

        <!-- 待确认：日期 + 低置信数值就地处理（F-UP-05 / AC-05） -->
        <div v-if="r.status === 'needs_confirmation'" class="confirm">
          <div v-if="!r.date_confirmed" class="field">
            <label class="label">这份报告的检查日期</label>
            <div class="row">
              <input v-model="r._date" type="date" class="input" style="max-width: 180px" />
              <span class="tiny">趋势将使用此真实日期，而不是今天的上传时间</span>
            </div>
          </div>
          <div v-if="r._lowObs?.length" class="field">
            <label class="label">以下数值识别置信度较低，请核对</label>
            <div class="row wrap" v-for="o in r._lowObs" :key="o.id" style="margin-bottom:6px">
              <span class="obn">{{ o.original_name || o.code }}</span>
              <input v-model.number="o._val" type="number" step="any"
                     class="input" style="max-width: 120px" />
              <span class="tiny">{{ o.unit }}</span>
            </div>
          </div>
          <button class="btn btn-primary btn-sm" :disabled="r._saving" @click="confirm(r)">
            <span v-if="r._saving" class="spin"></span>确认并入档
          </button>
        </div>
      </div>
    </section>

    <!-- 分析范围与去向（F-UP-08 / AC-06） -->
    <section v-if="scope" class="card fade-in scope">
      <div class="card-title"><span class="dot"></span>本次分析将使用的数据范围</div>
      <p class="muted" style="margin: 6px 0">
        当前 + 历史共 <b class="num">{{ scope.report_count }}</b> 份已就绪资料
        <template v-if="scope.date_span">
          ，覆盖 {{ scope.date_span[0] }} ~ {{ scope.date_span[1] }}
        </template>
        ；可比较指标 <b class="num">{{ scope.comparable_codes.length }}</b> 项
      </p>
      <div class="row wrap" style="margin-bottom: var(--sp-3)">
        <span v-for="rp in scope.reports.slice(0, 6)" :key="rp.id" class="src">
          {{ typeCN(rp.type) }} {{ rp.date || '' }}
        </span>
        <span v-if="scope.reports.length > 6" class="tiny">
          等 {{ scope.reports.length }} 份
        </span>
      </div>
      <button class="btn btn-gold btn-block btn-lg" @click="$router.push('/analysis')">
        开始健康分析 ›
      </button>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { useSessionStore } from '../store/session'

const session = useSessionStore()
const busy = ref(false)
const doing = ref(0)
const total = ref(0)
const summary = ref(null)
const items = ref([])
const scope = ref(null)

const icoUp = '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4M7.5 8.5 12 4l4.5 4.5"/><path d="M4 15v4a1.5 1.5 0 0 0 1.5 1.5h13A1.5 1.5 0 0 0 20 19v-4"/></svg>'

function typeCN(t) {
  return { lab_report: '检验报告', ultrasound_report: '超声检查',
           checkup: '体检报告', other: '健康资料' }[t] || '健康资料'
}
function statusCN(s) {
  return { uploaded: '排队中', processing: '识别中', ready: '已识别',
           needs_confirmation: '需要确认', failed: '失败' }[s] || s
}
function statusBadge(s) {
  return { ready: 'badge-ok', needs_confirmation: 'badge-warn',
           failed: 'badge-danger' }[s] || 'badge-quiet'
}

async function onPick(e) {
  const files = [...e.target.files]
  e.target.value = ''
  if (!files.length) return
  busy.value = true
  total.value = files.length
  doing.value = files.length   // 后端同步处理整批，进度以整批呈现
  try {
    const res = await api.uploadReports(session.profileId, files)
    summary.value = res
    await hydrate(res.reports)
    await loadScope()
  } catch (err) {
    alert(err.message)
  } finally {
    busy.value = false
    doing.value = 0
  }
}

async function hydrate(list) {
  // 为待确认报告拉取低置信观测项，就地编辑
  const out = []
  for (const r of list) {
    const row = { ...r, _date: r.report_date || '', _lowObs: [], _saving: false }
    if (r.status === 'needs_confirmation') {
      try {
        const full = await api.getReport(r.id)
        row._lowObs = (full.observations || [])
          .filter((o) => o.needs_confirm && !o.confirmed)
          .map((o) => ({ ...o, _val: o.value_num }))
      } catch { /* 保底仍可确认日期 */ }
    }
    out.push(row)
  }
  items.value = out
}

async function confirm(r) {
  r._saving = true
  try {
    const res = await api.confirmReport(r.id, {
      report_date: r._date || null,
      confirmations: r._lowObs.map((o) => ({
        observation_id: o.id, value_num: o._val,
      })),
    })
    Object.assign(r, res, { _lowObs: [], _saving: false })
    if (summary.value) {
      summary.value.needs_confirmation -= 1
      summary.value.ready += 1
    }
    await loadScope()
  } catch (e) {
    r._saving = false
    alert(e.message)
  }
}

async function retry(r) {
  try {
    const res = await api.retryReport(r.id)
    Object.assign(r, res)
    await loadScope()
  } catch (e) { alert(e.message) }
}

async function loadScope() {
  try { scope.value = await api.analysisScope(session.profileId) } catch { /* 空 */ }
}

onMounted(loadScope)
</script>

<style scoped>
.drop { display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: var(--sp-6) var(--sp-4); border: 1.5px dashed var(--brand-500);
  border-radius: var(--r-md); background: var(--brand-050);
  color: var(--brand-800); cursor: pointer; text-align: center; transition: .16s; }
.drop:hover { background: var(--brand-100); }
.drop.busy { cursor: wait; }
.drop-ico { color: var(--brand-600); }
.drop b { font-size: 14px; }

.ledger .lg-grid { display: grid; grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-2); margin: var(--sp-3) 0; text-align: center; }
.lg-grid b { display: block; font-size: 20px; }
.lg-grid span { font-size: 11px; color: var(--ink-500); }
.lg-grid .ok { color: var(--ok); }
.lg-grid .warn { color: var(--warn); }
.lg-grid .bad { color: var(--danger); }
.lg-meta { display: flex; flex-wrap: wrap; gap: var(--sp-3);
  font-size: 12px; color: var(--ink-500);
  border-top: 1px dashed var(--line); padding-top: var(--sp-2); }

.rep .st { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.st-ready { background: var(--ok); }
.st-needs_confirmation { background: var(--warn); }
.st-failed { background: var(--danger); }
.st-processing, .st-uploaded { background: var(--ink-300); }
.fn { font-size: 14px; display: block; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; max-width: 46vw; }
.meta { display: block; }
.need { color: var(--warn); font-style: normal; }
.dup { margin-top: var(--sp-2); }
.confirm { margin-top: var(--sp-3); padding-top: var(--sp-3);
  border-top: 1px dashed var(--line); display: flex;
  flex-direction: column; gap: var(--sp-3); }
.obn { min-width: 96px; font-size: 13px; }
.scope { border-color: var(--gold-500); }
</style>

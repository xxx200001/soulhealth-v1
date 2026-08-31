<template>
  <div class="page stack">
    <!-- 选择与上传 -->
    <section class="card fade-in">
      <div class="card-title"><span class="dot"></span>上传健康资料</div>
      <p class="muted" style="margin: 6px 0 var(--sp-3)">
        支持图片 / 拍照 / PDF，单次建议选择 1~3 份；每份独立高精识别、秒级入档
      </p>

      <!-- 隐藏文件输入：图片专用（兼容所有安卓机型） -->
      <input ref="inputImage" type="file" multiple accept="image/*" hidden
             :disabled="busy" @change="onPick" />
      <!-- 隐藏文件输入：PDF 专用（解决 OPPO/Vivo/小米/华为 等国产安卓 image/* 劫持问题） -->
      <input ref="inputPdf" type="file" multiple accept="application/pdf,.pdf" hidden
             :disabled="busy" @change="onPick" />

      <div class="drop" :class="{ busy }" v-if="!busy">
        <span class="drop-ico" v-html="icoUp"></span>
        <b>点击选择文件（单次建议 1~3 份）</b>
        <div class="drop-btns">
          <button type="button" class="drop-btn drop-btn-img" @click.stop="$refs.inputImage.click()">
            <span class="drop-btn-ico">🖼</span> 图片 / 拍照
          </button>
          <button type="button" class="drop-btn drop-btn-pdf" @click.stop="$refs.inputPdf.click()">
            <span class="drop-btn-ico">📄</span> PDF 文件
          </button>
        </div>
        <span class="tiny">系统将自动并发识别并入档，一份失败不影响其他；
          原件完整保存，识别结果可随时回溯</span>
      </div>
      <div class="drop busy" v-else>
        <span class="spin"></span>
        <b>{{ `正在极速并发识别中（共 ${total} 份）…` }}</b>
      </div>
      <div v-if="busy" class="bar" style="margin-top: var(--sp-3)">
        <span :style="{ width: (doing / Math.max(total,1)) * 100 + '%' }"></span>
      </div>
      <p v-if="notice" class="alert fade-in" :class="'alert-' + notice.type"
         style="margin-top: var(--sp-3)">{{ notice.text }}</p>
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
        <div class="row row-between" style="align-items: center">
          <div class="row" style="align-items: center; gap: 8px; flex: 1; min-width: 0">
            <span class="st" :class="`st-${r.status}`"></span>
            <span class="grow" style="min-width: 0">
              <b class="fn clickable" @click="openLightbox(r)" :title="'点击查看原图：' + r.source_filename">
                {{ r.source_filename }}
                <span class="ico-eye" v-html="icoEye"></span>
              </b>
              <span class="tiny meta">
                {{ typeCN(r.report_type) }}
                <template v-if="r.report_date"> · 检查日期 {{ r.report_date }}
                  <em v-if="!r.date_confirmed" class="need">（待确认）</em>
                </template>
                <template v-if="r.stats?.observations">
                  · 提取 {{ r.stats.observations }} 项
                </template>
                <template v-if="r.stats?.findings">
                  · 提取 {{ r.stats.findings }} 项所见
                </template>
              </span>
            </span>
          </div>
          <div class="row" style="gap: 6px; align-items: center; flex: none">
            <button v-if="r.id && !r._local" class="btn btn-sm btn-quiet"
                    style="padding: 3px 8px; font-size: 12px"
                    @click="openLightbox(r)">
              查看原图
            </button>
            <span class="badge clickable" :class="statusBadge(r.status)"
                  @click="r.status === 'needs_confirmation' ? openLightbox(r) : null"
                  :title="r.status === 'needs_confirmation' ? '点击查看原图核对' : ''">
              {{ statusCN(r.status) }}
            </span>
          </div>
        </div>

        <p v-if="r.duplicate_of" class="alert alert-info dup">
          与已有报告日期/类型相同，疑似重复——已照常保存，你可以在档案中对比后自行删除
        </p>
        <p v-if="r.error" class="alert alert-danger dup">
          {{ r.error }}
          <button class="btn btn-sm btn-ghost" style="margin-left:8px" @click="retry(r)">重试</button>
        </p>

        <!-- 待确认：原图核对 + 日期 + 低置信数值就地处理（F-UP-05 / AC-05） -->
        <div v-if="r.status === 'needs_confirmation'" class="confirm">
          <!-- 原图核对缩略窗 -->
          <div class="preview-box">
            <div class="row-between" style="align-items: center; margin-bottom: 6px">
              <span class="preview-tag">
                <span class="dot-warn"></span>
                <b>原图核对</b>：请查看原图上的实际检查日期
              </span>
              <button class="btn btn-sm btn-gold" style="padding: 2px 10px; font-size: 12px"
                      @click="openLightbox(r)">
                🔍 点击放大查看完整原图
              </button>
            </div>
            <div class="thumb-container clickable" @click="openLightbox(r)">
              <img v-if="r._fileUrl && !isPdf(r)" :src="r._fileUrl" alt="报告缩略图" class="thumb-img" />
              <div v-else-if="r._fileUrl && isPdf(r)" class="pdf-placeholder">
                <span>📄 PDF 文档（点击全屏浏览）</span>
              </div>
              <div v-else class="thumb-loading">
                <span class="spin"></span>
                <span class="tiny">正在加载原图预览…</span>
              </div>
              <div class="thumb-mask">
                <span class="thumb-mask-text">🔍 点击查看高清大图</span>
              </div>
            </div>
          </div>

          <div v-if="!r.date_confirmed" class="field">
            <label class="label">这份报告的检查日期（按上方原图核对）</label>
            <div class="row" style="align-items: center; gap: 8px">
              <input v-model="r._date" type="date" class="input" style="max-width: 180px" />
              <span class="tiny muted">填入报告单印刷的实际日期</span>
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
          <button class="btn btn-primary btn-sm btn-block" :disabled="r._saving" @click="confirm(r)">
            <span v-if="r._saving" class="spin"></span>确认并入档
          </button>
        </div>
      </div>
    </section>

    <!-- 原图全屏放大灯箱 Modal -->
    <div v-if="lightbox.show" class="lightbox-overlay fade-in" @click.self="closeLightbox">
      <div class="lightbox-content">
        <div class="lightbox-header">
          <div>
            <b class="lightbox-title">{{ lightbox.report?.source_filename }}</b>
            <span class="tiny muted" style="margin-left: 8px">
              {{ typeCN(lightbox.report?.report_type) }} ·
              原记录日期 {{ lightbox.report?.report_date || '待确认' }}
            </span>
          </div>
          <div class="row" style="gap: 8px; align-items: center">
            <button class="btn btn-sm btn-quiet" @click="zoomIn" title="放大">＋ 放大</button>
            <button class="btn btn-sm btn-quiet" @click="zoomOut" title="缩小">－ 缩小</button>
            <button class="btn btn-sm btn-quiet" @click="resetZoom" title="重置">1:1</button>
            <button class="lightbox-close" @click="closeLightbox" title="关闭 (Esc)">✕</button>
          </div>
        </div>
        <div class="lightbox-body">
          <div class="lightbox-img-wrap" :style="{ transform: `scale(${lightbox.zoom})` }">
            <img v-if="lightbox.url && !isPdf(lightbox.report)" :src="lightbox.url"
                 alt="原图高清预览" class="lightbox-img" />
            <iframe v-else-if="lightbox.url && isPdf(lightbox.report)" :src="lightbox.url"
                    class="lightbox-iframe" title="PDF报告原件"></iframe>
            <div v-else-if="lightbox.loading" class="lightbox-loading">
              <span class="spin"></span>
              <p style="margin-top: 8px">正在获取原图…</p>
            </div>
            <p v-else class="alert alert-warn">原件暂时无法预览</p>
          </div>
        </div>
        <div class="lightbox-footer">
          <span class="tiny muted">提示：双指捏合或点击放大/缩小按钮可缩放查看报告文字与日期详情</span>
          <button class="btn btn-primary btn-sm" @click="closeLightbox">关闭预览</button>
        </div>
      </div>
    </div>

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
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'
import { useSessionStore } from '../store/session'

const session = useSessionStore()
const busy = ref(false)
const doing = ref(0)
const total = ref(0)
const summary = ref(null)
const items = ref([])
const scope = ref(null)
const notice = ref(null)   // { type: 'ok' | 'warn' | 'danger', text }

const icoUp = '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4M7.5 8.5 12 4l4.5 4.5"/><path d="M4 15v4a1.5 1.5 0 0 0 1.5 1.5h13A1.5 1.5 0 0 0 20 19v-4"/></svg>'
const icoEye = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:middle; margin-left:4px; opacity:0.75"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>'

const lightbox = ref({
  show: false,
  report: null,
  url: '',
  zoom: 1,
  loading: false,
})

function isPdf(r) {
  return (r?.source_filename || '').toLowerCase().endsWith('.pdf')
}

async function openLightbox(r) {
  if (!r?.id || r._local) return
  lightbox.value.show = true
  lightbox.value.report = r
  lightbox.value.zoom = 1
  lightbox.value.loading = true

  if (r._fileUrl) {
    lightbox.value.url = r._fileUrl
    lightbox.value.loading = false
    return
  }

  try {
    const res = await fetch(api.reportFileUrl(r.id), {
      headers: { Authorization: `Bearer ${localStorage.getItem('sh_token')}` },
    })
    if (res.ok) {
      const blob = await res.blob()
      const u = URL.createObjectURL(blob)
      r._fileUrl = u
      lightbox.value.url = u
    }
  } catch (err) {
    console.error('获取原图失败', err)
  } finally {
    lightbox.value.loading = false
  }
}

function closeLightbox() {
  lightbox.value.show = false
  lightbox.value.zoom = 1
}

function zoomIn() {
  lightbox.value.zoom = Math.min(3.0, lightbox.value.zoom + 0.25)
}

function zoomOut() {
  lightbox.value.zoom = Math.max(0.5, lightbox.value.zoom - 0.25)
}

function resetZoom() {
  lightbox.value.zoom = 1.0
}

function onKeydown(e) {
  if (e.key === 'Escape' && lightbox.value.show) {
    closeLightbox()
  }
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
function statusCN(s) {
  return { uploaded: '排队中', processing: '识别中', ready: '已识别',
           needs_confirmation: '需要确认', failed: '失败' }[s] || s
}
function statusBadge(s) {
  return { ready: 'badge-ok', needs_confirmation: 'badge-warn',
           failed: 'badge-danger' }[s] || 'badge-quiet'
}

// 单次选择的份数上限（保障秒级并发识别与防止超时）；并发上传，单份失败不影响其他
const MAX_PICK = 3

async function onPick(e) {
  let files = [...e.target.files]
  e.target.value = ''
  if (!files.length) return
  notice.value = null
  if (files.length > MAX_PICK) {
    files = files.slice(0, MAX_PICK)
    notice.value = { type: 'warn',
      text: `为了保障秒级极速识别与稳定性，单次最多选择 ${MAX_PICK} 份；已为您保留前 ${MAX_PICK} 份开始并发识别，其余资料请稍后上传` }
  }
  busy.value = true
  total.value = files.length
  doing.value = 0
  summary.value = null
  items.value = []
  const merged = { total: 0, ready: 0, needs_confirmation: 0, failed: 0,
                   observations: 0, comparable_codes: 0, date_span: null }
  try {
    // 并发快速处理（避免单线排队超时）
    const tasks = files.map(async (f) => {
      try {
        const res = await api.uploadReports(session.profileId, [f])
        mergeSummary(merged, res)
        await hydrate(res.reports)
      } catch (err) {
        merged.total += 1
        merged.failed += 1
        items.value.push({
          id: `local-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`,
          status: 'failed', source_filename: f.name,
          error: `上传解析失败：${err.message}`,
          _local: true, _file: f, _lowObs: [], _saving: false, _fileUrl: '',
        })
      } finally {
        doing.value += 1
      }
    })
    await Promise.allSettled(tasks)
    summary.value = merged
    notice.value = buildNotice(merged)
  } finally {
    busy.value = false
    doing.value = 0
    await loadScope()
  }
}

function mergeSummary(m, res) {
  m.total += res.total
  m.ready += res.ready
  m.needs_confirmation += res.needs_confirmation
  m.failed += res.failed
  m.observations += res.observations
  m.comparable_codes = res.comparable_codes   // 档案级口径，取最新值
  if (res.date_span) {
    m.date_span = m.date_span
      ? [m.date_span[0] < res.date_span[0] ? m.date_span[0] : res.date_span[0],
         m.date_span[1] > res.date_span[1] ? m.date_span[1] : res.date_span[1]]
      : [...res.date_span]
  }
}

function buildNotice(m) {
  const okCount = m.ready + m.needs_confirmation
  if (!m.failed && !m.needs_confirmation) {
    return { type: 'ok', text: `本次 ${m.total} 份已全部上传成功并识别入档 ✓` }
  }
  if (!m.failed) {
    return { type: 'ok',
      text: `本次 ${m.total} 份已全部上传成功 ✓ 其中 ${m.needs_confirmation} 份` +
            '需要你在下方核对原图并确认日期或数值后入档' }
  }
  if (okCount) {
    return { type: 'warn',
      text: `已成功上传 ${okCount} 份、失败 ${m.failed} 份；失败的条目可在下方单独重试` }
  }
  return { type: 'danger',
    text: `本次 ${m.total} 份上传失败，请检查网络后重试` }
}

async function hydrate(list) {
  // 为待确认报告拉取低置信观测项，就地编辑；逐份追加到列表
  for (const r of list) {
    const row = { ...r, _date: r.report_date || '', _lowObs: [], _saving: false, _fileUrl: '' }
    if (r.status === 'needs_confirmation') {
      try {
        const full = await api.getReport(r.id)
        row._lowObs = (full.observations || [])
          .filter((o) => o.needs_confirm && !o.confirmed)
          .map((o) => ({ ...o, _val: o.value_num }))
      } catch { /* 保底仍可确认日期 */ }
    }
    items.value.push(row)
    // 异步加载缩略图
    loadThumb(row)
  }
}

async function loadThumb(row) {
  if (!row.id || row._local) return
  try {
    const res = await fetch(api.reportFileUrl(row.id), {
      headers: { Authorization: `Bearer ${localStorage.getItem('sh_token')}` },
    })
    if (res.ok) {
      row._fileUrl = URL.createObjectURL(await res.blob())
    }
  } catch { /* 忽略缩略图静默失败 */ }
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
  // 网络层失败的文件：服务端没有记录，直接重新上传这一份
  if (r._local && r._file) {
    r.error = ''
    r.status = 'processing'
    try {
      const res = await api.uploadReports(session.profileId, [r._file])
      const nr = res.reports[0]
      Object.assign(r, nr, { _local: false, _file: null, _fileUrl: '' })
      if (nr.status === 'needs_confirmation') {
        try {
          const full = await api.getReport(nr.id)
          r._date = nr.report_date || ''
          r._lowObs = (full.observations || [])
            .filter((o) => o.needs_confirm && !o.confirmed)
            .map((o) => ({ ...o, _val: o.value_num }))
        } catch { /* 保底仍可确认日期 */ }
      }
      loadThumb(r)
      if (summary.value) {
        summary.value.failed -= 1
        if (nr.status === 'ready') summary.value.ready += 1
        else if (nr.status === 'needs_confirmation') summary.value.needs_confirmation += 1
        else summary.value.failed += 1
        notice.value = buildNotice(summary.value)
      }
    } catch (e) {
      r.status = 'failed'
      r.error = `上传请求失败：${e.message}`
    }
    await loadScope()
    return
  }
  try {
    const res = await api.retryReport(r.id)
    Object.assign(r, res)
    await loadScope()
  } catch (e) { alert('重试失败，请稍后再试') }
}

async function loadScope() {
  try { scope.value = await api.analysisScope(session.profileId) } catch { /* 空 */ }
}

onMounted(() => {
  loadScope()
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  // 清理 blob URLs
  for (const r of items.value) {
    if (r._fileUrl) URL.revokeObjectURL(r._fileUrl)
  }
})
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

/* 双按钮行：图片 / PDF 分离，解决国产安卓 file picker 兼容性 */
.drop-btns { display: flex; gap: 10px; margin: 8px 0 4px; width: 100%; justify-content: center; }
.drop-btn { display: inline-flex; align-items: center; gap: 6px; padding: 10px 20px;
  border: 1.5px solid var(--brand-400); border-radius: var(--r-sm); background: #fff;
  color: var(--brand-700); font-size: 14px; font-weight: 600; cursor: pointer;
  transition: all .16s; flex: 1; justify-content: center; max-width: 180px; }
.drop-btn:hover { background: var(--brand-100); border-color: var(--brand-600); }
.drop-btn:active { transform: scale(0.97); }
.drop-btn-ico { font-size: 18px; }

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
.fn { font-size: 14px; display: inline-flex; align-items: center; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; max-width: 44vw; }
.clickable { cursor: pointer; }
.clickable:hover { color: var(--brand-700); }
.ico-eye { display: inline-flex; align-items: center; }
.meta { display: block; }
.need { color: var(--warn); font-style: normal; }
.dup { margin-top: var(--sp-2); }
.confirm { margin-top: var(--sp-3); padding-top: var(--sp-3);
  border-top: 1px dashed var(--line); display: flex;
  flex-direction: column; gap: var(--sp-3); }
.obn { min-width: 96px; font-size: 13px; }
.scope { border-color: var(--gold-500); }

/* 原图核对缩略窗 */
.preview-box { background: var(--surface-sunk); border: 1px solid var(--line);
  border-radius: var(--r-sm); padding: 10px 12px; }
.preview-tag { font-size: 12px; display: inline-flex; align-items: center; gap: 4px; color: var(--ink-700); }
.dot-warn { width: 7px; height: 7px; border-radius: 50%; background: var(--warn); display: inline-block; }
.thumb-container { position: relative; width: 100%; height: 140px; background: #00000008;
  border-radius: var(--r-sm); overflow: hidden; border: 1px dashed var(--line-strong);
  display: flex; align-items: center; justify-content: center; margin-top: 6px; }
.thumb-img { width: 100%; height: 100%; object-fit: contain; display: block; }
.thumb-loading { display: flex; flex-direction: column; align-items: center; gap: 6px; color: var(--ink-400); }
.pdf-placeholder { font-size: 13px; color: var(--brand-700); font-weight: 500; }
.thumb-mask { position: absolute; inset: 0; background: rgba(0,0,0,0.38); opacity: 0;
  display: flex; align-items: center; justify-content: center; transition: opacity 0.2s; }
.thumb-container:hover .thumb-mask, .thumb-container:active .thumb-mask { opacity: 1; }
.thumb-mask-text { color: #fff; font-size: 13px; font-weight: 600; background: rgba(0,0,0,0.65);
  padding: 4px 12px; border-radius: 20px; backdrop-filter: blur(4px); }

/* 原图放大灯箱 Modal */
.lightbox-overlay { position: fixed; inset: 0; z-index: 1000; background: rgba(0, 0, 0, 0.78);
  backdrop-filter: blur(6px); display: flex; align-items: center; justify-content: center; padding: var(--sp-3); }
.lightbox-content { background: var(--surface); width: 100%; max-width: 860px; height: 90vh;
  border-radius: var(--r-md); box-shadow: 0 20px 40px rgba(0,0,0,0.3); display: flex; flex-direction: column;
  overflow: hidden; animation: zoomIn 0.2s ease-out; }
.lightbox-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px;
  border-bottom: 1px solid var(--line); background: var(--surface-card); }
.lightbox-title { font-size: 15px; color: var(--ink-900); }
.lightbox-close { width: 28px; height: 28px; border-radius: 50%; border: none; background: var(--surface-sunk);
  color: var(--ink-700); font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.lightbox-close:hover { background: var(--line-strong); }
.lightbox-body { flex: 1; overflow: auto; display: flex; align-items: center; justify-content: center;
  background: #111; padding: var(--sp-4); }
.lightbox-img-wrap { transition: transform 0.2s ease-out; max-width: 100%; max-height: 100%; }
.lightbox-img { max-width: 100%; max-height: 70vh; object-fit: contain; border-radius: 4px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
.lightbox-iframe { width: 100%; height: 70vh; border: none; background: #fff; }
.lightbox-loading { color: #fff; display: flex; flex-direction: column; align-items: center; }
.lightbox-footer { display: flex; justify-content: space-between; align-items: center; padding: 10px 16px;
  border-top: 1px solid var(--line); background: var(--surface-card); }

@keyframes zoomIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
</style>

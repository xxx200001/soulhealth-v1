<template>
  <div class="page stack" v-if="report">
    <!-- 元信息 -->
    <section class="card fade-in">
      <div class="row-between">
        <div>
          <h3 style="font-size:17px">{{ report.source_filename || '健康资料' }}</h3>
          <p class="tiny">
            {{ typeCN(report.report_type) }} ·
            检查日期 {{ report.report_date || '待确认' }}
            <em v-if="!report.date_confirmed" class="warnem">（待确认）</em>
            · 上传于 {{ report.upload_time?.slice(0, 10) }}
          </p>
        </div>
        <span class="badge" :class="stBadge(report.status)">{{ stCN(report.status) }}</span>
      </div>
      <p v-if="report.duplicate_of" class="alert alert-info" style="margin-top: var(--sp-2)">
        与档案中另一份报告日期/类型相同，疑似重复上传
      </p>
      <p v-if="report.error" class="alert alert-danger" style="margin-top: var(--sp-2)">
        {{ report.error }}
      </p>
    </section>

    <!-- 待确认处理（与上传页一致的就地确认） -->
    <section v-if="report.status === 'needs_confirmation'" class="card fade-in confirmc">
      <div class="card-title"><span class="dot"></span>需要你的确认</div>
      <div v-if="!report.date_confirmed" class="field" style="margin-top: var(--sp-2)">
        <label class="label">检查日期</label>
        <input v-model="editDate" type="date" class="input" style="max-width: 180px" />
      </div>
      <div v-if="lowObs.length" class="field" style="margin-top: var(--sp-2)">
        <label class="label">低置信数值核对</label>
        <div v-for="o in lowObs" :key="o.id" class="row" style="margin-bottom: 6px">
          <span style="min-width: 110px; font-size: 13px">{{ o.original_name || o.code }}</span>
          <input v-model.number="o._val" type="number" step="any" class="input"
                 style="max-width: 130px" />
          <span class="tiny">{{ o.unit }}</span>
        </div>
      </div>
      <button class="btn btn-primary btn-sm" :disabled="saving" @click="confirmNow">
        <span v-if="saving" class="spin"></span>确认并入档
      </button>
    </section>

    <!-- 原件预览（AC-09：证据可回到原始报告） -->
    <section class="card fade-in">
      <div class="row-between">
        <div class="card-title"><span class="dot"></span>原件</div>
        <a v-if="fileUrl" :href="fileUrl" :download="report.source_filename"
           class="tiny">下载原件 ›</a>
      </div>
      <div class="orig">
        <img v-if="fileUrl && !isPdf" :src="fileUrl" alt="报告原件" />
        <iframe v-else-if="fileUrl && isPdf" :src="fileUrl" title="报告原件"></iframe>
        <p v-else-if="fileMissing" class="tiny" style="padding: var(--sp-4)">
          该报告为演示数据或原件已移除，未存储文件
        </p>
        <span v-else class="spin" style="margin: var(--sp-4)"></span>
      </div>
    </section>

    <!-- 提取的指标 -->
    <section v-if="report.observations?.length" class="card fade-in">
      <div class="card-title"><span class="dot"></span>
        提取的指标（{{ report.observations.length }} 项）</div>
      <div class="table-wrap" style="margin-top: var(--sp-2)">
        <table class="table">
          <thead><tr><th>报告原名</th><th>数值</th><th>参考</th><th>判读</th></tr></thead>
          <tbody>
            <tr v-for="o in report.observations" :key="o.id">
              <td>
                <b>{{ o.original_name || o.code }}</b>
                <div class="tiny">
                  <template v-if="o.code">标准化 → {{ o.code }}
                    <em v-if="o.match_method !== 'exact'" class="mm">
                      （{{ mmCN(o.match_method) }}）</em>
                  </template>
                  <template v-else>未能匹配标准指标</template>
                </div>
              </td>
              <td class="num">
                {{ o.value_num ?? o.value_text ?? '—' }} {{ o.unit }}
                <span v-if="o.needs_confirm && !o.confirmed"
                      class="badge badge-warn" style="margin-left:4px">待确认</span>
              </td>
              <td class="tiny">
                <template v-if="o.ref_low != null || o.ref_high != null">
                  {{ o.ref_low ?? '' }}~{{ o.ref_high ?? '' }}
                </template>
                <template v-else>—</template>
              </td>
              <td>
                <span class="badge" :class="o.grade ? 'badge-warn' : 'badge-ok'">
                  {{ gradeCN(o.grade) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 检查所见 -->
    <section v-if="report.findings?.length" class="card fade-in">
      <div class="card-title"><span class="dot"></span>检查所见</div>
      <div v-for="(f, i) in report.findings" :key="i" class="finding">
        <b>{{ f.organ }}</b>
        <p>{{ f.description }}</p>
      </div>
    </section>

    <!-- 抽取元信息 -->
    <section class="card-flat fade-in tiny">
      识别引擎：{{ report.engine || '—' }}
      <template v-if="report.stats">
        · 提取 {{ report.stats.observations }} 项
        · 标准化命中 {{ report.stats.matched }} 项
        <template v-if="report.stats.low_confidence">
          · 低置信 {{ report.stats.low_confidence }} 项
        </template>
      </template>
    </section>
  </div>
  <div v-else class="page"><div class="empty"><span class="spin"></span></div></div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'

const route = useRoute()
const report = ref(null)
const fileUrl = ref('')
const fileMissing = ref(false)
const editDate = ref('')
const lowObs = ref([])
const saving = ref(false)

const isPdf = computed(() =>
  (report.value?.source_filename || '').toLowerCase().endsWith('.pdf'))

function typeCN(t) {
  return { lab_report: '检验报告', ultrasound_report: '超声检查',
           checkup: '体检报告', other: '健康资料' }[t] || '健康资料'
}
function stCN(s) {
  return { ready: '已识别', needs_confirmation: '待确认', failed: '失败',
           processing: '识别中', uploaded: '排队中' }[s] || s
}
function stBadge(s) {
  return { ready: 'badge-ok', needs_confirmation: 'badge-warn',
           failed: 'badge-danger' }[s] || 'badge-quiet'
}
function gradeCN(g) {
  return { '-3': '重度偏低', '-2': '中度偏低', '-1': '轻度偏低', 0: '正常',
           1: '轻度偏高', 2: '中度偏高', 3: '重度偏高' }[String(g ?? 0)] || '正常'
}
function mmCN(m) {
  return { fold: '容错匹配', fuzzy: '相似匹配' }[m] || m
}

async function load() {
  report.value = await api.getReport(route.params.rid)
  editDate.value = report.value.report_date || ''
  lowObs.value = (report.value.observations || [])
    .filter((o) => o.needs_confirm && !o.confirmed)
    .map((o) => ({ ...o, _val: o.value_num }))
  loadFile()
}

async function loadFile() {
  if (!report.value?.stored_path) { fileMissing.value = true; return }
  try {
    // 带鉴权抓取原件 → blob URL（<img src> 无法附带 Authorization）
    const res = await fetch(api.reportFileUrl(report.value.id), {
      headers: { Authorization: `Bearer ${localStorage.getItem('sh_token')}` },
    })
    if (!res.ok) { fileMissing.value = true; return }
    fileUrl.value = URL.createObjectURL(await res.blob())
  } catch { fileMissing.value = true }
}

async function confirmNow() {
  saving.value = true
  try {
    await api.confirmReport(report.value.id, {
      report_date: editDate.value || null,
      confirmations: lowObs.value.map((o) => ({
        observation_id: o.id, value_num: o._val })),
    })
    await load()
  } catch (e) { alert(e.message) }
  finally { saving.value = false }
}

onMounted(load)
onBeforeUnmount(() => { if (fileUrl.value) URL.revokeObjectURL(fileUrl.value) })
</script>

<style scoped>
.warnem { color: var(--warn); font-style: normal; }
.confirmc { border-color: var(--warn); }
.orig { margin-top: var(--sp-2); border: 1px solid var(--line);
  border-radius: var(--r-sm); overflow: hidden; background: var(--surface-sunk);
  display: flex; justify-content: center; }
.orig img { max-width: 100%; display: block; }
.orig iframe { width: 100%; height: 420px; border: none; }
.mm { color: var(--gold-700); font-style: normal; }
.finding { border-left: 3px solid var(--info); background: var(--info-bg);
  border-radius: 0 var(--r-sm) var(--r-sm) 0; padding: 8px 12px;
  margin-top: var(--sp-2); }
.finding b { font-size: 13.5px; color: var(--info); }
.finding p { margin: 3px 0 0; font-size: 13.5px; color: var(--ink-700); }
</style>

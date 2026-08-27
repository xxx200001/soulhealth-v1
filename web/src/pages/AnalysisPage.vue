<template>
  <div class="page stack">
    <!-- 空态：还没有可分析资料 -->
    <EmptyState v-if="loaded && !assessment && !running" icon="◎"
                text="还没有分析结果">
      <p class="muted" style="margin: 6px 0 var(--sp-3)">
        上传健康资料，或先通过「问问我的健康」记录信息
      </p>
      <div class="row" style="justify-content:center">
        <button class="btn btn-primary" @click="$router.push('/upload')">上传健康资料</button>
        <button class="btn btn-ghost" @click="run(true)">直接分析</button>
      </div>
    </EmptyState>

    <template v-else>
      <!-- 顶部：分析元信息 + 数据范围（AC-06） -->
      <section class="card fade-in headc">
        <div class="row-between">
          <div>
            <div class="card-title"><span class="dot"></span>我的健康分析</div>
            <p class="tiny" v-if="assessment">
              分析时间 {{ assessment.created_at?.slice(0, 10) }}
              <template v-if="assessment.cached"> · 数据未变化，展示既有结果</template>
            </p>
          </div>
          <button class="btn btn-ghost btn-sm" :disabled="running" @click="run(true)">
            <span v-if="running" class="spin"></span>{{ running ? '分析中' : '重新分析' }}
          </button>
        </div>
        <button class="scope-line" @click="scopeOpen = !scopeOpen">
          本次分析使用
          <b class="num">{{ scope?.report_count ?? '…' }}</b> 份资料 ·
          可比较指标 <b class="num">{{ scope?.comparable_codes?.length ?? '…' }}</b> 项
          <span class="tiny">{{ scopeOpen ? '收起 ▴' : '查看范围 ▾' }}</span>
        </button>
        <div v-if="scopeOpen && scope" class="row wrap" style="margin-top: var(--sp-2)">
          <span v-for="rp in scope.reports" :key="rp.id" class="src">
            {{ typeCN(rp.type) }} {{ rp.date || '' }}
          </span>
        </div>
      </section>

      <!-- DRP 慢病进展风险概率预测卡片（1Y/3Y/5Y 时程切换） -->
      <section v-if="pred" class="card fade-in pred-card">
        <div class="row-between" style="align-items: center">
          <div class="card-title">
            <span class="dot" :style="{ background: currentHorizon?.tier_color || 'var(--gold-500)' }"></span>
            未来慢病进展风险概率预测
          </div>
          <span class="badge" :style="{ background: currentHorizon?.tier_color + '22', color: currentHorizon?.tier_color, borderColor: currentHorizon?.tier_color }">
            {{ currentHorizon?.tier_cn }}区间
          </span>
        </div>

        <p class="tiny muted" style="margin: 4px 0 10px">
          {{ pred.target }} · {{ pred.evidence }}
        </p>

        <!-- 时程切换 Tabs (1Y / 3Y / 5Y) -->
        <div class="horizon-tabs">
          <button v-for="h in pred.horizons" :key="h.horizon"
                  class="horizon-tab"
                  :class="{ active: selectedHorizon === h.horizon }"
                  @click="selectedHorizon = h.horizon">
            <span class="h-label">{{ h.horizon_label }}</span>
            <b class="h-prob" :style="{ color: selectedHorizon === h.horizon ? h.tier_color : 'inherit' }">
              {{ h.percentage }}
            </b>
          </button>
        </div>

        <!-- 当前选定时程的详细卡片 -->
        <div class="horizon-detail" v-if="currentHorizon">
          <div class="row-between" style="align-items: center; margin-bottom: 8px">
            <div class="row" style="align-items: baseline; gap: 6px">
              <span class="pred-big-num" :style="{ color: currentHorizon.tier_color }">{{ currentHorizon.percentage }}</span>
              <span class="tiny muted">校准进展概率</span>
            </div>
            <div class="pred-advice">
              <span class="tiny">建议随访：</span>
              <b>{{ currentHorizon.follow_up_advice }}</b>
            </div>
          </div>
          <p class="pred-summary">{{ currentHorizon.summary }}</p>
        </div>

        <!-- SHAP 风险归因分析（推高 vs 降低因子） -->
        <div v-if="pred.top_drivers?.length" class="driver-section">
          <div class="driver-title">
            <span class="dot-sm"></span>
            <b>Top 风险归因分析（哪些因素在推高/降低风险）</b>
          </div>
          <div class="driver-list">
            <div v-for="d in pred.top_drivers" :key="d.code" class="driver-item"
                 :class="d.direction === 'increase' ? 'dr-up' : 'dr-down'">
              <div class="row-between" style="align-items: center">
                <div class="row" style="gap: 6px; align-items: center">
                  <span class="dr-tag" :class="d.direction === 'increase' ? 'tag-up' : 'tag-down'">
                    {{ d.direction_cn }}
                  </span>
                  <b class="dr-name">{{ d.name }}</b>
                  <span v-if="d.current_value !== null" class="tiny dr-val">
                    ({{ d.current_value }}{{ d.unit }})
                  </span>
                </div>
                <div class="dr-bar-wrap">
                  <div class="dr-bar" :style="{ width: Math.min(100, d.impact * 80) + '%', background: d.direction === 'increase' ? 'var(--danger)' : 'var(--ok)' }"></div>
                </div>
              </div>
              <p class="dr-reason">{{ d.reason }}</p>
            </div>
          </div>
        </div>
      </section>

      <!-- 临床衍生复合评分卡片（AST/ALT, FIB-4, eGFR, TyG...） -->
      <section v-if="pred?.ratios?.length" class="card fade-in ratios-card">
        <button class="row-between fold" @click="ratiosOpen = !ratiosOpen">
          <span class="card-title">
            <span class="dot" style="background: var(--brand-600)"></span>
            临床衍生复合指数（{{ pred.ratios.length }} 项）
          </span>
          <span class="tiny">{{ ratiosOpen ? '收起 ▴' : '展开 ▾' }}</span>
        </button>
        <div v-if="ratiosOpen" class="ratios-grid" style="margin-top: 10px">
          <div v-for="rt in pred.ratios" :key="rt.key" class="ratio-item">
            <div class="row-between" style="align-items: center">
              <b class="ratio-name">{{ rt.name }}</b>
              <div class="row" style="gap: 6px; align-items: center">
                <b class="ratio-val num">{{ rt.value }} {{ rt.unit }}</b>
                <span class="ratio-badge" :class="`rb-${rt.status}`">
                  {{ rt.status === 'danger' ? '偏高' : (rt.status === 'warn' ? '留意' : '良好') }}
                </span>
              </div>
            </div>
            <p class="ratio-interp">{{ rt.interpretation }}</p>
            <span class="tiny ratio-ref">参考范围：{{ rt.reference }} · {{ rt.literature }}</span>
          </div>
        </div>
      </section>

      <!-- TOP 1–3（AC-07：首屏明确第一优先与依据） -->
      <section v-for="it in tops" :key="it.id" class="card top card-clickable fade-in"
               :class="`b-${it.level}`" @click="$router.push(`/issue/${it.id}`)">
        <div class="row-between">
          <div class="row" style="gap: 10px">
            <span class="rk num">{{ it.rank }}</span>
            <h3 class="tt">{{ it.title }}</h3>
          </div>
          <LevelBadge :level="it.level" />
        </div>
        <p class="sm">{{ it.summary }}</p>
        <div class="why">
          <b>为什么排在第 {{ it.rank }}：</b>{{ (it.detail.why_priority || [])[0] }}
        </div>
        <div class="row wrap ev">
          <span v-for="(e, i) in keyEvidence(it)" :key="i" class="evi">
            <b>{{ e.name }}</b> {{ e.value }}{{ e.unit }}
            <em>{{ e.date }}</em>
            <SourceTag :text="e.source" />
          </span>
        </div>
        <div class="more-cta">
          <span class="more-icon">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
            </svg>
          </span>
          <div class="more-content">
            <span class="more-title">查看完整依据与行动建议</span>
            <span class="more-sub">深度医学解释 · 本次VS上次对比 · 趋势预测 · 定制方案</span>
          </div>
          <span class="more-arrow">›</span>
        </div>
      </section>

      <!-- 分析完成 → 直达方案（反馈修复：分析后主动提示生成专属食疗与药食同源配方） -->
      <section v-if="assessment" class="card fade-in cta">
        <div class="card-title"><span class="dot" style="background: var(--gold-500)"></span>
          下一步：把分析结果落到一日三餐</div>
        <p class="muted" style="margin: 6px 0 var(--sp-3)">
          根据本次分析出的健康目标，为你生成专属食补食谱与药食同源茶饮；
          茶饮生成前会按你的档案（过敏、用药、孕期等）做安全检查
        </p>
        <button class="btn btn-gold btn-block" @click="$router.push('/plan?gen=all')">
          一键生成 专属食补食谱 + 药食同源茶饮 ›
        </button>
        <div class="row" style="margin-top: var(--sp-2)">
          <button class="btn btn-ghost btn-sm grow" @click="$router.push('/plan?gen=diet')">
            只生成食补</button>
          <button class="btn btn-ghost btn-sm grow" @click="$router.push('/plan?gen=tea')">
            只生成茶饮</button>
        </div>
      </section>

      <!-- 相对稳定项折叠（信息不过载） -->
      <section v-if="stables.length" class="card fade-in">
        <button class="row-between fold" @click="stableOpen = !stableOpen">
          <span class="card-title"><span class="dot" style="background: var(--lv-stable)"></span>
            相对稳定（{{ stables.length }} 组）</span>
          <span class="tiny">{{ stableOpen ? '收起 ▴' : '展开 ▾' }}</span>
        </button>
        <div v-if="stableOpen" class="stack-sm" style="margin-top: var(--sp-2)">
          <router-link v-for="it in stables" :key="it.id" class="stb"
                       :to="`/issue/${it.id}`">
            <b>{{ it.title }}</b>
            <span class="grow tiny">{{ it.summary }}</span>
            <LevelBadge :level="it.level" />
          </router-link>
        </div>
      </section>

      <!-- 结合档案问一问：分析完成后最适合的入口位置 -->
      <section v-if="assessment" class="card fade-in ask-archive-card card-clickable"
               @click="$router.push('/ask')">
        <div class="ask-archive-row">
          <span class="ask-archive-ico">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none"
                 stroke="currentColor" stroke-width="1.7" stroke-linecap="round"
                 stroke-linejoin="round">
              <path d="M21 12a8 8 0 1 0-3.1 6.3L21 20l-.9-3.4A8 8 0 0 0 21 12Z"/>
              <path d="M8 10h8M8 14h5"/>
            </svg>
          </span>
          <div class="ask-archive-text">
            <b class="ask-archive-title">结合档案问一问</b>
            <span class="ask-archive-sub">基于你的报告、指标趋势与分析结果，回答个性化健康问题</span>
          </div>
          <span class="ask-archive-arrow">›</span>
        </div>
      </section>

      <!-- 趋势入口 + 免责 -->
      <button class="btn btn-ghost btn-block" @click="$router.push('/trends')">
        查看健康趋势与本次 VS 上次 ›
      </button>
      <p class="tiny" style="text-align:center">
        风险预测基于多变量统计与临床模型，不替代临床诊断；如指标显著异常请及时就医
      </p>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useSessionStore } from '../store/session'
import EmptyState from '../components/EmptyState.vue'
import LevelBadge from '../components/LevelBadge.vue'
import SourceTag from '../components/SourceTag.vue'

const session = useSessionStore()
const loaded = ref(false)
const running = ref(false)
const assessment = ref(null)
const scope = ref(null)
const scopeOpen = ref(false)
const stableOpen = ref(false)
const ratiosOpen = ref(true)
const selectedHorizon = ref('3y')

const pred = computed(() => assessment.value?.prediction || null)
const currentHorizon = computed(() => {
  if (!pred.value?.horizons) return null
  return pred.value.horizons.find((h) => h.horizon === selectedHorizon.value) || pred.value.horizons[1]
})

const tops = computed(() =>
  (assessment.value?.issues || []).filter((i) => i.rank <= 3))
const stables = computed(() =>
  (assessment.value?.issues || []).filter((i) => i.rank > 3))

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
function keyEvidence(it) {
  const seen = new Set()
  const out = []
  for (const e of it.evidence || []) {
    if (e.code === 'finding' || seen.has(e.code)) continue
    if (!e.grade) continue
    seen.add(e.code)
    out.push(e)
    if (out.length >= 3) break
  }
  // 若无异常指标（如仅影像所见），退回展示前两条
  return out.length ? out : (it.evidence || []).slice(0, 2)
}

async function run(force) {
  running.value = true
  try {
    assessment.value = await api.runAssessment(session.profileId, force)
  } catch (e) {
    alert(e.message)
  } finally {
    running.value = false
  }
}

onMounted(async () => {
  const pid = session.profileId
  const [a, s] = await Promise.allSettled([
    api.latestAssessment(pid), api.analysisScope(pid)])
  if (a.status === 'fulfilled') assessment.value = a.value.assessment
  if (s.status === 'fulfilled') scope.value = s.value
  loaded.value = true
  // 有资料但从未分析过 → 自动跑一次，减少一步操作
  if (!assessment.value && (scope.value?.report_count || 0) > 0) run(false)
})
</script>

<style scoped>
.headc .scope-line { margin-top: var(--sp-2); width: 100%; text-align: left;
  border: none; background: var(--surface-sunk); border-radius: var(--r-sm);
  padding: 8px 12px; font-size: 13px; color: var(--ink-700); cursor: pointer;
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.scope-line .tiny { margin-left: auto; }

/* DRP 预测卡片样式 */
.pred-card {
  border: 1.5px solid var(--gold-400);
  background: linear-gradient(180deg, rgba(254, 252, 245, 0.9) 0%, #ffffff 100%);
  position: relative;
}
.badge {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid;
}
.horizon-tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}
.horizon-tab {
  background: #fff;
  border: 1px solid var(--line-soft);
  border-radius: var(--r-sm);
  padding: 8px 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.horizon-tab:hover {
  border-color: var(--gold-500);
}
.horizon-tab.active {
  background: var(--gold-050);
  border-color: var(--gold-600);
  box-shadow: 0 2px 6px rgba(184, 145, 47, 0.15);
}
.h-label {
  font-size: 12px;
  color: var(--ink-600);
}
.h-prob {
  font-size: 16px;
  font-family: var(--font-mono);
}
.horizon-detail {
  background: #fff;
  border: 1px solid var(--line-soft);
  border-radius: var(--r-sm);
  padding: 12px;
  margin-bottom: 14px;
}
.pred-big-num {
  font-size: 32px;
  font-weight: 800;
  font-family: var(--font-mono);
  line-height: 1;
}
.pred-advice {
  text-align: right;
  font-size: 12.5px;
  color: var(--brand-900);
}
.pred-advice b {
  color: var(--danger);
}
.pred-summary {
  font-size: 13px;
  color: var(--ink-700);
  line-height: 1.5;
}

/* SHAP 归因驱动 */
.driver-section {
  border-top: 1px dashed var(--line-soft);
  padding-top: 12px;
}
.driver-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--ink-800);
  margin-bottom: 8px;
}
.dot-sm {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--gold-600);
}
.driver-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.driver-item {
  background: #fff;
  border: 1px solid var(--line-soft);
  border-radius: var(--r-sm);
  padding: 8px 10px;
}
.dr-tag {
  font-size: 10.5px;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 700;
}
.tag-up {
  background: rgba(239, 68, 68, 0.12);
  color: var(--danger);
}
.tag-down {
  background: rgba(16, 185, 129, 0.12);
  color: var(--ok);
}
.dr-name {
  font-size: 13px;
}
.dr-val {
  color: var(--ink-500);
}
.dr-bar-wrap {
  width: 70px;
  height: 6px;
  background: var(--surface-sunk);
  border-radius: 3px;
  overflow: hidden;
}
.dr-bar {
  height: 100%;
  border-radius: 3px;
}
.dr-reason {
  font-size: 12px;
  color: var(--ink-600);
  margin-top: 4px;
  line-height: 1.4;
}

/* 临床衍生评分卡片 */
.ratios-card {
  border-color: rgba(45, 95, 75, 0.2);
}
.ratios-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ratio-item {
  background: var(--surface-sunk);
  border: 1px solid var(--line-soft);
  border-radius: var(--r-sm);
  padding: 9px 12px;
}
.ratio-name {
  font-size: 13.5px;
  color: var(--ink-900);
}
.ratio-val {
  font-size: 14px;
  color: var(--brand-900);
}
.ratio-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}
.rb-ok {
  background: rgba(16, 185, 129, 0.12);
  color: var(--ok);
}
.rb-warn {
  background: rgba(245, 158, 11, 0.15);
  color: var(--warn);
}
.rb-danger {
  background: rgba(239, 68, 68, 0.15);
  color: var(--danger);
}
.ratio-interp {
  font-size: 12px;
  color: var(--ink-700);
  margin: 4px 0 2px;
  line-height: 1.4;
}
.ratio-ref {
  color: var(--ink-500);
}

.cta { border-color: var(--gold-500); }

.top { border-left: 4px solid; }
.b-priority { border-left-color: var(--lv-priority); }
.b-watch { border-left-color: var(--lv-watch); }
.b-mild { border-left-color: var(--lv-mild); }
.b-stable { border-left-color: var(--lv-stable); }
.rk { width: 24px; height: 24px; border-radius: 8px; background: var(--brand-050);
  color: var(--brand-800); display: flex; align-items: center;
  justify-content: center; font-size: 14px; }
.tt { font-size: 18px; }
.sm { margin: var(--sp-2) 0; font-size: 13.5px; color: var(--ink-700); }
.why { font-size: 12.5px; background: var(--gold-100); color: #6F5518;
  border-radius: var(--r-sm); padding: 7px 11px; line-height: 1.6; }
.why b { color: var(--gold-700); }
.ev { margin-top: var(--sp-3); gap: var(--sp-2); }
.evi { display: inline-flex; align-items: center; gap: 6px;
  background: var(--surface-sunk); border: 1px solid var(--line-soft);
  border-radius: var(--r-sm); padding: 4px 9px; font-size: 12px; }
.more-cta {
  margin-top: var(--sp-3);
  display: flex;
  align-items: center;
  gap: 12px;
  background: linear-gradient(135deg, rgba(45, 95, 75, 0.08) 0%, rgba(184, 145, 47, 0.12) 100%);
  border: 1.5px solid rgba(45, 95, 75, 0.22);
  border-radius: var(--r-md);
  padding: 10px 14px;
  transition: all 0.2s ease;
  color: var(--brand-900);
}
.card-clickable:hover .more-cta {
  background: linear-gradient(135deg, rgba(45, 95, 75, 0.15) 0%, rgba(184, 145, 47, 0.22) 100%);
  border-color: var(--brand-600);
  box-shadow: 0 3px 12px rgba(45, 95, 75, 0.12);
  transform: translateY(-1px);
}
.more-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: var(--brand-700);
  color: #fff;
  border-radius: 9px;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(45, 95, 75, 0.25);
}
.more-content {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  gap: 2px;
  text-align: left;
}
.more-title {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--brand-800);
  letter-spacing: 0.2px;
}
.more-sub {
  font-size: 11px;
  color: var(--ink-500);
  line-height: 1.3;
}
.more-arrow {
  font-size: 20px;
  font-weight: 700;
  color: var(--brand-700);
  line-height: 1;
  transition: transform 0.2s ease;
}
.card-clickable:hover .more-arrow {
  transform: translateX(3px);
  color: var(--gold-600);
}

.fold { width: 100%; border: none; background: none; padding: 0;
  cursor: pointer; font: inherit; text-align: left; }
.stb { display: flex; align-items: center; gap: var(--sp-3);
  padding: var(--sp-2) 0; border-bottom: 1px solid var(--line-soft);
  color: inherit; }
.stb:last-child { border-bottom: none; }
.stb b { font-size: 14px; min-width: 60px; }
.stb .tiny { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 结合档案问一问 入口卡 */
.ask-archive-card {
  border: 1.5px solid var(--gold-300);
  background: linear-gradient(135deg, var(--gold-050, #fefcf5) 0%, #fff 100%);
  cursor: pointer;
  transition: all 0.25s ease;
}
.ask-archive-card:hover {
  border-color: var(--gold-500);
  box-shadow: 0 3px 12px rgba(180, 140, 40, 0.12);
  transform: translateY(-1px);
}
.ask-archive-row {
  display: flex; align-items: center; gap: 12px;
}
.ask-archive-ico {
  display: flex; align-items: center; justify-content: center;
  width: 38px; height: 38px; border-radius: 11px;
  background: var(--gold-100); color: var(--gold-700); flex-shrink: 0;
}
.ask-archive-text {
  display: flex; flex-direction: column; flex-grow: 1; gap: 3px;
}
.ask-archive-title {
  font-size: 14.5px; font-weight: 700; color: var(--gold-800, #6d5a1e);
  font-family: var(--font-serif);
}
.ask-archive-sub {
  font-size: 11.5px; color: var(--ink-500); line-height: 1.4;
}
.ask-archive-arrow {
  font-size: 22px; font-weight: 700; color: var(--gold-600);
  transition: transform 0.2s ease;
}
.ask-archive-card:hover .ask-archive-arrow {
  transform: translateX(3px);
}
</style>

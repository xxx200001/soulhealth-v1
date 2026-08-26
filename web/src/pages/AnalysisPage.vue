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
        <span class="more">查看依据与行动建议 ›</span>
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

      <!-- 趋势入口 + 免责 -->
      <button class="btn btn-ghost btn-block" @click="$router.push('/trends')">
        查看健康趋势与本次 VS 上次 ›
      </button>
      <p class="tiny" style="text-align:center">
        风险以关注等级与依据表达，不提供未经验证的患病概率；如指标显著异常请及时就医
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

const tops = computed(() =>
  (assessment.value?.issues || []).filter((i) => i.rank <= 3))
const stables = computed(() =>
  (assessment.value?.issues || []).filter((i) => i.rank > 3))

function typeCN(t) {
  return { lab_report: '检验报告', ultrasound_report: '超声检查',
           checkup: '体检报告', other: '健康资料' }[t] || '健康资料'
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
.evi em { font-style: normal; color: var(--ink-400); font-size: 11px; }
.more { display: block; margin-top: var(--sp-3); font-size: 12.5px;
  color: var(--brand-700); font-weight: 600; }

.fold { width: 100%; border: none; background: none; padding: 0;
  cursor: pointer; font: inherit; text-align: left; }
.stb { display: flex; align-items: center; gap: var(--sp-3);
  padding: var(--sp-2) 0; border-bottom: 1px solid var(--line-soft);
  color: inherit; }
.stb:last-child { border-bottom: none; }
.stb b { font-size: 14px; min-width: 60px; }
.stb .tiny { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>

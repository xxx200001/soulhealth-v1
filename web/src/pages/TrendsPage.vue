<template>
  <div class="page stack">
    <!-- 综合慢病进展风险时序走势轨迹 (DRP 风险轨迹) -->
    <section v-if="timelineData?.history?.length" class="card fade-in timeline-card">
      <div class="row-between" style="align-items: center">
        <div class="card-title">
          <span class="dot" style="background: var(--gold-500)"></span>
          全周期慢病风险演进轨迹（按真实检查日期）
        </div>
        <span v-if="latestTimelinePoint" class="badge"
              :style="{ background: latestTimelinePoint.tier_color + '22', color: latestTimelinePoint.tier_color, borderColor: latestTimelinePoint.tier_color }">
          当前处于{{ latestTimelinePoint.tier_cn }}区间
        </span>
      </div>
      <p class="tiny muted" style="margin: 4px 0 12px">
        基于历次真实化验单检查时点回溯重跑风险模型，展示病情随时间演变实线与未来 1Y/3Y/5Y 预测虚线
      </p>

      <!-- 时间轴圆点步进链 -->
      <div class="timeline-step-wrap">
        <div class="timeline-steps">
          <div v-for="(p, i) in timelineData.history" :key="p.date" class="t-step-item">
            <div class="t-dot" :style="{ background: p.tier_color }">
              <span class="t-inner-dot"></span>
            </div>
            <span class="t-date">{{ p.date }}</span>
            <b class="t-prob num" :style="{ color: p.tier_color }">{{ p.percentage }}</b>
            <span class="t-tier">{{ p.tier_cn }}</span>
          </div>

          <!-- 未来预测虚线点 -->
          <div v-for="f in (timelineData.future || []).filter(x => x.type === 'projection')" :key="f.date" class="t-step-item projection">
            <div class="t-dot proj" :style="{ borderColor: f.tier_color }">
              <span class="t-inner-dot proj" :style="{ background: f.tier_color }"></span>
            </div>
            <span class="t-date">{{ f.label }}</span>
            <b class="t-prob num proj" :style="{ color: f.tier_color }">{{ f.percentage }}</b>
            <span class="t-tier proj">{{ f.tier_cn }} (预估)</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 指标选择 -->
    <section class="card fade-in">
      <div class="card-title"><span class="dot"></span>单项生化指标趋势</div>
      <p class="muted" style="margin: 6px 0 var(--sp-3)">
        按真实检查日期排列的跨报告变化；点选指标查看
      </p>
      <div v-if="codes.length" class="row wrap">
        <button v-for="c in codes" :key="c.code" class="opt"
                :class="{ on: c.code === current }" @click="pick(c.code)">
          {{ c.name_cn }}
          <small class="cnt">{{ c.n }}次</small>
        </button>
      </div>
      <EmptyState v-else-if="loaded" icon="◍" text="档案中还没有可绘制的指标">
        <button class="btn btn-primary btn-sm" style="margin-top: var(--sp-2)"
                @click="$router.push('/upload')">上传健康资料</button>
      </EmptyState>
    </section>

    <!-- 大图 -->
    <section v-if="series" class="card fade-in">
      <div class="row-between">
        <div>
          <h3 style="font-size:17px">{{ series.name_cn }}</h3>
          <p class="tiny">
            单位 {{ series.unit || '—' }}
            <template v-if="series.ref">
              · 参考范围 {{ series.ref.low ?? '—' }} ~ {{ series.ref.high ?? '—' }}
            </template>
          </p>
        </div>
        <span v-if="latestGrade" class="badge"
              :class="latestGrade > 0 ? 'badge-warn' : 'badge-info'">
          {{ gradeCN(latestGrade) }}
        </span>
      </div>
      <TrendChart :points="chartPoints" :unit="series.unit"
                  :ref-low="series.ref?.low" :ref-high="series.ref?.high" />
      <p v-if="insightLine" class="alert alert-info" style="margin-top: var(--sp-2)">
        {{ insightLine }}
      </p>
    </section>

    <!-- 本次 VS 上次（AC-10：必须带两个具体日期） -->
    <section v-if="cmp" class="card fade-in">
      <div class="card-title"><span class="dot"></span>本次 VS 上次</div>
      <div class="cmp-body">
        <div class="cmp-col">
          <span class="tiny">上次 · {{ cmp.prev_date }}</span>
          <b class="num">{{ cmp.prev_value }}<small>{{ series.unit }}</small></b>
        </div>
        <span class="cmp-arrow" :class="arrowClass">{{ arrow }}</span>
        <div class="cmp-col">
          <span class="tiny">本次 · {{ cmp.curr_date }}</span>
          <b class="num">{{ cmp.curr_value }}<small>{{ series.unit }}</small></b>
        </div>
        <div class="cmp-col right">
          <span class="tiny">变化</span>
          <b class="num" :class="arrowClass">
            {{ cmp.delta_pct > 0 ? '+' : '' }}{{ cmp.delta_pct }}%
          </b>
        </div>
      </div>
      <p class="tiny" style="margin-top: 8px">
        {{ cmp.is_real_change
           ? '此变化超出该指标的正常生理波动范围（RCV），属于真实变化'
           : '此变化在该指标的正常生理波动范围内，视为基本平稳' }}
      </p>
    </section>

    <!-- 数据点列表：每个点可回溯到原始报告（AC-09） -->
    <section v-if="series?.insight?.points?.length" class="card fade-in">
      <div class="card-title"><span class="dot"></span>历史记录</div>
      <div class="table-wrap" style="margin-top: var(--sp-2)">
        <table class="table">
          <thead><tr><th>检查日期</th><th>数值</th><th>判读</th><th>出处</th></tr></thead>
          <tbody>
            <tr v-for="(p, i) in [...series.insight.points].reverse()" :key="i">
              <td class="tiny">{{ p.date }}</td>
              <td class="num">{{ p.value }} {{ p.unit || series.unit }}</td>
              <td>
                <span class="badge" :class="p.grade ? 'badge-warn' : 'badge-ok'">
                  {{ gradeCN(p.grade) }}
                </span>
              </td>
              <td>
                <router-link v-if="p.report_id" :to="`/report/${p.report_id}`"
                             class="tiny">查看原件 ›</router-link>
                <span v-else class="tiny">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useSessionStore } from '../store/session'
import EmptyState from '../components/EmptyState.vue'
import TrendChart from '../components/TrendChart.vue'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()

const loaded = ref(false)
const codes = ref([])
const current = ref('')
const series = ref(null)
const timelineData = ref(null)

const latestTimelinePoint = computed(() => {
  const h = timelineData.value?.history
  return h && h.length ? h[h.length - 1] : null
})

const chartPoints = computed(() => series.value?.insight?.points || [])
const cmp = computed(() => series.value?.insight?.compare || null)
const latestGrade = computed(() => series.value?.insight?.latest?.grade || 0)
const arrow = computed(() => {
  if (!cmp.value) return '→'
  return { 上升: '↑', 下降: '↓' }[cmp.value.direction] || '→'
})
const arrowClass = computed(() => {
  if (!cmp.value?.is_real_change) return 'flat'
  return cmp.value.worsened ? 'bad' : 'good'
})
const insightLine = computed(() => {
  const ins = series.value?.insight
  if (!ins) return ''
  const parts = []
  if (ins.persistent_direction) parts.push(`多次记录呈${ins.persistent_direction}`)
  if (ins.abnormal_streak >= 2) parts.push(`已连续 ${ins.abnormal_streak} 次异常`)
  return parts.join('；')
})

function gradeCN(g) {
  return { '-3': '重度偏低', '-2': '中度偏低', '-1': '轻度偏低', 0: '正常',
           1: '轻度偏高', 2: '中度偏高', 3: '重度偏高' }[String(g)] || '正常'
}

async function pick(code) {
  current.value = code
  router.replace({ query: { code } })
  series.value = null
  try {
    series.value = await api.metricSeries(session.profileId, code)
  } catch (e) { alert(e.message) }
}

onMounted(async () => {
  try {
    const [r, tl] = await Promise.allSettled([
      api.metricCodes(session.profileId),
      api.riskTimeline(session.profileId),
    ])
    if (r.status === 'fulfilled') {
      codes.value = (r.value.items || []).filter((c) => c.code)
    }
    if (tl.status === 'fulfilled') {
      timelineData.value = tl.value
    }
  } finally { loaded.value = true }
  const pre = route.query.code
  const first = codes.value.find((c) => c.code === pre) || codes.value[0]
  if (first) pick(first.code)
})
</script>

<style scoped>
.timeline-card {
  border: 1.5px solid var(--gold-300);
  background: linear-gradient(180deg, rgba(254, 252, 245, 0.7) 0%, #fff 100%);
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
.timeline-step-wrap {
  overflow-x: auto;
  padding: 10px 4px;
}
.timeline-steps {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  min-width: max-content;
  position: relative;
}
.t-step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  position: relative;
  min-width: 80px;
}
.t-step-item:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 8px;
  left: 50%;
  width: 100%;
  height: 2px;
  background: rgba(184, 145, 47, 0.25);
  z-index: 1;
}
.t-step-item.projection:not(:last-child)::after {
  border-top: 2px dashed var(--gold-400);
  background: transparent;
}
.t-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 5px rgba(0,0,0,0.15);
  position: relative;
  z-index: 2;
}
.t-dot.proj {
  background: #fff;
  border: 2px dashed;
}
.t-inner-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #fff;
}
.t-inner-dot.proj {
  width: 4px;
  height: 4px;
}
.t-date {
  font-size: 11px;
  color: var(--ink-500);
  margin-top: 4px;
}
.t-prob {
  font-size: 15px;
}
.t-tier {
  font-size: 11px;
  color: var(--ink-600);
}
.t-tier.proj {
  color: var(--brand-700);
  font-style: italic;
}

.cnt { font-size: 10px; opacity: .65; margin-left: 3px; }
.cmp-body { display: flex; align-items: center; gap: var(--sp-4);
  margin-top: var(--sp-2); }
.cmp-col { display: flex; flex-direction: column; }
.cmp-col.right { margin-left: auto; text-align: right; }
.cmp-col b { font-size: 20px; }
.cmp-col small { font-size: 10px; color: var(--ink-400); margin-left: 2px; }
.cmp-arrow { font-size: 24px; font-weight: 900; color: var(--ink-400); }
.cmp-arrow.bad, .num.bad { color: var(--lv-priority); }
.cmp-arrow.good, .num.good { color: var(--lv-stable); }
.cmp-arrow.flat, .num.flat { color: var(--ink-400); }
</style>

<template>
  <div class="page stack" v-if="issue">
    <!-- 标题区 -->
    <section class="card fade-in head" :class="`b-${issue.level}`">
      <div class="row-between">
        <h2 class="tt">{{ issue.title }}</h2>
        <LevelBadge :level="issue.level" />
      </div>
      <p class="muted" style="margin: 6px 0 0">{{ issue.summary }}</p>
      <p class="tiny" style="margin-top: 4px">
        基于 {{ issue.assessment_created_at?.slice(0, 10) }} 的健康分析
        <template v-if="issue.rank <= 3"> · 当前优先级第 {{ issue.rank }}</template>
      </p>
    </section>

    <!-- ① 发现了什么 -->
    <section class="card fade-in">
      <div class="sec"><i>①</i>发现了什么</div>
      <ul class="ls">
        <li v-for="(x, i) in d.found" :key="i">{{ x }}</li>
      </ul>
    </section>

    <!-- ② 过去怎么变化（含 本次VS上次 双日期卡, AC-10） -->
    <section class="card fade-in">
      <div class="sec"><i>②</i>过去怎么变化</div>
      <ul class="ls">
        <li v-for="(x, i) in d.history" :key="i">{{ x }}</li>
      </ul>
      <div v-if="d.compare?.length" class="cmp-list">
        <div v-for="c in d.compare" :key="c.code" class="cmp">
          <div class="cmp-name">{{ c.name }}</div>
          <div class="cmp-body">
            <div class="cmp-col">
              <span class="tiny">上次 · {{ c.prev_date }}</span>
              <b class="num">{{ c.prev_value }}<small>{{ c.unit }}</small></b>
            </div>
            <span class="cmp-arrow" :class="arrowClass(c)">{{ arrowOf(c) }}</span>
            <div class="cmp-col">
              <span class="tiny">本次 · {{ c.curr_date }}</span>
              <b class="num">{{ c.curr_value }}<small>{{ c.unit }}</small></b>
            </div>
            <div class="cmp-col right">
              <span class="tiny">变化幅度</span>
              <b class="num" :class="arrowClass(c)">
                {{ c.delta_pct > 0 ? '+' : '' }}{{ c.delta_pct }}%
              </b>
            </div>
          </div>
          <p class="tiny cmp-note">
            {{ c.is_real_change
               ? (c.worsened ? '超出该指标的正常波动范围，且方向不利，属于真实变化'
                             : '超出该指标的正常波动范围，属于真实变化')
               : '在该指标的生理波动（RCV）范围内，视为基本平稳' }}
          </p>
        </div>
      </div>
    </section>

    <!-- ③ 为什么优先关注 -->
    <section class="card fade-in why-card">
      <div class="sec"><i>③</i>为什么优先关注</div>
      <ul class="ls">
        <li v-for="(x, i) in d.why_priority" :key="i">{{ x }}</li>
      </ul>
    </section>

    <!-- ④ 意味着什么 -->
    <section class="card fade-in">
      <div class="sec"><i>④</i>这意味着什么</div>
      <p class="para">{{ d.meaning }}</p>
    </section>

    <!-- ⑤ 未来趋势可能 -->
    <section class="card fade-in">
      <div class="sec"><i>⑤</i>未来趋势可能</div>
      <p class="para">{{ d.future }}</p>
    </section>

    <!-- ⑥ 信息缺口 -->
    <section class="card fade-in">
      <div class="sec"><i>⑥</i>信息缺口与建议补充</div>
      <ul class="ls">
        <li v-for="(x, i) in d.gaps" :key="i">{{ x }}</li>
      </ul>
      <button class="btn btn-ghost btn-sm" @click="$router.push('/upload')">
        补充上传历史报告 ›
      </button>
    </section>

    <!-- ⑦ 现在可以做什么 -->
    <section class="card fade-in act">
      <div class="sec"><i>⑦</i>现在可以做什么</div>
      <ol class="ls ol">
        <li v-for="(x, i) in d.actions" :key="i">{{ x }}</li>
      </ol>
      <div v-if="issue.goal_tags?.length" class="row" style="margin-top: var(--sp-3)">
        <button class="btn btn-gold grow" @click="$router.push('/plan')">
          查看为此生成的食补与茶饮方案 ›
        </button>
      </div>
    </section>

    <!-- 证据与出处（AC-09：任一关键数据可回溯原始报告） -->
    <section class="card fade-in">
      <div class="sec"><i>◎</i>证据与出处</div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>指标/所见</th><th>数值</th><th>日期</th><th>来源</th></tr></thead>
          <tbody>
            <tr v-for="(e, i) in issue.evidence" :key="i">
              <td>
                <b>{{ e.name }}</b>
                <div v-if="e.text" class="tiny">{{ e.text }}</div>
              </td>
              <td class="num">
                <template v-if="e.value != null">{{ e.value }} {{ e.unit }}</template>
                <span v-else class="tiny">—</span>
              </td>
              <td class="tiny">{{ e.date }}</td>
              <td>
                <router-link v-if="e.report_id" :to="`/report/${e.report_id}`"
                             class="srclink">
                  <SourceTag :text="e.source" /> ›
                </router-link>
                <SourceTag v-else :text="e.source" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="row wrap" style="margin-top: var(--sp-3)">
        <button v-for="c in d.codes_abnormal" :key="c" class="chip"
                @click="$router.push(`/trends?code=${c}`)">
          {{ c }} 趋势图 ›
        </button>
      </div>
    </section>

    <p class="tiny" style="text-align:center">
      以上为健康管理建议，不构成诊断；如有明显不适请及时就医
    </p>
  </div>

  <div v-else class="page"><div class="empty"><span class="spin"></span></div></div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import LevelBadge from '../components/LevelBadge.vue'
import SourceTag from '../components/SourceTag.vue'

const route = useRoute()
const issue = ref(null)
const d = computed(() => issue.value?.detail || {})

function arrowOf(c) {
  if (c.direction === '上升') return '↑'
  if (c.direction === '下降') return '↓'
  return '→'
}
function arrowClass(c) {
  if (!c.is_real_change) return 'flat'
  return c.worsened ? 'bad' : 'good'
}

onMounted(async () => {
  try {
    issue.value = await api.getIssue(route.params.iid)
  } catch (e) {
    alert(e.message)
  }
})
</script>

<style scoped>
.head { border-left: 4px solid; }
.b-priority { border-left-color: var(--lv-priority); }
.b-watch { border-left-color: var(--lv-watch); }
.b-mild { border-left-color: var(--lv-mild); }
.b-stable { border-left-color: var(--lv-stable); }
.tt { font-size: 20px; }

.sec { display: flex; align-items: center; gap: 8px;
  font-family: var(--font-serif); font-weight: 700; font-size: 15.5px;
  color: var(--brand-800); margin-bottom: var(--sp-2); }
.sec i { font-style: normal; color: var(--gold-600); font-size: 14px; }

.ls { margin: 0; padding-left: 18px; font-size: 14px; color: var(--ink-700); }
.ls li { margin: 5px 0; line-height: 1.7; }
.ls.ol li::marker { color: var(--gold-600); font-weight: 700; }
.para { margin: 0; font-size: 14px; line-height: 1.8; color: var(--ink-700); }

.why-card { background: linear-gradient(180deg, var(--gold-100), var(--surface) 60%); }

.cmp-list { display: flex; flex-direction: column; gap: var(--sp-3);
  margin-top: var(--sp-3); }
.cmp { border: 1px solid var(--line); border-radius: var(--r-md);
  padding: var(--sp-3); background: var(--surface-sunk); }
.cmp-name { font-weight: 700; font-size: 13.5px; margin-bottom: 6px; }
.cmp-body { display: flex; align-items: center; gap: var(--sp-3); }
.cmp-col { display: flex; flex-direction: column; }
.cmp-col.right { margin-left: auto; text-align: right; }
.cmp-col b { font-size: 17px; }
.cmp-col small { font-size: 10px; color: var(--ink-400); margin-left: 2px; }
.cmp-arrow { font-size: 20px; font-weight: 900; color: var(--ink-400); }
.cmp-arrow.bad, .num.bad { color: var(--lv-priority); }
.cmp-arrow.good, .num.good { color: var(--lv-stable); }
.cmp-arrow.flat, .num.flat { color: var(--ink-400); }
.cmp-note { margin: 6px 0 0; }

.act { border-color: var(--gold-500); }
.srclink { display: inline-flex; align-items: center; gap: 3px; font-size: 12px; }
</style>

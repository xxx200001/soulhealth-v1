<template>
  <div class="page stack">

    <!-- ===================== 食补方案（P09） ===================== -->
    <section class="section-header fade-in">
      <div class="section-header-row">
        <span class="section-icon diet-icon">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
               stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8Z"/>
            <line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/>
            <line x1="14" y1="1" x2="14" y2="4"/>
          </svg>
        </span>
        <h2 class="section-title">我的食补</h2>
      </div>
    </section>

    <EmptyState v-if="loaded && !diet" icon="❋" text="还没有食补方案">
      <p class="muted" style="margin: 6px 0 var(--sp-3)">完成健康分析后一键生成</p>
      <button class="btn btn-primary" :disabled="gen" @click="genDiet">
        <span v-if="gen" class="spin"></span>生成我的食补方案
      </button>
    </EmptyState>

    <template v-else-if="diet">
      <!-- 目标说明：为什么是这些目标 -->
      <section class="card fade-in">
        <div class="row-between">
          <div class="card-title"><span class="dot"></span>本方案针对的健康目标</div>
          <button class="btn btn-quiet btn-sm" :disabled="gen" @click="genDiet">
            <span v-if="gen" class="spin"></span>重新生成
          </button>
        </div>
        <div class="stack-sm" style="margin-top: var(--sp-2)">
          <div v-for="g in diet.goals" :key="g.tag" class="goal">
            <span class="badge badge-gold">{{ g.label }}</span>
            <span class="tiny grow">{{ g.why }}</span>
          </div>
        </div>
        <p class="tiny" style="margin-top: var(--sp-2)">
          基于 {{ diet.created_at?.slice(0, 10) }} 的健康分析 · 第 {{ diet.version }} 版
        </p>
      </section>

      <!-- 四类食物池（AC-12） -->
      <section v-for="pk in poolKeys" :key="pk.key" class="card fade-in"
               v-show="diet.pools[pk.key]?.length">
        <div class="pool-head" :class="pk.cls"><span class="bar"></span>{{ pk.label }}
          <span class="tiny" style="font-weight:400">（{{ diet.pools[pk.key].length }}）</span>
        </div>
        <div class="stack-sm" style="margin-top: var(--sp-2)">
          <div v-for="(f, i) in diet.pools[pk.key]" :key="i" class="food">
            <div class="row-between">
              <b class="fname">{{ f.name }}</b>
              <span class="badge badge-quiet">{{ f.goal }}</span>
            </div>
            <p class="fwhy">{{ f.why }}</p>
            <p v-if="f.portion || f.frequency" class="tiny">
              <template v-if="f.portion">份量：{{ f.portion }}</template>
              <template v-if="f.portion && f.frequency">　·　</template>
              <template v-if="f.frequency">频率：{{ f.frequency }}</template>
            </p>
          </div>
        </div>
      </section>

      <!-- 菜谱（P10 入口） -->
      <section v-if="diet.recipes?.length" class="card fade-in">
        <div class="card-title"><span class="dot"></span>推荐菜谱</div>
        <div class="stack-sm" style="margin-top: var(--sp-2)">
          <button v-for="rc in diet.recipes" :key="rc.id"
                  class="rc card-clickable" @click="$router.push(`/recipe/${rc.id}`)">
            <span class="grow">
              <b>{{ rc.name }}</b>
              <span class="tiny" style="display:block">{{ rc.reason }}</span>
            </span>
            <span class="badge badge-gold">{{ goalLabel(rc.goal_tag) }}</span>
            <span class="arr">›</span>
          </button>
        </div>
      </section>

      <!-- 历史版本（AC-18 可追溯） -->
      <HistoryFold :items="dietHist" label="食补方案"
                   @open="(id) => openDiet(id)" />
    </template>

    <!-- ===================== 分割线 ===================== -->
    <div class="section-divider"></div>

    <!-- ===================== 茶饮方案（P11） ===================== -->
    <section class="section-header fade-in">
      <div class="section-header-row">
        <span class="section-icon tea-icon">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
               stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 9h13v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V9Z"/>
            <path d="M17 10h1.5a2.5 2.5 0 0 1 0 5H17"/>
            <path d="M8 5c0-1 .8-1 .8-2M12 5c0-1 .8-1 .8-2"/>
          </svg>
        </span>
        <h2 class="section-title">药食同源茶饮</h2>
      </div>
    </section>

    <EmptyState v-if="loaded && !tea" icon="◵" text="还没有茶饮方案">
      <p class="muted" style="margin: 6px 0 var(--sp-3)">
        生成前将按你的档案执行安全检查（人群 / 过敏 / 用药）
      </p>
      <button class="btn btn-primary" :disabled="gen" @click="genTea">
        <span v-if="gen" class="spin"></span>生成茶饮方案
      </button>
    </EmptyState>

    <template v-else-if="tea">
      <SafetyNotice :status="tea.safety_status" class="fade-in" />

      <!-- allow：完整方案 -->
      <template v-if="tea.safety_status === 'allow'">
        <section class="card fade-in teacard">
          <div class="row-between">
            <div>
              <h3 class="teaname">{{ p.name }}</h3>
              <p class="tiny">{{ p.goal_label }} · 第 {{ tea.version }} 版</p>
            </div>
            <button class="btn btn-quiet btn-sm" :disabled="gen" @click="genTea">
              <span v-if="gen" class="spin"></span>重新生成
            </button>
          </div>

          <div class="table-wrap" style="margin: var(--sp-3) 0">
            <table class="table">
              <thead><tr><th>原料</th><th>用量</th><th>注意</th></tr></thead>
              <tbody>
                <tr v-for="ing in p.ingredients" :key="ing.name">
                  <td><b>{{ ing.name }}</b><span v-if="ing.note" class="tiny">
                    （{{ ing.note }}）</span></td>
                  <td class="num">{{ ing.grams }} g</td>
                  <td class="tiny">{{ ing.caution || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="grid-2 brew">
            <div class="bx"><span class="bt">水量</span><b>{{ p.water_ml }} ml</b></div>
            <div class="bx"><span class="bt">频率</span><b>{{ p.frequency }}</b></div>
            <div class="bx wide"><span class="bt">制作</span><b>{{ p.brew }}</b></div>
            <div class="bx wide"><span class="bt">周期</span><b>{{ p.cycle }}</b></div>
          </div>

          <div class="blockq">
            <b>配伍依据</b>
            <p>{{ p.rationale }}</p>
          </div>

          <div class="contra">
            <b>禁忌与注意</b>
            <ul>
              <li v-for="(c, i) in p.contraindications" :key="i">{{ c }}</li>
              <li v-for="(c, i) in p.cautions || []" :key="'c' + i" class="hl">{{ c }}</li>
            </ul>
          </div>
          <p class="tiny">{{ p.note }}</p>
        </section>
      </template>

      <!-- require_info：缺失清单 + 去补充（AC-13） -->
      <section v-else-if="tea.safety_status === 'require_info'" class="card fade-in">
        <h3 style="font-size:16px">{{ p.message }}</h3>
        <div class="stack-sm" style="margin: var(--sp-3) 0">
          <div v-for="m in p.missing" :key="m.field" class="miss">
            <b>{{ m.label }}</b>
            <span class="tiny grow">{{ m.why }}</span>
          </div>
        </div>
        <button class="btn btn-primary btn-block"
                @click="$router.push('/me/profile?back=/plan')">
          去补充这些信息 ›
        </button>
        <p class="tiny" style="margin-top: var(--sp-2); text-align:center">
          补充保存后回到本页，点击下方按钮重新生成
        </p>
        <button class="btn btn-ghost btn-block btn-sm" :disabled="gen"
                style="margin-top: var(--sp-2)" @click="genTea">
          <span v-if="gen" class="spin"></span>我已补充，重新检查并生成
        </button>
      </section>

      <!-- block / professional_review：不输出配方（AC-14） -->
      <section v-else class="card fade-in">
        <h3 style="font-size:16px">{{ p.message }}</h3>
        <ul class="ls" style="margin-top: var(--sp-2)">
          <li v-for="(r, i) in p.reasons" :key="i">{{ r }}</li>
        </ul>
        <p class="tiny" style="margin-top: var(--sp-2)">
          这是为了你的安全而设计的前置拦截；档案信息变化后可重新检查
        </p>
        <button class="btn btn-ghost btn-sm" :disabled="gen" @click="genTea">
          <span v-if="gen" class="spin"></span>档案已更新，重新检查
        </button>
      </section>

      <HistoryFold :items="teaHist" label="茶饮方案"
                   @open="(id) => openTea(id)" />
    </template>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useSessionStore } from '../store/session'
import EmptyState from '../components/EmptyState.vue'
import SafetyNotice from '../components/SafetyNotice.vue'

// 轻量历史折叠子组件（AC-18：旧版本可追溯）
const HistoryFold = defineComponent({
  props: { items: Array, label: String },
  emits: ['open'],
  setup(props, { emit }) {
    const open = ref(false)
    return () => {
      const olds = (props.items || []).filter((x) => x.status !== 'active')
      if (!olds.length) return null
      return h('section', { class: 'card fade-in' }, [
        h('button', {
          class: 'row-between fold-btn',
          onClick: () => (open.value = !open.value),
        }, [
          h('span', { class: 'muted' }, `历史${props.label}（${olds.length} 版）`),
          h('span', { class: 'tiny' }, open.value ? '收起 ▴' : '展开 ▾'),
        ]),
        open.value && h('div', { class: 'stack-sm', style: 'margin-top:8px' },
          olds.map((x) => h('button', {
            class: 'hist-row', key: x.id, onClick: () => emit('open', x.id),
          }, [
            h('span', {}, `第 ${x.version} 版`),
            h('span', { class: 'tiny grow' }, x.created_at?.slice(0, 16).replace('T', ' ')),
            h('span', { class: 'tiny' }, '查看 ›'),
          ]))),
      ])
    }
  },
})

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const tab = ref('diet')
const loaded = ref(false)
const gen = ref(false)
const diet = ref(null)
const tea = ref(null)
const dietHist = ref([])
const teaHist = ref([])
const teaHint = ref(false)

const p = computed(() => tea.value?.plan || {})
const poolKeys = [
  { key: 'recommended', label: '推荐吃', cls: 'pool-rec' },
  { key: 'allowed', label: '可以吃', cls: 'pool-ok' },
  { key: 'limit', label: '少吃', cls: 'pool-limit' },
  { key: 'avoid', label: '建议避免', cls: 'pool-avoid' },
]
const GOAL_CN = { liver_care: '肝脏管理', lipid_care: '血脂管理',
  glucose_care: '血糖管理', uric_care: '尿酸管理', weight_care: '体重管理',
  bp_care: '血压管理', kidney_care: '肾功能关注', blood_care: '气血养护',
  general_balance: '均衡养护' }
const goalLabel = (t) => GOAL_CN[t] || t

async function refresh() {
  const pid = session.profileId
  const [d, t, dh, th] = await Promise.allSettled([
    api.dietActive(pid), api.teaActive(pid),
    api.dietHistory(pid), api.teaHistory(pid)])
  if (d.status === 'fulfilled') diet.value = d.value.plan
  if (t.status === 'fulfilled') tea.value = t.value.plan
  if (dh.status === 'fulfilled') dietHist.value = dh.value.items
  if (th.status === 'fulfilled') teaHist.value = th.value.items
  loaded.value = true
}

async function genDiet() {
  gen.value = true
  try { diet.value = await api.dietGenerate(session.profileId); await refresh() }
  catch (e) { alert(e.message) } finally { gen.value = false }
}
async function genTea() {
  gen.value = true
  try { tea.value = await api.teaGenerate(session.profileId); await refresh() }
  catch (e) { alert(e.message) } finally { gen.value = false }
}
async function openDiet(id) {
  try { diet.value = await api.dietGet(id) }
  catch (e) { alert(e.message) }
}
async function openTea(id) {
  try { tea.value = await api.teaGet(id) }
  catch (e) { alert(e.message) }
}

onMounted(async () => {
  await refresh()
  // 从分析页「一键生成」进入：gen=diet / tea / all（AC 反馈修复）
  const g = route.query.gen
  if (!g) return
  router.replace({ path: '/plan' })   // 清掉参数，避免刷新时重复生成
  if (g === 'tea') {
    await genTea()
    return
  }
  if (g === 'diet') {
    await genDiet()
    return
  }
  if (g === 'all') {
    await Promise.allSettled([genDiet(), genTea()])
  }
})
</script>

<style scoped>
/* 方案板块大标题与分割 */
.section-header {
  margin: var(--sp-2) 0 var(--sp-1);
}
.section-header-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.section-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.diet-icon {
  background: var(--brand-050, #E8F4EC);
  color: var(--brand-700, #2D5F4B);
}
.tea-icon {
  background: var(--gold-100, #FDF5E6);
  color: var(--gold-700, #9C6500);
}
.section-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  font-family: var(--font-serif);
  color: var(--brand-900, #1E3A2F);
  letter-spacing: 0.3px;
}
.section-divider {
  margin: var(--sp-4) 0 var(--sp-2);
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--line) 20%, var(--line) 80%, transparent 100%);
}

.goal { display: flex; align-items: flex-start; gap: var(--sp-2); }
.food { border-bottom: 1px dashed var(--line-soft); padding-bottom: var(--sp-2); }
.food:last-child { border-bottom: none; padding-bottom: 0; }
.fname { font-size: 14.5px; }
.fwhy { margin: 3px 0 2px; font-size: 13px; color: var(--ink-500); line-height: 1.6; }

.rc { display: flex; align-items: center; gap: var(--sp-3); width: 100%;
  text-align: left; border: 1px solid var(--line); border-radius: var(--r-sm);
  background: var(--surface-sunk); padding: var(--sp-3); font: inherit; }
.rc .arr { color: var(--ink-300); font-size: 20px; }

.teacard { border-color: var(--gold-500); }
.teaname { font-size: 19px; color: var(--brand-900); }
.brew { gap: var(--sp-2); }
.bx { background: var(--surface-sunk); border-radius: var(--r-sm);
  padding: 8px 12px; display: flex; flex-direction: column; gap: 2px; }
.bx.wide { grid-column: span 2; }
.bt { font-size: 11px; color: var(--ink-400); }
.bx b { font-size: 13.5px; font-weight: 600; line-height: 1.55; }

.blockq { margin-top: var(--sp-3); background: var(--gold-100);
  border-left: 3px solid var(--gold-500);
  border-radius: 0 var(--r-sm) var(--r-sm) 0; padding: 10px 13px; }
.blockq b { font-size: 13px; color: var(--gold-700); }
.blockq p { margin: 4px 0 0; font-size: 13px; color: #6F5518; line-height: 1.7; }

.contra { margin-top: var(--sp-3); }
.contra b { font-size: 13px; color: var(--danger); }
.contra ul { margin: 6px 0 0; padding-left: 18px; font-size: 13px;
  color: var(--ink-700); }
.contra li { margin: 3px 0; }
.contra li.hl { color: var(--warn); font-weight: 600; }

.miss { display: flex; align-items: baseline; gap: var(--sp-2);
  background: var(--info-bg); border-radius: var(--r-sm); padding: 9px 12px; }
.miss b { color: var(--info); font-size: 13.5px; white-space: nowrap; }

.ls { margin: 0; padding-left: 18px; font-size: 14px; color: var(--ink-700); }
.ls li { margin: 4px 0; }

:deep(.fold-btn) { width: 100%; border: none; background: none; padding: 0;
  cursor: pointer; font: inherit; }
:deep(.hist-row) { display: flex; align-items: center; gap: var(--sp-3);
  width: 100%; border: none; background: var(--surface-sunk);
  border-radius: var(--r-sm); padding: 9px 12px; font: inherit;
  cursor: pointer; text-align: left; }
</style>

<template>
  <div class="page stack" v-if="form">
    <p class="alert alert-info fade-in" v-if="fromPlan">
      为了茶饮方案的安全检查，请重点确认：出生年月、过敏史、当前用药
      <template v-if="form.sex === 'female'">、是否怀孕</template>。
      没有也请保存"无"——这与"未记录"不同
    </p>

    <!-- 基本信息 -->
    <section class="card fade-in stack">
      <div class="card-title"><span class="dot"></span>基本信息</div>
      <div class="field">
        <label class="label">姓名 / 昵称</label>
        <input v-model.trim="form.name" class="input" />
      </div>
      <div class="grid-2">
        <div class="field">
          <label class="label">性别</label>
          <select v-model="form.sex" class="select">
            <option value="">未选择</option>
            <option value="male">男</option>
            <option value="female">女</option>
          </select>
        </div>
        <div class="field">
          <label class="label">出生日期
            <em v-if="ft.birth_date" class="upd">{{ updAt('birth_date') }}</em></label>
          <input v-model="form.birth_date" type="date" class="input" />
        </div>
      </div>
      <div class="grid-2">
        <div class="field">
          <label class="label">身高 cm</label>
          <input v-model.number="form.height_cm" type="number" class="input" />
        </div>
        <div class="field">
          <label class="label">体重 kg</label>
          <input v-model.number="form.weight_kg" type="number" step="0.1" class="input" />
        </div>
      </div>
      <div v-if="form.sex === 'female'" class="field">
        <label class="label">当前是否怀孕
          <em v-if="ft.pregnant" class="upd">{{ updAt('pregnant') }}</em></label>
        <div class="opt-grid">
          <button class="opt" :class="{ on: form.pregnant === false }"
                  @click="form.pregnant = false">否</button>
          <button class="opt" :class="{ on: form.pregnant === true }"
                  @click="form.pregnant = true">是</button>
        </div>
      </div>
    </section>

    <!-- 安全关键信息 -->
    <section class="card fade-in stack safetyc">
      <div class="card-title"><span class="dot" style="background: var(--info)"></span>
        安全关键信息</div>
      <TagField v-model="form.allergies" label="过敏史"
                :updated="updAt('allergies')" placeholder="如：花粉、青霉素（回车添加）"
                empty-hint="确认无过敏也请直接保存" />
      <TagField v-model="form.medications" label="当前用药"
                :updated="updAt('medications')" placeholder="如：厄贝沙坦（回车添加）"
                empty-hint="确认未用药也请直接保存" />
      <TagField v-model="form.conditions" label="既往疾病"
                :updated="updAt('conditions')" placeholder="如：高血压（回车添加）" />
      <TagField v-model="form.surgeries" label="手术史"
                :updated="updAt('surgeries')" placeholder="回车添加" />
    </section>

    <!-- 生活方式 -->
    <section class="card fade-in stack">
      <div class="card-title"><span class="dot"></span>生活方式</div>
      <div class="grid-2">
        <div class="field">
          <label class="label">吸烟</label>
          <select v-model="form.smoking" class="select">
            <option value="">未记录</option>
            <option value="none">不吸烟</option>
            <option value="occasional">偶尔</option>
            <option value="regular">经常</option>
            <option value="quit">已戒</option>
          </select>
        </div>
        <div class="field">
          <label class="label">饮酒</label>
          <select v-model="form.alcohol" class="select">
            <option value="">未记录</option>
            <option value="none">不饮酒</option>
            <option value="occasional">偶尔</option>
            <option value="regular">经常</option>
            <option value="quit">已戒</option>
          </select>
        </div>
      </div>
      <TagField v-model="form.diet_pref" label="饮食偏好 / 禁忌"
                placeholder="如：素食、不吃辣（回车添加）" />
    </section>

    <p v-if="error" class="alert alert-danger fade-in">{{ error }}</p>
    <button class="btn btn-primary btn-block btn-lg fade-in" :disabled="saving"
            @click="save">
      <span v-if="saving" class="spin"></span>保存
    </button>
    <p class="tiny" style="text-align:center">
      所有字段都是渐进补充：现在留空不影响使用，需要时系统会提示
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useSessionStore } from '../store/session'
import TagField from '../components/TagField.vue'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const form = ref(null)
const ft = ref({})
const saving = ref(false)
const error = ref('')
const fromPlan = computed(() => route.query.back === '/plan')

function updAt(field) {
  const t = ft.value?.[field]
  return t ? `已记录 ${t.slice(5, 10)}` : ''
}

onMounted(async () => {
  const p = session.profile || await session.refresh()
  if (!p) { router.replace('/onboard'); return }
  ft.value = p.field_times || {}
  form.value = {
    name: p.name, sex: p.sex || '', birth_date: p.birth_date || '',
    height_cm: p.height_cm, weight_kg: p.weight_kg,
    pregnant: 'pregnant' in ft.value ? !!p.pregnant : null,
    allergies: p.allergies ?? null, medications: p.medications ?? null,
    conditions: p.conditions ?? null, surgeries: p.surgeries ?? null,
    smoking: p.smoking || '', alcohol: p.alcohol || '',
    diet_pref: p.diet_pref ?? null,
  }
  // 数组字段：从未记录时初始化为空数组以便编辑；保存时空数组=明确"无"
  for (const k of ['allergies', 'medications', 'conditions', 'surgeries', 'diet_pref']) {
    if (!Array.isArray(form.value[k])) form.value[k] = []
  }
})

async function save() {
  saving.value = true
  error.value = ''
  try {
    const f = form.value
    const payload = {
      name: f.name, sex: f.sex || null, birth_date: f.birth_date || null,
      height_cm: f.height_cm ?? null, weight_kg: f.weight_kg ?? null,
      // 空数组也提交：写入 field_times，满足茶饮安全检查"已确认无"的语义
      allergies: f.allergies, medications: f.medications,
      conditions: f.conditions, surgeries: f.surgeries,
      smoking: f.smoking || null, alcohol: f.alcohol || null,
      diet_pref: f.diet_pref,
    }
    if (f.pregnant !== null) payload.pregnant = f.pregnant
    await api.updateProfile(session.profileId, payload)
    await session.refresh()
    router.push(route.query.back || '/me')
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.safetyc { border-color: #CCDCEE; }
.upd { font-style: normal; font-weight: 400; font-size: 11px;
  color: var(--ok); margin-left: 6px; }
</style>

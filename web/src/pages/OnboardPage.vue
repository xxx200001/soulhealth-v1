<template>
  <div class="onb">
    <!-- P01 首次进入：三入口，不强制长问卷 -->
    <template v-if="step === 1">
      <div class="head fade-in">
        <div class="mark">和</div>
        <h1>今天想做什么？</h1>
        <p class="muted">选择一个开始，健康档案会在下一步一起建立</p>
      </div>
      <div class="stack stagger">
        <button v-for="e in entries" :key="e.key" class="card entry card-clickable"
                @click="choose(e.key)">
          <span class="ico" v-html="e.icon"></span>
          <span class="grow">
            <b class="et">{{ e.title }}</b>
            <span class="muted ed">{{ e.desc }}</span>
          </span>
          <span class="arrow">›</span>
        </button>
      </div>
    </template>

    <!-- P02 最小建档：仅三要素 -->
    <template v-else>
      <div class="head fade-in">
        <h1>先认识一下</h1>
        <p class="muted">只需要三项，其余信息在需要时再补充</p>
      </div>
      <div class="card stack fade-in">
        <div class="field">
          <label class="label">姓名 / 昵称</label>
          <input v-model.trim="name" class="input" placeholder="怎么称呼你" />
        </div>
        <div class="field">
          <label class="label">性别</label>
          <div class="opt-grid">
            <button class="opt" :class="{ on: sex === 'male' }" @click="sex = 'male'">男</button>
            <button class="opt" :class="{ on: sex === 'female' }" @click="sex = 'female'">女</button>
          </div>
        </div>
        <div class="field">
          <label class="label">出生年月</label>
          <input v-model="birth" type="month" class="input" />
        </div>
        <p v-if="error" class="alert alert-danger">{{ error }}</p>
        <button class="btn btn-primary btn-block btn-lg" :disabled="busy" @click="create">
          <span v-if="busy" class="spin"></span>建立我的健康档案
        </button>
        <button class="btn btn-quiet btn-block btn-sm" @click="step = 1">‹ 返回上一步</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useSessionStore } from '../store/session'

const router = useRouter()
const session = useSessionStore()
const step = ref(1)
const intent = ref('archive')
const name = ref('')
const sex = ref('')
const birth = ref('')
const error = ref('')
const busy = ref(false)

const sw = 'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"'
const entries = [
  { key: 'upload', title: '我有健康报告', desc: '上传体检报告、化验单、检查资料',
    icon: `<svg viewBox="0 0 24 24" width="26" height="26" ${sw}><path d="M12 16V4M7.5 8.5 12 4l4.5 4.5"/><path d="M4 15v4a1.5 1.5 0 0 0 1.5 1.5h13A1.5 1.5 0 0 0 20 19v-4"/></svg>` },
  { key: 'ask', title: '我有健康问题想问', desc: '没有报告也可以，从当前问题开始',
    icon: `<svg viewBox="0 0 24 24" width="26" height="26" ${sw}><path d="M21 12a8 8 0 1 0-3.1 6.3L21 20l-.9-3.4A8 8 0 0 0 21 12Z"/><path d="M9.6 9.6a2.4 2.4 0 0 1 4.7.6c0 1.6-2.3 2-2.3 3.2M12 16.4v.02"/></svg>` },
  { key: 'archive', title: '我想建立健康档案', desc: '逐步整理既往健康资料',
    icon: `<svg viewBox="0 0 24 24" width="26" height="26" ${sw}><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>` },
]

function choose(k) { intent.value = k; step.value = 2 }

async function create() {
  if (!name.value) { error.value = '请填写姓名或昵称'; return }
  busy.value = true
  error.value = ''
  try {
    const p = await api.createProfile({
      name: name.value, sex: sex.value || null,
      birth_date: birth.value ? `${birth.value}-01` : null,
    })
    await session.select(p.id)
    router.replace({ upload: '/upload', ask: '/ask', archive: '/archive' }[intent.value])
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.onb { min-height: 100%; max-width: 460px; margin: 0 auto;
  padding: var(--sp-10) var(--sp-4); display: flex; flex-direction: column;
  justify-content: center; gap: var(--sp-5); }
.head { text-align: center; }
.head h1 { font-size: 22px; color: var(--brand-900); }
.head .muted { margin-top: 6px; }
.mark { width: 46px; height: 46px; margin: 0 auto var(--sp-3); border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-serif); font-size: 22px; font-weight: 900; color: #fff;
  background: linear-gradient(135deg, var(--brand-800), var(--brand-500)); }
.entry { display: flex; align-items: center; gap: var(--sp-4); text-align: left;
  width: 100%; border: 1px solid var(--line); font: inherit; }
.entry:hover { border-color: var(--brand-500); }
.ico { color: var(--brand-700); display: flex; }
.et { display: block; font-family: var(--font-serif); font-size: 16px; }
.ed { display: block; font-size: 12.5px; margin-top: 2px; }
.arrow { color: var(--ink-300); font-size: 22px; }
</style>

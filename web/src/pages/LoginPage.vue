<template>
  <div class="login">
    <div class="brand fade-in">
      <div class="mark">和</div>
      <h1>SOULHEALTH</h1>
      <p class="slogan">长期健康档案 · 看懂变化 · 食养有方</p>
    </div>

    <div class="card panel fade-in">
      <div class="seg">
        <button :class="{ on: mode === 'login' }" @click="mode = 'login'">登录</button>
        <button :class="{ on: mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <div class="stack" style="margin-top: var(--sp-4)">
        <div class="field">
          <label class="label">用户名</label>
          <input v-model.trim="username" class="input" autocomplete="username"
                 placeholder="demo" @keyup.enter="submit" />
        </div>
        <div class="field">
          <label class="label">密码</label>
          <input v-model="password" type="password" class="input"
                 autocomplete="current-password" placeholder="至少 6 位"
                 @keyup.enter="submit" />
        </div>
        <div v-if="mode === 'register'" class="field">
          <label class="label">昵称（可选）</label>
          <input v-model.trim="displayName" class="input" placeholder="怎么称呼你" />
        </div>

        <p v-if="error" class="alert alert-danger">{{ error }}</p>

        <button class="btn btn-primary btn-block btn-lg" :disabled="busy" @click="submit">
          <span v-if="busy" class="spin"></span>
          {{ mode === 'login' ? '进入我的健康' : '创建账号' }}
        </button>
        <p class="tiny" style="text-align:center">
          演示账号 demo / demo123456 · 内置三年历史体检数据
        </p>
      </div>
    </div>

    <p class="tiny foot">健康管理信息服务 · 不构成医疗诊断或处方</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'
import { useSessionStore } from '../store/session'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const session = useSessionStore()

const mode = ref('login')
const username = ref('')
const password = ref('')
const displayName = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  if (!username.value || password.value.length < 6) {
    error.value = '请输入用户名和至少 6 位密码'
    return
  }
  busy.value = true
  error.value = ''
  try {
    if (mode.value === 'login') await auth.login(username.value, password.value)
    else await auth.register(username.value, password.value, displayName.value)
    await session.ensureProfile()
    router.replace(session.hasProfile ? (route.query.r || '/') : '/onboard')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.login { min-height: 100%; display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: var(--sp-6) var(--sp-4); gap: var(--sp-6);
  background:
    radial-gradient(600px 300px at 85% -60px, var(--brand-100), transparent 70%),
    radial-gradient(500px 260px at -60px 100%, var(--gold-100), transparent 70%),
    var(--bg); }
.brand { text-align: center; }
.mark { width: 58px; height: 58px; margin: 0 auto var(--sp-3); border-radius: 17px;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-serif); font-size: 28px; font-weight: 900; color: #fff;
  background: linear-gradient(135deg, var(--brand-800), var(--brand-500));
  box-shadow: var(--shadow-md); }
.brand h1 { font-size: 24px; letter-spacing: 3px; color: var(--brand-900); }
.slogan { margin: 6px 0 0; font-size: 13px; color: var(--ink-500); letter-spacing: 1px; }
.panel { width: 100%; max-width: 380px; padding: var(--sp-5); }
.foot { text-align: center; }
</style>

<template>
  <div class="page stack">
    <!-- 账号卡 -->
    <section class="card fade-in row">
      <div class="avatar">{{ initials }}</div>
      <div class="grow">
        <b style="font-size:16px; font-family: var(--font-serif)">{{ auth.displayName }}</b>
        <p class="tiny">@{{ auth.user?.username }}</p>
      </div>
    </section>

    <!-- 档案切换 -->
    <section class="card fade-in">
      <div class="card-title"><span class="dot"></span>健康档案</div>
      <div class="stack-sm" style="margin-top: var(--sp-2)">
        <button v-for="p in profiles" :key="p.id" class="prow"
                :class="{ on: p.id === session.profileId }" @click="pick(p)">
          <b>{{ p.name }}</b>
          <span class="tiny grow">
            {{ { female: '女', male: '男' }[p.sex] || '' }}
            <template v-if="p.age_years != null"> · {{ p.age_years }} 岁</template>
          </span>
          <span v-if="p.id === session.profileId" class="badge badge-ok">当前</span>
        </button>
      </div>
      <div class="row" style="margin-top: var(--sp-3)">
        <button class="btn btn-ghost btn-sm grow" @click="$router.push('/me/profile')">
          编辑当前档案资料
        </button>
        <button class="btn btn-quiet btn-sm" @click="$router.push('/onboard')">
          ＋新建档案
        </button>
      </div>
    </section>

    <!-- 系统状态 -->
    <section class="card fade-in" v-if="session.health">
      <div class="card-title"><span class="dot"></span>系统能力</div>
      <div class="row wrap" style="margin-top: var(--sp-2)">
        <span class="badge" :class="session.health.llm_mode === 'real' ? 'badge-ok' : 'badge-quiet'">
          智能识别：{{ modeCN(session.health.llm_mode) }}
        </span>
        <span class="badge badge-ok">标准化指标 {{ session.health.indicators }} 项</span>
        <span class="badge badge-ok">规则安全引擎已启用</span>
      </div>
      <p v-if="session.health.llm_mode !== 'real'" class="tiny" style="margin-top: 8px">
        当前为{{ modeCN(session.health.llm_mode) }}模式。配置 ANTHROPIC_API_KEY 后，
        可识别真实报告照片、问询回答也会更自然
      </p>
    </section>

    <!-- 免责声明 -->
    <section class="card-flat fade-in">
      <b style="font-size:13px">服务边界</b>
      <p class="tiny" style="margin-top: 4px">{{ disclaimer }}</p>
    </section>

    <button class="btn btn-danger btn-block fade-in" @click="logout">退出登录</button>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useAuthStore } from '../store/auth'
import { useSessionStore } from '../store/session'

const router = useRouter()
const auth = useAuthStore()
const session = useSessionStore()
const profiles = ref([])

const initials = computed(() => (auth.displayName || 'S')[0])
const disclaimer = computed(() =>
  session.health?.disclaimer ||
  '本服务提供健康管理信息与生活方式建议，不构成医疗诊断、治疗方案或处方；如有不适请及时就医。')

function modeCN(m) {
  return { real: '已连接模型', mock: '离线演示', unconfigured: '未配置' }[m] || m
}

async function pick(p) {
  if (p.id === session.profileId) return
  await session.select(p.id)
  router.push('/')
}

function logout() {
  auth.logout()
  router.replace('/login')
}

onMounted(async () => {
  try { profiles.value = (await api.listProfiles()).items } catch { /* 忽略 */ }
  session.loadHealth()
})
</script>

<style scoped>
.avatar { width: 52px; height: 52px; border-radius: 16px;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-serif); font-size: 24px; font-weight: 900; color: #fff;
  background: linear-gradient(135deg, var(--brand-800), var(--brand-500)); }
.prow { display: flex; align-items: center; gap: var(--sp-2); width: 100%;
  text-align: left; border: 1px solid var(--line); border-radius: var(--r-sm);
  background: var(--surface); padding: 10px 12px; font: inherit; cursor: pointer; }
.prow.on { border-color: var(--brand-500); background: var(--brand-050); }
</style>

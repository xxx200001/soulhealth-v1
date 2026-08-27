<template>
  <div class="askp">
    <!-- 会话区 -->
    <div class="flow" ref="flowEl">
      <!-- 开场引导 -->
      <div class="msg msg-ai fade-in">
        <b>你好，我是你的健康档案助手。</b><br />
        我会结合你档案中的报告、指标趋势与健康事件来回答。可以问我：
        <div class="row wrap" style="margin-top: 8px">
          <button v-for="s in starters" :key="s" class="chip" @click="send(s)">{{ s }}</button>
        </div>
      </div>

      <template v-for="(m, i) in messages" :key="i">
        <div v-if="m.role === 'user'" class="msg msg-user fade-in">{{ m.content }}</div>

        <div v-else class="msg msg-ai fade-in" :class="{ danger: m.kind === 'red_flag' }">
          <MarkdownView :source="m.content" />

          <!-- 追问选项：点击即发送 -->
          <div v-if="m.kind === 'followup' && m.options?.length && i === messages.length - 1"
               class="row wrap" style="margin-top: 8px">
            <button v-for="o in m.options" :key="o" class="chip" @click="send(o)">{{ o }}</button>
          </div>

          <!-- 候选事件确认（AC-16：确认后才入档） -->
          <div v-if="m.candidate && m.candidate.status === 'pending'" class="cand">
            <div class="tiny" style="color:#6F5518">
              是否把这条信息保存到健康档案？
            </div>
            <div class="cand-body">「{{ m.candidate.content }}」</div>
            <div class="row">
              <button class="btn btn-gold btn-sm" :disabled="m._resolving"
                      @click="resolve(m, true)">保存入档</button>
              <button class="btn btn-quiet btn-sm" :disabled="m._resolving"
                      @click="resolve(m, false)">暂不需要</button>
            </div>
          </div>
          <div v-else-if="m.candidate && m.candidate.status === 'confirmed'"
               class="tiny okline">✓ 已保存到健康档案，时间线与后续分析会用到它</div>
        </div>
      </template>

      <!-- AI 思考中动态卡片 -->
      <div v-if="busy" class="msg msg-ai thinking-msg fade-in">
        <div class="ai-thinking">
          <div class="think-icon-box">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spin-slow">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
            </svg>
          </div>
          <span class="think-label">健康档案助手正在结合数据分析解答</span>
          <span class="dot-flashing">
            <i></i><i></i><i></i>
          </span>
        </div>
      </div>
    </div>

    <!-- 输入区（固定于底栏之上） -->
    <div class="inputbar">
      <div class="inputbar-inner">
        <select v-if="convs.length" v-model="convPick" class="select conv"
                @change="switchConv">
          <option value="">新对话</option>
          <option v-for="c in convs" :key="c.id" :value="c.id">
            {{ c.title || '未命名对话' }}
          </option>
        </select>
        <input v-model="draft" class="input grow" placeholder="描述症状，或问指标 / 饮食 / 报告…"
               :disabled="busy" @keyup.enter="send()" />
        <button class="btn btn-primary send" :disabled="busy || !draft.trim()"
                @click="send()">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round"
               stroke-linejoin="round"><path d="M22 2 11 13M22 2 15 22l-4-9-9-4 20-7Z"/></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { api } from '../api'
import { useSessionStore } from '../store/session'
import MarkdownView from '../components/MarkdownView.vue'

const session = useSessionStore()
const flowEl = ref(null)
const messages = ref([])
const draft = ref('')
const busy = ref(false)
const convId = ref('')
const convs = ref([])
const convPick = ref('')

const starters = ['最近有点乏力，正常吗', '我的转氨酶怎么样了', '晚上应该怎么吃', '适合喝什么茶']

function scrollBottom() {
  nextTick(() => {
    flowEl.value?.scrollTo({ top: flowEl.value.scrollHeight, behavior: 'smooth' })
  })
}

async function send(text) {
  const content = (text ?? draft.value).trim()
  if (!content || busy.value) return
  draft.value = ''
  messages.value.push({ role: 'user', content })
  busy.value = true
  scrollBottom()
  try {
    const res = await api.ask(session.profileId, content, convId.value)
    convId.value = res.conversation_id
    convPick.value = res.conversation_id
    const r = res.reply
    messages.value.push({
      role: 'assistant', kind: r.kind, content: r.text,
      options: r.options || [], candidate: r.candidate || null,
    })
    refreshConvs()
  } catch (e) {
    messages.value.push({ role: 'assistant', kind: 'error',
      content: `出错了：${e.message}` })
  } finally {
    busy.value = false
    scrollBottom()
  }
}

async function resolve(m, accept) {
  m._resolving = true
  try {
    const r = await api.resolveCandidate(session.profileId, m.candidate.id, accept)
    m.candidate = { ...m.candidate, status: r.status }
  } catch (e) { alert(e.message) }
  finally { m._resolving = false }
}

async function refreshConvs() {
  try { convs.value = (await api.conversations(session.profileId)).items } catch { /* 忽略 */ }
}

async function switchConv() {
  messages.value = []
  convId.value = convPick.value
  if (!convPick.value) return
  try {
    const r = await api.conversation(convPick.value)
    messages.value = (r.messages || []).map((m) => ({
      role: m.role, kind: m.meta?.kind, content: m.content,
      options: m.meta?.options || [], candidate: null,
    }))
    scrollBottom()
  } catch (e) { alert(e.message) }
}

onMounted(refreshConvs)
</script>

<style scoped>
.askp { display: flex; flex-direction: column;
  height: calc(100vh - var(--header-h)); max-width: var(--maxw); margin: 0 auto; }
.flow { flex: 1; overflow-y: auto; display: flex; flex-direction: column;
  gap: var(--sp-3); padding: var(--sp-4) var(--sp-4)
  calc(var(--nav-h) + 76px); }
.msg.danger { border-color: var(--danger); background: var(--danger-bg); }
.okline { color: var(--ok); margin-top: 8px; }

.cand { margin-top: 10px; background: var(--gold-100);
  border: 1px solid #EBDDBD; border-radius: var(--r-sm);
  padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; }
.cand-body { font-size: 13.5px; color: #5B4712; }

.inputbar { position: fixed; left: 0; right: 0; bottom: var(--nav-h); z-index: 40;
  background: rgba(246, 248, 246, .95); backdrop-filter: blur(10px);
  border-top: 1px solid var(--line);
  padding: 8px var(--sp-4) calc(8px + env(safe-area-inset-bottom) * 0); }
.inputbar-inner { max-width: var(--maxw); margin: 0 auto; display: flex;
  gap: var(--sp-2); align-items: center; }
.conv { max-width: 116px; font-size: 12px; padding: 8px 26px 8px 10px; }
.send { width: 42px; height: 42px; padding: 0; border-radius: 50%; flex: none; }
:deep(.md) { font-size: 14px; }
:deep(.md h1), :deep(.md h2), :deep(.md h3) { font-size: 14px; margin: 10px 0 4px; }
:deep(.md strong) { color: var(--brand-800); }

/* 思考中动态卡片 */
.thinking-msg {
  padding: 11px 16px !important;
  background: #ffffff !important;
  border: 1px solid var(--brand-200, #c8ded4) !important;
  border-radius: var(--r-md) !important;
  border-bottom-left-radius: 4px !important;
  box-shadow: 0 2px 8px rgba(45, 95, 75, 0.06);
}
.ai-thinking {
  display: flex;
  align-items: center;
  gap: 9px;
}
.think-icon-box {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--brand-600);
}
.spin-slow {
  animation: spin 2.2s linear infinite;
}
.think-label {
  font-size: 13.5px;
  color: var(--ink-700);
  font-weight: 500;
  letter-spacing: 0.2px;
}
.dot-flashing {
  display: inline-flex;
  align-items: center;
  gap: 3.5px;
  margin-left: 2px;
}
.dot-flashing i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--brand-600);
  display: inline-block;
  animation: bounceDot 1.4s infinite ease-in-out both;
}
.dot-flashing i:nth-child(1) { animation-delay: -0.32s; }
.dot-flashing i:nth-child(2) { animation-delay: -0.16s; }
.dot-flashing i:nth-child(3) { animation-delay: 0s; }

@keyframes bounceDot {
  0%, 80%, 100% { transform: scale(0.3); opacity: 0.3; }
  40% { transform: scale(1); opacity: 1; }
}
</style>

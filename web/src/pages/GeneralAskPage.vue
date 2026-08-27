<template>
  <div class="gaskp">
    <!-- 会话区 -->
    <div class="flow" ref="flowEl">
      <!-- 开场引导 -->
      <div class="msg msg-ai fade-in">
        <b>你好，我是你的健康顾问。</b><br />
        你可以直接问我任何健康问题，我会尽力给出专业、实用的建议。
        <div class="row wrap" style="margin-top: 8px">
          <button v-for="s in starters" :key="s" class="chip" @click="send(s)">{{ s }}</button>
        </div>
      </div>

      <template v-for="(m, i) in messages" :key="i">
        <div v-if="m.role === 'user'" class="msg msg-user fade-in">{{ m.content }}</div>

        <div v-else class="msg msg-ai fade-in" :class="{ danger: m.kind === 'red_flag' }">
          <MarkdownView :source="m.content" />
        </div>
      </template>

      <div v-if="busy" class="msg msg-ai"><span class="spin"></span></div>

      <!-- 档案入口引导（在回答后温和提示） -->
      <div v-if="answered && !busy" class="archive-hint fade-in">
        <span class="hint-ico">💡</span>
        <span>上传体检报告后，可以使用
          <router-link to="/ask" class="hint-link">「结合档案问一问」</router-link>
          获得基于你真实数据的个性化解答
        </span>
      </div>
    </div>

    <!-- 输入区（固定于底栏之上） -->
    <div class="inputbar">
      <div class="inputbar-inner">
        <input v-model="draft" class="input grow" placeholder="问我任何健康问题：症状、饮食、运动、睡眠…"
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
import { nextTick, ref } from 'vue'
import { api } from '../api'
import MarkdownView from '../components/MarkdownView.vue'

const flowEl = ref(null)
const messages = ref([])
const draft = ref('')
const busy = ref(false)
const answered = ref(false)

const starters = [
  '经常熬夜怎么补救',
  '血压高平时注意什么',
  '减肥期间怎么吃',
  '总是觉得累是怎么回事',
  '喝水一天喝多少合适',
  '腰酸背痛怎么缓解',
]

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
    const res = await api.askGeneral(content)
    const r = res.reply
    messages.value.push({
      role: 'assistant', kind: r.kind, content: r.text,
    })
    answered.value = true
  } catch (e) {
    messages.value.push({ role: 'assistant', kind: 'error',
      content: `出错了：${e.message}` })
  } finally {
    busy.value = false
    scrollBottom()
  }
}
</script>

<style scoped>
.gaskp { display: flex; flex-direction: column;
  height: calc(100vh - var(--header-h)); max-width: var(--maxw); margin: 0 auto; }
.flow { flex: 1; overflow-y: auto; display: flex; flex-direction: column;
  gap: var(--sp-3); padding: var(--sp-4) var(--sp-4)
  calc(var(--nav-h) + 76px); }
.msg.danger { border-color: var(--danger); background: var(--danger-bg); }

.inputbar { position: fixed; left: 0; right: 0; bottom: var(--nav-h); z-index: 40;
  background: rgba(246, 248, 246, .95); backdrop-filter: blur(10px);
  border-top: 1px solid var(--line);
  padding: 8px var(--sp-4) calc(8px + env(safe-area-inset-bottom) * 0); }
.inputbar-inner { max-width: var(--maxw); margin: 0 auto; display: flex;
  gap: var(--sp-2); align-items: center; }
.send { width: 42px; height: 42px; padding: 0; border-radius: 50%; flex: none; }
:deep(.md) { font-size: 14px; }
:deep(.md h1), :deep(.md h2), :deep(.md h3) { font-size: 14px; margin: 10px 0 4px; }
:deep(.md strong) { color: var(--brand-800); }

.archive-hint {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 10px 14px; margin-top: 4px;
  background: var(--brand-050); border: 1px solid var(--brand-100);
  border-radius: var(--r-sm); font-size: 13px; color: var(--ink-600);
  line-height: 1.6;
}
.hint-ico { font-size: 16px; flex: none; margin-top: 1px; }
.hint-link { color: var(--brand-700); font-weight: 600; text-decoration: underline; }
</style>

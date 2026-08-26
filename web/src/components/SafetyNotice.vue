<template>
  <div class="sn" :class="`sn-${status}`">
    <div class="sn-head">
      <span class="sn-ico" v-html="meta.icon"></span>
      <b>{{ meta.title }}</b>
    </div>
    <div class="sn-body"><slot>{{ meta.desc }}</slot></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ status: { type: String, default: 'allow' } })
const M = {
  allow: { title: '已通过安全检查', desc: '本方案已按你的档案完成人群、过敏、用药核对。',
    icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 6 9 17l-5-5"/></svg>' },
  require_info: { title: '需要先补充安全信息', desc: '为了确认配方对你安全，请先补充以下信息。',
    icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5v.01"/></svg>' },
  block: { title: '已安全拦截', desc: '基于你的档案信息，本配方不适合当前情况。',
    icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M5.5 5.5l13 13"/></svg>' },
  professional_review: { title: '建议专业人员评估', desc: '当前情况建议先咨询医生或具备资质的专业人员。',
    icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3l9 5v5c0 5-4 8-9 8s-9-3-9-8V8l9-5Z"/></svg>' },
}
const meta = computed(() => M[props.status] || M.allow)
</script>

<style scoped>
.sn { border-radius: var(--r-md); padding: var(--sp-3) var(--sp-4); border: 1px solid; }
.sn-head { display: flex; align-items: center; gap: 8px; font-size: 14px; }
.sn-ico { display: flex; }
.sn-body { font-size: 13px; margin-top: 4px; opacity: .92; }
.sn-allow { background: var(--ok-bg); border-color: #CFE7DA; color: #1D5741; }
.sn-require_info { background: var(--info-bg); border-color: #CCDCEE; color: #24486B; }
.sn-block { background: var(--danger-bg); border-color: #F0CFCA; color: #8A2F27; }
.sn-professional_review { background: var(--warn-bg); border-color: #EEDBB8; color: #7A5312; }
</style>

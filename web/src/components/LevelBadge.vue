<template>
  <span class="lv" :class="`lv-${level}`">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ level: { type: String, default: 'stable' } })
const CN = { stable: '相对稳定', mild: '轻度关注', watch: '需要留意', priority: '重点关注' }
const label = computed(() => CN[props.level] || props.level)
</script>

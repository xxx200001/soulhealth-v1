<template>
  <svg :viewBox="`0 0 ${W} ${H}`" class="mini" preserveAspectRatio="none">
    <polyline v-if="pts.length > 1" :points="line" fill="none"
              :stroke="color" stroke-width="2" stroke-linecap="round"
              stroke-linejoin="round" />
    <circle v-if="pts.length" :cx="pts[pts.length-1][0]" :cy="pts[pts.length-1][1]"
            r="3" :fill="color" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  values: { type: Array, default: () => [] },
  color: { type: String, default: 'var(--gold-500)' },
})
const W = 96, H = 30, PAD = 4
const pts = computed(() => {
  const v = props.values.filter((x) => typeof x === 'number')
  if (!v.length) return []
  const min = Math.min(...v), max = Math.max(...v)
  const span = max - min || 1
  return v.map((x, i) => [
    PAD + (i * (W - PAD * 2)) / Math.max(1, v.length - 1),
    H - PAD - ((x - min) / span) * (H - PAD * 2),
  ])
})
const line = computed(() => pts.value.map((p) => p.join(',')).join(' '))
</script>

<style scoped>
.mini { width: 96px; height: 30px; display: block; }
</style>

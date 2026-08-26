<template>
  <div class="empty">
    <span class="icon">{{ icon }}</span>
    <div>{{ text }}</div>
    <slot />
  </div>
</template>
<script setup>
defineProps({ icon: { type: String, default: '○' }, text: { type: String, default: '暂无内容' } })
</script>

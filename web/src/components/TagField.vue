<template>
  <div class="field">
    <label class="label">{{ label }}
      <em v-if="updated" class="upd">{{ updated }}</em>
    </label>
    <div class="row wrap" style="gap: 6px">
      <span v-for="(t, i) in modelValue || []" :key="t + i" class="tag">
        {{ t }}
        <button class="tag-x" type="button" @click="rm(i)">×</button>
      </span>
      <input class="input" style="flex: 1; min-width: 150px"
             :placeholder="placeholder" v-model="draft"
             @keyup.enter="add" @blur="add" />
    </div>
    <span v-if="(!modelValue || !modelValue.length) && emptyHint" class="tiny">
      {{ emptyHint }}
    </span>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: Array,
  label: String,
  placeholder: String,
  updated: String,
  emptyHint: String,
})
const emit = defineEmits(['update:modelValue'])
const draft = ref('')

function add() {
  const v = draft.value.trim()
  if (!v) return
  emit('update:modelValue', [...(props.modelValue || []), v])
  draft.value = ''
}
function rm(i) {
  const arr = [...(props.modelValue || [])]
  arr.splice(i, 1)
  emit('update:modelValue', arr)
}
</script>

<style scoped>
.upd { font-style: normal; font-weight: 400; font-size: 11px;
  color: var(--ok); margin-left: 6px; }
.tag { display: inline-flex; align-items: center; gap: 4px;
  background: var(--brand-050); color: var(--brand-800);
  border: 1px solid var(--brand-100); border-radius: var(--r-full);
  padding: 5px 6px 5px 12px; font-size: 13px; }
.tag-x { border: none; background: none; color: var(--brand-500);
  font-size: 15px; cursor: pointer; line-height: 1; padding: 0 4px; }
</style>

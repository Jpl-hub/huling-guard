<script setup lang="ts">
import type { ViewMode } from '../types/runtime'

const props = defineProps<{
  modelValue: ViewMode
}>()

const emit = defineEmits<{
  'update:modelValue': [value: ViewMode]
}>()

function setMode(mode: ViewMode) {
  emit('update:modelValue', mode)
}
</script>

<template>
  <div class="mode-switch">
    <button
      type="button"
      class="mode-button"
      :class="{ active: props.modelValue === 'care' }"
      @click="setMode('care')"
    >
      值守视图
    </button>
    <button
      type="button"
      class="mode-button"
      :class="{ active: props.modelValue === 'xray' }"
      @click="setMode('xray')"
    >
      引擎透视
    </button>
  </div>
</template>

<style scoped>
.mode-switch {
  display: inline-flex;
  gap: 8px;
  padding: 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(120, 146, 176, 0.18);
}

.mode-button {
  border: 0;
  padding: 10px 16px;
  border-radius: 999px;
  background: transparent;
  color: rgba(226, 236, 247, 0.84);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 180ms ease, color 180ms ease;
}

.mode-button.active {
  background: linear-gradient(135deg, rgba(67, 215, 255, 0.2), rgba(47, 114, 255, 0.2));
  color: #f8fbff;
}
</style>

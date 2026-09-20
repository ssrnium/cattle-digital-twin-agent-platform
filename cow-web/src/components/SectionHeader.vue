<script setup lang="ts">
defineProps<{ title: string; eyebrow?: string; action?: string }>()
const emit = defineEmits<{ (e: 'action'): void }>()
</script>

<template>
  <div class="section-head">
    <div>
      <div v-if="eyebrow" class="eyebrow">{{ eyebrow }}</div>
      <div class="panel-title">{{ title }}</div>
    </div>
    <button v-if="action" class="ghost-btn" @click="emit('action')">{{ action }} ↗</button>
  </div>
</template>

<style scoped>
.section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.section-head .eyebrow { margin-bottom: 5px; }
.ghost-btn { color: #76b9c1; background: transparent; border: 0; font-size: 11px; cursor: pointer; }
.ghost-btn:hover { color: #a2edf0; }
</style>

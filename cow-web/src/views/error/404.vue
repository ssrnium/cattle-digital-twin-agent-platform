<template>
  <div class="not-found">
    <h1>404</h1>
    <p>页面不存在</p>
    <el-button type="primary" @click="$router.push('/dashboard')">返回总览</el-button>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.not-found {
  height: 100%; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 12px;
}
h1 { font-size: 64px; margin: 0; color: #409eff; }
</style>

<template>
  <router-view />
</template>

<script setup lang="ts">
// 根组件 - 仅提供路由视图
</script>

<style>
/* 全局样式 */
*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #1a1a2e;
  font-family: 'Noto Sans SC', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
}

/* 禁止 iOS 橡皮筋滚动 */
body {
  position: fixed;
  overscroll-behavior: none;
}

/* 滚动条美化 */
::-webkit-scrollbar {
  width: 4px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.15);
  border-radius: 2px;
}

#app {
  width: 100%;
  height: 100%;
}
</style>

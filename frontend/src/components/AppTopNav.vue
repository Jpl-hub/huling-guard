<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()

const items = [
  { path: '/live', label: '实时值守' },
  { path: '/records', label: '历史回看' },
  { path: '/system', label: '系统说明' },
]
</script>

<template>
  <header class="topnav">
    <div class="brand">
      <span class="brand-mark">HG</span>
      <div>
        <strong>护龄智守</strong>
        <p>单房间固定摄像头安全值守系统</p>
      </div>
    </div>

    <nav class="nav">
      <RouterLink
        v-for="item in items"
        :key="item.path"
        :to="item.path"
        class="nav-link"
        :class="{ active: route.path === item.path }"
      >
        {{ item.label }}
      </RouterLink>
    </nav>
  </header>
</template>

<style scoped>
.topnav {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: center;
  padding: 18px 28px;
  border-bottom: 1px solid rgba(112, 144, 181, 0.14);
  background:
    linear-gradient(180deg, rgba(4, 11, 19, 0.96), rgba(4, 11, 19, 0.88)),
    #050b13;
  backdrop-filter: blur(18px);
}

.brand {
  display: flex;
  gap: 14px;
  align-items: center;
  min-width: 0;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: linear-gradient(135deg, #43d7ff, #2f72ff);
  color: #04111d;
  font-size: 16px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.brand strong {
  display: block;
  font-size: 19px;
  line-height: 1.05;
}

.brand p {
  margin: 5px 0 0;
  color: rgba(204, 220, 238, 0.68);
  font-size: 12px;
  line-height: 1.45;
}

.nav {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.nav-link {
  padding: 10px 16px;
  border-radius: 999px;
  color: rgba(221, 233, 246, 0.78);
  text-decoration: none;
  font-size: 14px;
  font-weight: 700;
  transition: background-color 180ms ease, color 180ms ease, transform 180ms ease;
}

.nav-link:hover,
.nav-link.active {
  transform: translateY(-1px);
  background: rgba(67, 215, 255, 0.1);
  color: #f8fbff;
}

@media (max-width: 920px) {
  .topnav {
    flex-direction: column;
    align-items: flex-start;
    padding: 16px 18px;
  }
}
</style>

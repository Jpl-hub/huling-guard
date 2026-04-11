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
        <p>固定机位安全值守</p>
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
  padding: 18px 28px 16px;
  background: rgba(4, 11, 19, 0.94);
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
  background: rgba(67, 215, 255, 0.86);
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
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}

.nav-link {
  position: relative;
  padding: 12px 12px 10px;
  color: rgba(221, 233, 246, 0.76);
  text-decoration: none;
  font-size: 14px;
  font-weight: 700;
  transition: color 180ms ease, transform 180ms ease;
}

.nav-link::after {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 2px;
  height: 2px;
  border-radius: 999px;
  background: rgba(67, 215, 255, 0.9);
  opacity: 0;
  transform: scaleX(0.5);
  transition: opacity 180ms ease, transform 180ms ease;
}

.nav-link:hover,
.nav-link.active {
  color: #f8fbff;
}

.nav-link:hover::after,
.nav-link.active::after {
  opacity: 1;
  transform: scaleX(1);
}

@media (max-width: 920px) {
  .topnav {
    flex-direction: column;
    align-items: flex-start;
    padding: 16px 18px;
  }
}
</style>

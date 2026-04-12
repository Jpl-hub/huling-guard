<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()

const items = [
  { path: '/matrix', label: '监视器总览' },
  { path: '/live', label: '实时值守' },
  { path: '/records', label: '历史回看' },
  { path: '/brief', label: '交接班' },
  { path: '/system', label: '运行引擎' },
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
  gap: var(--space-6);
  align-items: center;
  padding: var(--space-5) var(--space-6) var(--space-4);
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-line-soft);
}

.brand {
  display: flex;
  gap: var(--space-3);
  align-items: center;
  min-width: 0;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  color: var(--color-bg-strong);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.brand strong {
  display: block;
  font-size: 18px;
  line-height: 1.05;
}

.brand p {
  margin: var(--space-1) 0 0;
  color: var(--color-text-tertiary);
  font-size: 12px;
  line-height: 1.45;
}

.nav {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  flex-wrap: wrap;
}

.nav-link {
  position: relative;
  padding: 10px 12px 11px;
  color: var(--color-text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 700;
  transition: color 180ms ease;
}

.nav-link::after {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 2px;
  height: 2px;
  border-radius: 999px;
  background: var(--color-accent);
  opacity: 0;
  transform: scaleX(0.5);
  transition: opacity 180ms ease, transform 180ms ease;
}

.nav-link:hover,
.nav-link.active {
  color: var(--color-text-primary);
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
    padding: var(--space-4) var(--space-5);
  }
}
</style>

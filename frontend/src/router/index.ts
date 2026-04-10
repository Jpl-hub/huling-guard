import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      redirect: '/live',
    },
    {
      path: '/live',
      component: () => import('../views/LiveMonitorView.vue'),
      meta: {
        title: '实时值守',
        subtitle: '',
      },
    },
    {
      path: '/records',
      component: () => import('../views/RecordsView.vue'),
      meta: {
        title: '历史回看',
        subtitle: '',
      },
    },
    {
      path: '/system',
      component: () => import('../views/SystemInfoView.vue'),
      meta: {
        title: '系统说明',
        subtitle: '',
      },
    },
  ],
})

export default router

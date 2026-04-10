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
        subtitle: '回看已保存记录，快速定位需要复看和确认的过程。',
      },
    },
    {
      path: '/system',
      component: () => import('../views/SystemInfoView.vue'),
      meta: {
        title: '系统说明',
        subtitle: '查看识别链路、状态定义和当前部署情况。',
      },
    },
  ],
})

export default router

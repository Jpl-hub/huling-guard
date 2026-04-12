import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      redirect: '/matrix',
    },
    {
      path: '/matrix',
      component: () => import('../views/MatrixWallView.vue'),
      meta: {
        title: '监视器总览',
        subtitle: '',
      },
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
      path: '/brief',
      component: () => import('../views/ShiftBriefView.vue'),
      meta: {
        title: '交接班简报',
        subtitle: '',
      },
    },
    {
      path: '/system',
      component: () => import('../views/SystemInfoView.vue'),
      meta: {
        title: '运行引擎',
        subtitle: '',
      },
    },
  ],
})

export default router

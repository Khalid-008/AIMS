import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'survey-list',
      component: () => import('@/views/SurveyListView.vue'),
    },
    {
      // Old workspace URL — redirect back to the list so the entry dialog can be used
      path: '/survey/:number',
      redirect: '/',
    },
    {
      path: '/survey/:number/analytics-report/:reportId',
      name: 'analytics-report',
      component: () => import('@/views/AnalyticsReportView.vue'),
    },
  ],
})

export default router

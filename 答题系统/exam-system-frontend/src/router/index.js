import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue')
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue')
  },
  {
    path: '/',
    component: () => import('../components/Layout.vue'),
    redirect: '/home',
    children: [
      {
        path: 'home',
        name: 'Home',
        component: () => import('../views/Home.vue')
      },
      {
        path: 'question',
        name: 'QuestionManage',
        component: () => import('../views/admin/QuestionManage.vue')
      },
      {
        path: 'student',
        name: 'StudentManage',
        component: () => import('../views/admin/StudentManage.vue')
      },
      {
        path: 'score',
        name: 'ScoreManage',
        component: () => import('../views/admin/ScoreManage.vue')
      },
      {
        path: 'exam',
        name: 'Exam',
        component: () => import('../views/student/Exam.vue')
      },
      {
        path: 'my-score',
        name: 'MyScore',
        component: () => import('../views/student/MyScore.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.path === '/login' || to.path === '/register') {
    next()
  } else if (!token) {
    next('/login')
  } else {
    next()
  }
})

export default router

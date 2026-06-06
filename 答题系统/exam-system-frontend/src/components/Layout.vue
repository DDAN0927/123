<template>
  <el-container style="min-height: 100vh">
    <el-aside v-if="!isMobile || sidebarOpen" :width="isMobile ? '220px' : '220px'" :class="['sidebar', { 'sidebar-mobile': isMobile }]">
      <div style="height: 60px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; font-weight: bold; border-bottom: 1px solid #3a4a5d">
        在线考试系统
      </div>
      <el-menu
        :default-active="$route.path"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
        @select="onMenuSelect"
      >
        <el-menu-item index="/home">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </el-menu-item>
        <template v-if="role === 'ADMIN'">
          <el-menu-item index="/question">
            <el-icon><Document /></el-icon>
            <span>题库管理</span>
          </el-menu-item>
          <el-menu-item index="/student">
            <el-icon><User /></el-icon>
            <span>学生管理</span>
          </el-menu-item>
          <el-menu-item index="/score">
            <el-icon><DataAnalysis /></el-icon>
            <span>成绩管理</span>
          </el-menu-item>
        </template>
        <template v-if="role === 'STUDENT'">
          <el-menu-item index="/exam">
            <el-icon><Edit /></el-icon>
            <span>在线答题</span>
          </el-menu-item>
          <el-menu-item index="/my-score">
            <el-icon><DataAnalysis /></el-icon>
            <span>我的成绩</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>
    <div v-if="isMobile && sidebarOpen" class="sidebar-overlay" @click="sidebarOpen = false"></div>
    <el-container>
      <el-header style="background: #fff; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 1px 4px rgba(0,21,41,.08); padding: 0 16px; height: 56px">
        <div style="display: flex; align-items: center; gap: 12px">
          <el-button v-if="isMobile" :icon="Fold" text @click="sidebarOpen = !sidebarOpen" style="font-size: 20px" />
          <span style="font-size: 16px; font-weight: 600">{{ role === 'ADMIN' ? '管理员' : '学生' }}工作台</span>
        </div>
        <div style="display: flex; align-items: center; gap: 12px">
          <span style="color: #666; font-size: 14px">{{ username }}</span>
          <el-button type="danger" size="small" @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main :style="{ background: '#f0f2f5', padding: isMobile ? '12px' : '20px' }">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { HomeFilled, Document, DataAnalysis, Edit, User, Fold } from '@element-plus/icons-vue'

const router = useRouter()
const role = ref(localStorage.getItem('role') || '')
const username = ref(localStorage.getItem('username') || '')
const sidebarOpen = ref(false)
const windowWidth = ref(window.innerWidth)

const isMobile = computed(() => windowWidth.value < 768)

const onResize = () => { windowWidth.value = window.innerWidth }
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))

const onMenuSelect = () => { if (isMobile.value) sidebarOpen.value = false }

const logout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('role')
  localStorage.removeItem('username')
  router.push('/login')
}
</script>

<style scoped>
.sidebar {
  background: #304156;
  transition: transform 0.3s;
}
.sidebar-mobile {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1001;
  height: 100vh;
}
.sidebar-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
}
</style>

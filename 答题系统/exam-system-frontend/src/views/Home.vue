<template>
  <div>
    <el-row :gutter="20" style="margin-bottom: 20px" class="home-cards">
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" style="text-align: center; margin-bottom: 12px">
          <div style="font-size: 36px; color: #409EFF; margin-bottom: 10px">📚</div>
          <div style="font-size: 20px; font-weight: bold; color: #303133">{{ role === 'ADMIN' ? '题库管理' : '在线答题' }}</div>
          <div style="color: #909399; margin-top: 8px">{{ role === 'ADMIN' ? '管理考试题目' : '开始你的考试' }}</div>
          <el-button type="primary" style="margin-top: 16px" @click="$router.push(role === 'ADMIN' ? '/question' : '/exam')">
            {{ role === 'ADMIN' ? '管理题库' : '开始答题' }}
          </el-button>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" style="text-align: center; margin-bottom: 12px">
          <div style="font-size: 36px; color: #67C23A; margin-bottom: 10px">📊</div>
          <div style="font-size: 20px; font-weight: bold; color: #303133">成绩查询</div>
          <div style="color: #909399; margin-top: 8px">{{ role === 'ADMIN' ? '查看所有成绩' : '查看我的成绩' }}</div>
          <el-button type="success" style="margin-top: 16px" @click="$router.push(role === 'ADMIN' ? '/score' : '/my-score')">
            查看成绩
          </el-button>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" style="text-align: center; margin-bottom: 12px">
          <div style="font-size: 36px; color: #E6A23C; margin-bottom: 10px">👤</div>
          <div style="font-size: 20px; font-weight: bold; color: #303133">个人信息</div>
          <div style="color: #909399; margin-top: 8px">用户：{{ username }}</div>
          <div style="color: #909399; margin-top: 4px">角色：{{ role === 'ADMIN' ? '管理员' : '学生' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>
        <span style="font-weight: bold">系统说明</span>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="系统名称">在线考试答题系统</el-descriptions-item>
        <el-descriptions-item label="技术栈">SpringBoot + MyBatis + Vue + Element Plus</el-descriptions-item>
        <el-descriptions-item label="功能说明">
          <span v-if="role === 'ADMIN'">管理员可以管理题库（增删改查）、查看所有学生成绩</span>
          <span v-else>学生可以选择科目进行在线答题，系统自动随机组卷并判分，可查看历史成绩</span>
        </el-descriptions-item>
        <el-descriptions-item label="默认账号">
          管理员：DDAN / admin123 &nbsp;&nbsp; 学生：student / 123456
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const role = ref(localStorage.getItem('role') || '')
const username = ref(localStorage.getItem('username') || '')
</script>

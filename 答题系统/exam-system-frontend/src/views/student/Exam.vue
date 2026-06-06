<template>
  <div>
    <el-card v-if="!examStarted">
      <template #header>
        <span style="font-weight: bold; font-size: 16px">在线答题</span>
      </template>
      <div style="text-align: center; padding: 40px 0">
        <div style="font-size: 48px; margin-bottom: 20px">📝</div>
        <h3 style="margin-bottom: 20px; color: #303133">选择科目开始答题</h3>
        <div class="subject-grid">
          <el-card
            v-for="sub in subjects"
            :key="sub"
            shadow="hover"
            style="cursor: pointer; text-align: center"
            class="subject-card"
            @click="startExam(sub)"
          >
            <div style="font-size: 24px; margin-bottom: 8px">{{ subIcons[sub] }}</div>
            <div style="font-weight: bold">{{ sub }}</div>
          </el-card>
        </div>
      </div>
    </el-card>

    <el-card v-else>
      <template #header>
        <div class="exam-header">
          <span style="font-weight: bold; font-size: 16px">{{ currentSubject }} - 答题中</span>
          <div class="exam-header-right">
            <span style="color: #E6A23C; font-weight: bold; font-size: 14px">
              ⏱ {{ formatTime(remainTime) }}
            </span>
            <el-button type="success" size="small" :loading="submitting" @click="handleSubmit">交卷</el-button>
          </div>
        </div>
      </template>

      <div class="exam-body">
        <div class="exam-questions">
          <div v-for="(q, index) in questions" :key="q.id" :style="{ marginBottom: '16px', padding: '12px', background: index === currentIndex ? '#ecf5ff' : '#fff', borderRadius: '8px', border: index === currentIndex ? '2px solid #409EFF' : '1px solid #ebeef5' }">
            <div style="margin-bottom: 10px; font-weight: bold; font-size: 14px">
              {{ index + 1 }}. {{ q.content }}
            </div>
            <el-radio-group v-model="answers[q.id]" style="display: flex; flex-direction: column; gap: 6px">
              <el-radio :label="'A'" style="margin: 0">A. {{ q.optionA }}</el-radio>
              <el-radio :label="'B'" style="margin: 0">B. {{ q.optionB }}</el-radio>
              <el-radio :label="'C'" style="margin: 0">C. {{ q.optionC }}</el-radio>
              <el-radio :label="'D'" style="margin: 0">D. {{ q.optionD }}</el-radio>
            </el-radio-group>
          </div>
        </div>

        <div class="exam-sidebar">
          <h4 style="margin-bottom: 10px; font-size: 14px">答题卡</h4>
          <div style="display: flex; flex-wrap: wrap; gap: 6px">
            <div
              v-for="(q, index) in questions"
              :key="q.id"
              :style="{
                width: '32px', height: '32px', borderRadius: '4px',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '13px', cursor: 'pointer',
                background: answers[q.id] ? '#409EFF' : '#f0f0f0',
                color: answers[q.id] ? '#fff' : '#606266'
              }"
              @click="currentIndex = index"
            >
              {{ index + 1 }}
            </div>
          </div>
          <div style="margin-top: 12px; font-size: 13px; color: #909399">
            已答：{{ answeredCount }} / {{ questions.length }}
          </div>
        </div>
      </div>
    </el-card>

    <el-dialog v-model="resultVisible" title="答题结果" width="90%" style="max-width: 450px" :close-on-click-modal="false" :show-close="false">
      <div style="text-align: center; padding: 20px 0">
        <div style="font-size: 60px; margin-bottom: 16px">{{ examResult.score >= 60 ? '🎉' : '😢' }}</div>
        <div style="font-size: 36px; font-weight: bold; margin-bottom: 8px" :style="{ color: examResult.score >= 60 ? '#67C23A' : '#F56C6C' }">
          {{ examResult.score }}分
        </div>
        <div style="color: #909399; margin-bottom: 16px">
          总题数：{{ examResult.totalQuestions }} &nbsp; 正确：{{ examResult.correctCount }}
        </div>
        <el-button type="primary" @click="backToHome">返回首页</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { getRandomPaper } from '../../api/question'
import { submitExam } from '../../api/score'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const subjects = ['Java基础', '数据库', 'Spring', '计算机网络']
const subIcons = { 'Java基础': '☕', '数据库': '🗄️', 'Spring': '🍃', '计算机网络': '🌐' }

const examStarted = ref(false)
const currentSubject = ref('')
const questions = ref([])
const answers = reactive({})
const currentIndex = ref(0)
const submitting = ref(false)
const resultVisible = ref(false)
const examResult = reactive({ score: 0, totalQuestions: 0, correctCount: 0 })
const remainTime = ref(1800)
let timer = null

const answeredCount = computed(() => Object.keys(answers).length)

const formatTime = (seconds) => {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const startExam = async (subject) => {
  try {
    const res = await getRandomPaper({ subject, count: 10 })
    if (!res.data || res.data.length === 0) {
      ElMessage.warning('该科目暂无题目')
      return
    }
    currentSubject.value = subject
    questions.value = res.data
    Object.keys(answers).forEach(k => delete answers[k])
    examStarted.value = true
    remainTime.value = 1800
    timer = setInterval(() => {
      remainTime.value--
      if (remainTime.value <= 0) {
        clearInterval(timer)
        handleSubmit()
      }
    }, 1000)
  } catch (e) {
    // handled
  }
}

const handleSubmit = async () => {
  if (timer) clearInterval(timer)

  const unanswered = questions.value.filter(q => !answers[q.id]).length
  if (unanswered > 0) {
    try {
      await ElMessageBox.confirm(`还有 ${unanswered} 题未作答，确定交卷吗？`, '提示', { type: 'warning' })
    } catch {
      remainTime.value = remainTime.value || 1
      timer = setInterval(() => {
        remainTime.value--
        if (remainTime.value <= 0) {
          clearInterval(timer)
          handleSubmit()
        }
      }, 1000)
      return
    }
  }

  submitting.value = true
  try {
    const answerList = questions.value.map(q => ({
      questionId: String(q.id),
      answer: answers[q.id] || ''
    }))
    const res = await submitExam({
      subject: currentSubject.value,
      answers: answerList
    })
    Object.assign(examResult, res.data)
    examStarted.value = false
    resultVisible.value = true
  } catch (e) {
    // handled
  } finally {
    submitting.value = false
  }
}

const backToHome = () => {
  resultVisible.value = false
  router.push('/home')
}

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.subject-grid {
  display: flex;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
  max-width: 600px;
  margin: 0 auto;
}
.subject-card {
  width: 120px;
}
.exam-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.exam-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.exam-body {
  display: flex;
  gap: 20px;
}
.exam-questions {
  flex: 1;
  min-width: 0;
}
.exam-sidebar {
  width: 200px;
  flex-shrink: 0;
}
@media (max-width: 768px) {
  .subject-grid {
    gap: 10px;
  }
  .subject-card {
    width: calc(50% - 10px);
  }
  .exam-body {
    flex-direction: column;
  }
  .exam-sidebar {
    width: 100%;
    position: static;
    border-top: 1px solid #ebeef5;
    padding-top: 12px;
  }
  .exam-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

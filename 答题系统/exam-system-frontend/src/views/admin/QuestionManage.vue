<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span style="font-weight: bold; font-size: 16px">题库管理</span>
          <div class="card-header-actions">
            <el-select v-model="searchSubject" placeholder="按科目筛选" clearable style="width: 160px" @change="loadData">
              <el-option label="Java基础" value="Java基础" />
              <el-option label="数据库" value="数据库" />
              <el-option label="Spring" value="Spring" />
              <el-option label="计算机网络" value="计算机网络" />
            </el-select>
            <el-button type="primary" @click="handleAdd">新增题目</el-button>
          </div>
        </div>
      </template>

      <div style="overflow-x: auto">
      <el-table :data="tableData" border stripe style="min-width: 800px">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="subject" label="科目" width="120" />
        <el-table-column prop="content" label="题目内容" min-width="200" show-overflow-tooltip />
        <el-table-column prop="optionA" label="选项A" width="120" show-overflow-tooltip />
        <el-table-column prop="optionB" label="选项B" width="120" show-overflow-tooltip />
        <el-table-column prop="optionC" label="选项C" width="120" show-overflow-tooltip />
        <el-table-column prop="optionD" label="选项D" width="120" show-overflow-tooltip />
        <el-table-column prop="answer" label="答案" width="70" align="center" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>

      <el-pagination
        style="margin-top: 16px; justify-content: flex-end"
        v-model:current-page="pageNum"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[5, 10, 20]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑题目' : '新增题目'" width="90%" style="max-width: 600px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="科目" prop="subject">
          <el-select v-model="form.subject" placeholder="请选择科目" style="width: 100%">
            <el-option label="Java基础" value="Java基础" />
            <el-option label="数据库" value="数据库" />
            <el-option label="Spring" value="Spring" />
            <el-option label="计算机网络" value="计算机网络" />
          </el-select>
        </el-form-item>
        <el-form-item label="题目内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="3" placeholder="请输入题目内容" />
        </el-form-item>
        <el-form-item label="选项A" prop="optionA">
          <el-input v-model="form.optionA" placeholder="请输入选项A" />
        </el-form-item>
        <el-form-item label="选项B" prop="optionB">
          <el-input v-model="form.optionB" placeholder="请输入选项B" />
        </el-form-item>
        <el-form-item label="选项C" prop="optionC">
          <el-input v-model="form.optionC" placeholder="请输入选项C" />
        </el-form-item>
        <el-form-item label="选项D" prop="optionD">
          <el-input v-model="form.optionD" placeholder="请输入选项D" />
        </el-form-item>
        <el-form-item label="正确答案" prop="answer">
          <el-radio-group v-model="form.answer">
            <el-radio label="A">A</el-radio>
            <el-radio label="B">B</el-radio>
            <el-radio label="C">C</el-radio>
            <el-radio label="D">D</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getQuestionList, addQuestion, updateQuestion, deleteQuestion } from '../../api/question'
import { ElMessage, ElMessageBox } from 'element-plus'

const tableData = ref([])
const pageNum = ref(1)
const pageSize = ref(10)
const total = ref(0)
const searchSubject = ref('')
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref()

const form = reactive({
  id: null,
  subject: '',
  content: '',
  optionA: '',
  optionB: '',
  optionC: '',
  optionD: '',
  answer: ''
})

const rules = {
  subject: [{ required: true, message: '请选择科目', trigger: 'change' }],
  content: [{ required: true, message: '请输入题目内容', trigger: 'blur' }],
  optionA: [{ required: true, message: '请输入选项A', trigger: 'blur' }],
  optionB: [{ required: true, message: '请输入选项B', trigger: 'blur' }],
  optionC: [{ required: true, message: '请输入选项C', trigger: 'blur' }],
  optionD: [{ required: true, message: '请输入选项D', trigger: 'blur' }],
  answer: [{ required: true, message: '请选择正确答案', trigger: 'change' }]
}

const loadData = async () => {
  const res = await getQuestionList({
    pageNum: pageNum.value,
    pageSize: pageSize.value,
    subject: searchSubject.value || undefined
  })
  tableData.value = res.data.list
  total.value = res.data.total
}

const resetForm = () => {
  Object.assign(form, { id: null, subject: '', content: '', optionA: '', optionB: '', optionC: '', optionD: '', answer: '' })
}

const handleAdd = () => {
  resetForm()
  isEdit.value = false
  dialogVisible.value = true
}

const handleEdit = (row) => {
  Object.assign(form, { ...row })
  isEdit.value = true
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value.validate()
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateQuestion(form)
      ElMessage.success('修改成功')
    } else {
      await addQuestion(form)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    // handled
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (id) => {
  await ElMessageBox.confirm('确定删除该题目吗？', '提示', { type: 'warning' })
  await deleteQuestion(id)
  ElMessage.success('删除成功')
  loadData()
}

onMounted(() => loadData())
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.card-header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
@media (max-width: 768px) {
  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span style="font-weight: bold; font-size: 16px">学生管理</span>
          <div class="card-header-actions">
            <el-input v-model="searchUsername" placeholder="搜索用户名" clearable style="width: 160px" @clear="loadData" @keyup.enter="loadData" />
            <el-select v-model="searchRole" placeholder="按角色筛选" clearable style="width: 130px" @change="loadData">
              <el-option label="学生" value="STUDENT" />
              <el-option label="管理员" value="ADMIN" />
            </el-select>
            <el-button type="primary" @click="loadData">搜索</el-button>
            <el-button type="success" @click="handleAdd">添加学生</el-button>
          </div>
        </div>
      </template>

      <div style="overflow-x: auto">
      <el-table :data="tableData" border stripe style="min-width: 600px">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="role" label="角色" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.role === 'ADMIN' ? 'danger' : 'primary'" size="small">{{ row.role === 'ADMIN' ? '管理员' : '学生' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" min-width="160" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="warning" size="small" @click="handleResetPwd(row)">重置密码</el-button>
            <el-button type="danger" size="small" :disabled="row.role === 'ADMIN'" @click="handleDelete(row)">删除</el-button>
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

    <el-dialog v-model="addDialogVisible" title="添加学生" width="90%" style="max-width: 450px" :close-on-click-modal="false">
      <el-form ref="addFormRef" :model="addForm" :rules="addRules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="addForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="addForm.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="addForm.role" placeholder="请选择角色" style="width: 100%">
            <el-option label="学生" value="STUDENT" />
            <el-option label="管理员" value="ADMIN" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleAddSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetDialogVisible" title="重置密码" width="90%" style="max-width: 450px" :close-on-click-modal="false">
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-width="80px">
        <el-form-item label="用户名">
          <el-input :model-value="resetForm.username" disabled />
        </el-form-item>
        <el-form-item label="新密码" prop="password">
          <el-input v-model="resetForm.password" type="password" show-password placeholder="请输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleResetSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getUserList, addUser, resetPassword, deleteUser } from '../../api/user'
import { ElMessage, ElMessageBox } from 'element-plus'

const tableData = ref([])
const pageNum = ref(1)
const pageSize = ref(10)
const total = ref(0)
const searchUsername = ref('')
const searchRole = ref('')
const submitting = ref(false)

const addDialogVisible = ref(false)
const addFormRef = ref()
const addForm = reactive({ username: '', password: '', role: 'STUDENT' })
const addRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }, { min: 4, message: '密码至少4位', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }]
}

const resetDialogVisible = ref(false)
const resetFormRef = ref()
const resetForm = reactive({ id: null, username: '', password: '' })
const resetRules = {
  password: [{ required: true, message: '请输入新密码', trigger: 'blur' }, { min: 4, message: '密码至少4位', trigger: 'blur' }]
}

const loadData = async () => {
  const res = await getUserList({
    pageNum: pageNum.value,
    pageSize: pageSize.value,
    username: searchUsername.value || undefined,
    role: searchRole.value || undefined
  })
  tableData.value = res.data.list
  total.value = res.data.total
}

const handleAdd = () => {
  Object.assign(addForm, { username: '', password: '', role: 'STUDENT' })
  addDialogVisible.value = true
}

const handleAddSubmit = async () => {
  await addFormRef.value.validate()
  submitting.value = true
  try {
    await addUser(addForm)
    ElMessage.success('添加成功')
    addDialogVisible.value = false
    loadData()
  } catch (e) {
    // handled
  } finally {
    submitting.value = false
  }
}

const handleResetPwd = (row) => {
  Object.assign(resetForm, { id: row.id, username: row.username, password: '' })
  resetDialogVisible.value = true
}

const handleResetSubmit = async () => {
  await resetFormRef.value.validate()
  submitting.value = true
  try {
    await resetPassword({ id: resetForm.id, password: resetForm.password })
    ElMessage.success('密码重置成功')
    resetDialogVisible.value = false
    loadData()
  } catch (e) {
    // handled
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确定删除用户「${row.username}」吗？`, '提示', { type: 'warning' })
  await deleteUser(row.id)
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

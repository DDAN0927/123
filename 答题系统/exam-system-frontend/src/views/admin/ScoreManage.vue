<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span style="font-weight: bold; font-size: 16px">成绩管理</span>
          <div class="card-header-actions">
            <el-input v-model="searchUsername" placeholder="按用户名搜索" clearable style="width: 160px" @clear="loadData" />
            <el-select v-model="searchSubject" placeholder="按科目筛选" clearable style="width: 140px" @change="loadData">
              <el-option label="Java基础" value="Java基础" />
              <el-option label="数据库" value="数据库" />
              <el-option label="Spring" value="Spring" />
              <el-option label="计算机网络" value="计算机网络" />
            </el-select>
            <el-button type="primary" @click="loadData">搜索</el-button>
          </div>
        </div>
      </template>

      <div style="overflow-x: auto">
      <el-table :data="tableData" border stripe style="min-width: 600px">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="学生" min-width="100" />
        <el-table-column prop="subject" label="科目" min-width="100" />
        <el-table-column prop="totalQuestions" label="总题数" width="80" align="center" />
        <el-table-column prop="correctCount" label="正确数" width="80" align="center" />
        <el-table-column prop="score" label="得分" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.score >= 60 ? 'success' : 'danger'" size="small">{{ row.score }}分</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="答题时间" min-width="150" />
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getScoreList } from '../../api/score'

const tableData = ref([])
const pageNum = ref(1)
const pageSize = ref(10)
const total = ref(0)
const searchUsername = ref('')
const searchSubject = ref('')

const loadData = async () => {
  const res = await getScoreList({
    pageNum: pageNum.value,
    pageSize: pageSize.value,
    username: searchUsername.value || undefined,
    subject: searchSubject.value || undefined
  })
  tableData.value = res.data.list
  total.value = res.data.total
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

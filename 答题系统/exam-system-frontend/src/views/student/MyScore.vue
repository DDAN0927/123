<template>
  <div>
    <el-card>
      <template #header>
        <span style="font-weight: bold; font-size: 16px">我的成绩</span>
      </template>

      <div style="overflow-x: auto">
      <el-table :data="tableData" border stripe style="min-width: 500px">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="subject" label="科目" min-width="100" />
        <el-table-column prop="totalQuestions" label="总题数" width="80" align="center" />
        <el-table-column prop="correctCount" label="正确数" width="80" align="center" />
        <el-table-column prop="score" label="得分" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.score >= 60 ? 'success' : 'danger'" size="small">{{ row.score }}分</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="答题时间" min-width="140" />
      </el-table>
      </div>

      <el-empty v-if="tableData.length === 0 && !loading" description="暂无答题记录" />

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
import { getMyScore } from '../../api/score'

const tableData = ref([])
const pageNum = ref(1)
const pageSize = ref(10)
const total = ref(0)
const loading = ref(false)

const loadData = async () => {
  loading.value = true
  try {
    const res = await getMyScore({
      pageNum: pageNum.value,
      pageSize: pageSize.value
    })
    tableData.value = res.data.list
    total.value = res.data.total
  } catch (e) {
    // handled
  } finally {
    loading.value = false
  }
}

onMounted(() => loadData())
</script>

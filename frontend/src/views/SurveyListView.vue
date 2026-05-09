<template>
  <div class="page">
    <header class="topbar">
      <span class="brand">Survey AI</span>
    </header>

    <main class="container">
      <h2>Surveys <span class="count" v-if="!loading">({{ filtered.length }})</span></h2>

      <div v-if="loading" class="center"><div class="spinner" /></div>
      <p v-else-if="error" class="error-msg">{{ error }}</p>

      <template v-else>
        <div class="filter-row">
          <input v-model="search" placeholder="Search surveys…" class="search-input" />
          <select v-model="statusFilter" class="filter-select">
            <option value="">All statuses</option>
            <option>PUBLISHED</option>
            <option>CLOSED</option>
          </select>
        </div>

        <div v-if="filtered.length === 0" class="empty">No surveys found.</div>

        <template v-else>
          <div class="grid">
            <div
              v-for="s in paginated"
              :key="s.id"
              class="card survey-card"
              @click="openEntry(s.surveyNumber)"
            >
              <div class="survey-header">
                <div class="survey-number">{{ s.surveyNumber }}</div>
                <span :class="['status-badge', s.status.toLowerCase()]">{{ s.status }}</span>
              </div>
              <div class="survey-subject">{{ s.subject || s.subjectAr || '—' }}</div>
              <div class="survey-description" v-if="s.description || s.descriptionAr">
                {{ s.description || s.descriptionAr }}
              </div>
              <div class="survey-meta">
                <span v-if="s.createBy">By {{ s.createBy }}</span>
                <span v-if="s.createdDate"> • {{ new Date(s.createdDate).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) }}</span>
              </div>
              <div class="survey-tags">
                <span class="tag" :class="s.isPublic ? 'tag-public' : 'tag-private'">
                  {{ s.isPublic ? 'Public' : 'Private' }}
                </span>
                <span class="tag tag-location" v-if="s.isLocation">Location</span>
                <span class="tag tag-answered" v-if="s.answered">Answered</span>
              </div>
            </div>
          </div>

          <div class="pagination" v-if="totalPages > 1">
            <span class="page-info">
              {{ (currentPage - 1) * pageSize + 1 }}–{{ Math.min(currentPage * pageSize, filtered.length) }}
              of {{ filtered.length }}
            </span>
            <div class="page-controls">
              <button class="page-btn" :disabled="currentPage === 1" @click="currentPage--">&#8249;</button>
              <template v-for="p in pageNumbers" :key="p">
                <span v-if="p === '...'" class="ellipsis">…</span>
                <button
                  v-else
                  class="page-btn"
                  :class="{ active: p === currentPage }"
                  @click="currentPage = p as number"
                >{{ p }}</button>
              </template>
              <button class="page-btn" :disabled="currentPage === totalPages" @click="currentPage++">&#8250;</button>
            </div>
          </div>
        </template>
      </template>
    </main>

    <SurveyEntryDialog
      v-model="entryDialogOpen"
      :survey-number="selectedSurveyNumber"
      lang="en"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { api, type ExternalSurvey } from '@/api/client'
import SurveyEntryDialog from '@/components/SurveyEntryDialog.vue'

const PAGE_SIZE = 10

const surveys = ref<ExternalSurvey[]>([])
const loading = ref(true)
const error = ref('')
const search = ref('')
const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = PAGE_SIZE

const entryDialogOpen = ref(false)
const selectedSurveyNumber = ref('')

function openEntry(surveyNumber: string) {
  selectedSurveyNumber.value = surveyNumber
  entryDialogOpen.value = true
}

const filtered = computed(() =>
  surveys.value.filter((s) => {
    const matchSearch =
      !search.value ||
      (s.subject ?? '').toLowerCase().includes(search.value.toLowerCase()) ||
      (s.subjectAr ?? '').includes(search.value) ||
      (s.description ?? '').toLowerCase().includes(search.value.toLowerCase()) ||
      (s.descriptionAr ?? '').includes(search.value) ||
      s.surveyNumber.toLowerCase().includes(search.value.toLowerCase())
    const matchStatus = !statusFilter.value || s.status === statusFilter.value
    return matchSearch && matchStatus
  }),
)

const totalPages = computed(() => Math.ceil(filtered.value.length / pageSize))

const paginated = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filtered.value.slice(start, start + pageSize)
})

const pageNumbers = computed(() => {
  const total = totalPages.value
  const cur = currentPage.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages: (number | string)[] = [1]
  if (cur > 3) pages.push('...')
  for (let p = Math.max(2, cur - 1); p <= Math.min(total - 1, cur + 1); p++) pages.push(p)
  if (cur < total - 2) pages.push('...')
  pages.push(total)
  return pages
})

watch([search, statusFilter], () => { currentPage.value = 1 })

onMounted(async () => {
  try {
    const res = await api.surveys.list()
    surveys.value = res.data
  } catch (e: unknown) {
    error.value = (e as Error).message || 'Failed to load surveys'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page { min-height: 100vh; }

.topbar {
  display: flex;
  align-items: center;
  padding: 14px 24px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.brand { font-size: 1.1rem; font-weight: 700; color: #4361ee; }

.container { max-width: 1100px; margin: 0 auto; padding: 32px 20px; }
h2 { font-size: 1.5rem; margin-bottom: 20px; }
.count { font-size: 1rem; font-weight: 400; color: #888; }

.filter-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}
.search-input, .filter-select {
  padding: 8px 12px;
  border: 1.5px solid #ddd;
  border-radius: 8px;
  font-size: 0.9rem;
}
.search-input { flex: 1; }
.search-input:focus, .filter-select:focus { outline: none; border-color: #4361ee; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.survey-card {
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  padding: 16px;
}
.survey-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.1); }

.survey-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.survey-number { font-size: 0.78rem; color: #888; }
.survey-subject { font-size: 1rem; font-weight: 600; margin-bottom: 6px; }
.survey-description { font-size: 0.85rem; color: #555; margin-bottom: 10px; line-height: 1.4; }
.survey-meta { font-size: 0.75rem; color: #999; margin-bottom: 10px; }

.survey-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.tag {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 12px;
}
.tag-public { background: #d1fae5; color: #065f46; }
.tag-private { background: #fef3c7; color: #92400e; }
.tag-location { background: #dbeafe; color: #1e40af; }
.tag-answered { background: #e0e7ff; color: #3730a3; }

.status-badge {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  text-transform: uppercase;
}
.status-badge.published { background: #d1fae5; color: #065f46; }
.status-badge.closed    { background: #fee2e2; color: #991b1b; }

.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 28px;
  flex-wrap: wrap;
  gap: 12px;
}

.page-info { font-size: 0.85rem; color: #888; }

.page-controls { display: flex; align-items: center; gap: 4px; }

.page-btn {
  min-width: 34px;
  height: 34px;
  padding: 0 8px;
  border: 1.5px solid #ddd;
  border-radius: 8px;
  background: #fff;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.15s;
}
.page-btn:hover:not(:disabled) { border-color: #4361ee; color: #4361ee; }
.page-btn.active { background: #4361ee; color: #fff; border-color: #4361ee; font-weight: 600; }
.page-btn:disabled { opacity: 0.35; cursor: default; }

.ellipsis { padding: 0 4px; color: #aaa; font-size: 0.9rem; }

.center { display: flex; justify-content: center; padding: 60px; }
.empty { text-align: center; color: #888; padding: 40px; }
.error-msg { text-align: center; color: #dc2626; padding: 40px; }
</style>

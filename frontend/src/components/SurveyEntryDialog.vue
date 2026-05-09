<template>
  <div v-if="modelValue" class="dialog-backdrop" @click.self="close">
    <div class="dialog-card">
      <header class="dialog-head">
        <h2>{{ lang === 'ar' ? 'فتح استبيان' : 'Open survey' }}</h2>
        <button class="close-btn" @click="close" aria-label="close">×</button>
      </header>

      <div class="dialog-body">
        <!-- Previous reports -->
        <section v-if="listLoading" class="list-loading">
          <span class="spinner-sm" />
          {{ lang === 'ar' ? 'تحميل التقارير…' : 'Loading reports…' }}
        </section>

        <template v-else-if="!listLoading">
          <p v-if="listError" class="list-warn">
            {{ lang === 'ar' ? '⚠️ تعذر تحميل التقارير السابقة' : '⚠️ Could not load previous reports' }}
          </p>

          <section v-if="reports.length > 0" class="prev-section">
            <h3 class="section-label">
              {{ lang === 'ar' ? 'تقارير سابقة' : 'Previous reports' }}
            </h3>
            <div class="prev-row">
              <select v-model="selectedReportId" class="report-select">
                <option :value="null" disabled>
                  {{ lang === 'ar' ? '— اختر تقريراً —' : '— Select a report —' }}
                </option>
                <option v-for="r in reports" :key="r.reportId" :value="r.reportId">
                  {{ reportLabel(r) }}
                </option>
              </select>
              <button
                type="button"
                class="btn btn-primary"
                :disabled="selectedReportId === null"
                @click="openReport(selectedReportId!)"
              >
                {{ lang === 'ar' ? 'فتح' : 'Open' }}
              </button>
            </div>
            <div class="divider">
              <span>{{ lang === 'ar' ? 'أو أنشئ تقريراً جديداً' : 'or generate a new one' }}</span>
            </div>
          </section>
        </template>

        <!-- Generate new form -->
        <form @submit.prevent="submit">
          <div class="field">
            <label>{{ lang === 'ar' ? 'لغة التقرير' : 'Report language' }}</label>
            <div class="radio-row">
              <label class="radio">
                <input type="radio" v-model="form.language" value="auto" />
                <span>{{ lang === 'ar' ? 'تلقائي' : 'Auto-detect' }}</span>
              </label>
              <label class="radio">
                <input type="radio" v-model="form.language" value="ar" />
                <span>{{ lang === 'ar' ? 'عربي' : 'Arabic' }}</span>
              </label>
              <label class="radio">
                <input type="radio" v-model="form.language" value="en" />
                <span>{{ lang === 'ar' ? 'إنجليزي' : 'English' }}</span>
              </label>
            </div>
          </div>

          <div class="field-row">
            <div class="field">
              <label>{{ lang === 'ar' ? 'من تاريخ' : 'Date from' }}</label>
              <input type="date" v-model="form.dateFrom" />
            </div>
            <div class="field">
              <label>{{ lang === 'ar' ? 'إلى تاريخ' : 'Date to' }}</label>
              <input type="date" v-model="form.dateTo" />
            </div>
          </div>

          <div class="field">
            <label>
              {{ lang === 'ar' ? 'حد الإرسالات (اختياري)' : 'Submissions limit (optional)' }}
            </label>
            <input
              type="number"
              min="1"
              v-model.number="form.submissionsLimit"
              :placeholder="lang === 'ar' ? 'مثال: 100 — اتركه فارغاً للجميع' : 'e.g. 100 — leave empty for all'"
            />
            <small class="hint">
              {{ lang === 'ar'
                ? 'يحلل أحدث N إرسال فقط ضمن النطاق الزمني.'
                : 'Analyzes only the most recent N submissions within the date range.' }}
            </small>
          </div>

          <p v-if="formError" class="error-msg">{{ formError }}</p>

          <div class="dialog-actions">
            <button type="button" class="btn btn-secondary" @click="close" :disabled="submitting">
              {{ lang === 'ar' ? 'إلغاء' : 'Cancel' }}
            </button>
            <button type="submit" class="btn btn-primary" :disabled="submitting">
              <span v-if="submitting" class="spinner-sm" />
              {{ submitting
                ? (lang === 'ar' ? 'جاري البدء…' : 'Starting…')
                : (lang === 'ar' ? 'إنشاء التقرير' : 'Generate report') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, type ReportSummary } from '@/api/client'

const props = defineProps<{
  modelValue: boolean
  surveyNumber: string
  lang: 'en' | 'ar'
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()

const router = useRouter()

const reports = ref<ReportSummary[]>([])
const listLoading = ref(false)
const listError = ref(false)
const selectedReportId = ref<number | null>(null)

const form = reactive<{
  language: 'auto' | 'ar' | 'en'
  dateFrom: string
  dateTo: string
  submissionsLimit: number | null
}>({
  language: 'auto',
  dateFrom: '',
  dateTo: '',
  submissionsLimit: null,
})

const submitting = ref(false)
const formError = ref('')

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      form.language = 'auto'
      form.dateFrom = ''
      form.dateTo = ''
      form.submissionsLimit = null
      formError.value = ''
      await fetchReports()
    }
  },
)

async function fetchReports() {
  listLoading.value = true
  listError.value = false
  selectedReportId.value = null
  try {
    const res = await api.analytics.list(props.surveyNumber)
    reports.value = res.data
  } catch {
    listError.value = true
    reports.value = []
  } finally {
    listLoading.value = false
  }
}

function close() {
  if (submitting.value) return
  emit('update:modelValue', false)
}

function openReport(reportId: number) {
  emit('update:modelValue', false)
  router.push({
    name: 'analytics-report',
    params: { number: props.surveyNumber, reportId: String(reportId) },
  })
}

async function submit() {
  if (form.dateFrom && form.dateTo && form.dateFrom > form.dateTo) {
    formError.value =
      props.lang === 'ar'
        ? 'تاريخ البداية يجب أن يكون قبل تاريخ النهاية.'
        : 'Date from must be on or before date to.'
    return
  }
  if (form.submissionsLimit !== null && form.submissionsLimit !== undefined && form.submissionsLimit < 1) {
    formError.value =
      props.lang === 'ar'
        ? 'حد الإرسالات يجب أن يكون أكبر من صفر.'
        : 'Submissions limit must be greater than zero.'
    return
  }

  submitting.value = true
  formError.value = ''
  try {
    const res = await api.analytics.trigger(props.surveyNumber, {
      language: form.language,
      dateFrom: form.dateFrom || undefined,
      dateTo: form.dateTo || undefined,
      submissionsLimit: form.submissionsLimit ?? undefined,
    })
    emit('update:modelValue', false)
    router.push({
      name: 'analytics-report',
      params: { number: props.surveyNumber, reportId: String(res.data.reportId) },
    })
  } catch (e: unknown) {
    const ax = e as { response?: { data?: { detail?: string } }; message?: string }
    formError.value = ax.response?.data?.detail || ax.message || 'Failed to start report'
  } finally {
    submitting.value = false
  }
}

function reportLabel(r: ReportSummary): string {
  const dateRange = r.dateFrom || r.dateTo
    ? `${r.dateFrom || '…'} → ${r.dateTo || '…'}`
    : (props.lang === 'ar' ? 'كل الفترات' : 'All time')
  const statusMap: Record<string, string> = {
    done: props.lang === 'ar' ? 'مكتمل' : 'Done',
    empty: props.lang === 'ar' ? 'فارغ' : 'Empty',
    running: props.lang === 'ar' ? 'جاري…' : 'Generating…',
    pending: props.lang === 'ar' ? 'جاري…' : 'Generating…',
  }
  const statusStr = statusMap[r.status] ?? r.status
  const answers = props.lang === 'ar' ? `${r.answerCount} إجابة` : `${r.answerCount} answers`
  return `[${r.reportLanguage.toUpperCase()}] ${dateRange} · ${answers} · ${statusStr} · ${formatRelative(r.createdAt)}`
}

function formatRelative(iso: string | null): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return props.lang === 'ar' ? 'الآن' : 'just now'
  if (minutes < 60) return props.lang === 'ar' ? `منذ ${minutes}د` : `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return props.lang === 'ar' ? `منذ ${hours}س` : `${hours}h ago`
  const days = Math.floor(hours / 24)
  return props.lang === 'ar' ? `منذ ${days}ي` : `${days}d ago`
}
</script>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 16px;
}

.dialog-card {
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
  width: min(720px, 95vw);
  max-width: 95vw;
}

.dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  background: #fff;
  z-index: 1;
}
.dialog-head h2 { font-size: 1.1rem; margin: 0; color: #1a1a2e; }

.close-btn {
  background: none;
  border: none;
  font-size: 1.6rem;
  line-height: 1;
  color: #6b7280;
  cursor: pointer;
  padding: 0 6px;
}
.close-btn:hover { color: #1a1a2e; }

.dialog-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
}

/* Previous reports */
.list-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #6b7280;
  font-size: 0.9rem;
}

.list-warn {
  font-size: 0.85rem;
  color: #92400e;
  background: #fef3c7;
  padding: 8px 12px;
  border-radius: 8px;
  margin: 0;
}

.prev-section { display: flex; flex-direction: column; gap: 10px; }

.section-label {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6b7280;
  margin: 0;
}

.prev-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.report-select {
  flex: 1;
  padding: 8px 12px;
  border: 1.5px solid #d1d5db;
  border-radius: 8px;
  font-size: 0.88rem;
  background: #fafafa;
  color: #1a1a2e;
  cursor: pointer;
}
.report-select:focus { outline: none; border-color: #4361ee; background: #fff; }

.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #94a3b8;
  font-size: 0.8rem;
}
.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #e2e8f0;
}

/* Form fields */
.field { display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 0.85rem; font-weight: 600; color: #374151; }
.field input[type="date"],
.field input[type="number"] {
  padding: 8px 12px;
  border: 1.5px solid #d1d5db;
  border-radius: 8px;
  font-size: 0.9rem;
  background: #fafafa;
}
.field input:focus { outline: none; border-color: #4361ee; background: #fff; }

.field-row { display: flex; gap: 12px; }
.field-row .field { flex: 1; }

.radio-row { display: flex; gap: 16px; flex-wrap: wrap; }
.radio { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 0.9rem; color: #374151; }
.radio input { margin: 0; }

.hint { color: #6b7280; font-size: 0.78rem; }

.error-msg {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 0.85rem;
  margin: 0;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 4px;
}
[dir="rtl"] .dialog-actions { justify-content: flex-start; }

/* Shared button styles (these mirror globals already in the app) */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn:disabled { opacity: 0.55; cursor: default; }
.btn-primary { background: #4361ee; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #3451d1; }
.btn-secondary { background: #f1f5f9; color: #1a1a2e; border: 1.5px solid #e2e8f0; }
.btn-secondary:hover:not(:disabled) { background: #e2e8f0; }

.spinner-sm {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  vertical-align: middle;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>

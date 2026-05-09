<template>
  <div class="report-shell" :dir="lang === 'ar' ? 'rtl' : 'ltr'">
    <header class="report-toolbar">
      <button class="btn btn-secondary back-btn" @click="goBack">
        {{ lang === 'ar' ? '→ رجوع' : '← Back' }}
      </button>
      <div class="toolbar-title">
        <span class="survey-number">{{ surveyNumber }}</span>
        <span class="title-sep">·</span>
        <span>{{ lang === 'ar' ? 'تقرير تنفيذي' : 'Executive Report' }}</span>
      </div>
      <div class="spacer" />
      <div class="report-actions">
        <button v-if="status === 'done'" class="btn btn-secondary" @click="printReport">
          {{ lang === 'ar' ? '🖨️ طباعة / PDF' : '🖨️ Print / PDF' }}
        </button>
      </div>
    </header>

    <div class="workspace-body">
      <!-- Left column: report -->
      <main class="left-column">
        <p v-if="loading" class="center-msg">
          <span class="spinner" />
          {{ lang === 'ar' ? 'جاري التحميل…' : 'Loading…' }}
        </p>

        <ReportProgress
          v-else-if="status === 'pending' || status === 'running'"
          :steps="steps"
          :trimmed-notice="trimmedNotice"
          :language="lang"
        />

        <section v-else-if="status === 'failed'" class="state-card state-error">
          <h2>{{ lang === 'ar' ? '⚠️ فشل إنشاء التقرير' : '⚠️ Report failed' }}</h2>
          <p>{{ errorMessage }}</p>
          <button class="btn btn-primary" @click="goBack">
            {{ lang === 'ar' ? 'العودة' : 'Back' }}
          </button>
        </section>

        <section v-else-if="status === 'empty'" class="state-card state-empty">
          <h2>{{ lang === 'ar' ? '📭 لا توجد بيانات كافية' : '📭 Not enough data' }}</h2>
          <p>{{ emptyMessage }}</p>
          <button class="btn btn-secondary" @click="goBack">
            {{ lang === 'ar' ? 'العودة' : 'Back' }}
          </button>
        </section>

        <template v-else-if="status === 'done' && payload">
          <section class="cover-card">
            <div class="cover-row">
              <h1 class="cover-title">
                {{ lang === 'ar' ? 'تقرير تحليلات الاستبيان' : 'Survey Analytics Report' }}
              </h1>
              <span class="lang-pill">{{ lang === 'ar' ? 'عربي' : 'English' }}</span>
            </div>
            <div class="cover-meta">
              <span class="meta-pill">
                <strong>{{ lang === 'ar' ? 'الاستبيان' : 'Survey' }}:</strong> {{ surveyNumber }}
              </span>
              <span v-if="payload.date_from || payload.date_to" class="meta-pill">
                <strong>{{ lang === 'ar' ? 'النطاق' : 'Range' }}:</strong>
                {{ payload.date_from || '…' }} → {{ payload.date_to || '…' }}
              </span>
              <span v-if="payload.submissions_limit" class="meta-pill meta-pill-accent">
                <strong>{{ lang === 'ar' ? 'حد الإرسالات' : 'Submissions limit' }}:</strong>
                {{ payload.submissions_limit }}
              </span>
              <span class="meta-pill">
                <strong>{{ lang === 'ar' ? 'تم في' : 'Generated' }}:</strong>
                {{ formatDate(payload.generated_at) }}
              </span>
              <span v-if="durationMs" class="meta-pill">
                <strong>{{ lang === 'ar' ? 'المدة' : 'Duration' }}:</strong>
                {{ formatDuration(durationMs) }}
              </span>
              <span v-if="llmCalls" class="meta-pill">
                <strong>{{ lang === 'ar' ? 'استدعاءات النموذج' : 'LLM calls' }}:</strong>
                {{ llmCalls }}
              </span>
            </div>
          </section>

          <ExecutiveSummaryCard
            :text="payload.synthesis.executive_summary"
            :language="lang"
          />

          <KeyMetricsStrip
            v-if="payload.synthesis.key_metrics.length"
            :metrics="payload.synthesis.key_metrics"
            :language="lang"
          />

          <section class="detailed-card">
            <h2 class="section-title">
              <span class="title-bar" />
              {{ lang === 'ar' ? 'التحليل التفصيلي' : 'Detailed Analysis' }}
            </h2>
            <p class="detailed-text">{{ payload.synthesis.detailed_analysis }}</p>
          </section>

          <RecommendationsList
            v-if="payload.synthesis.recommendations.length"
            :items="payload.synthesis.recommendations"
            :language="lang"
          />

          <section v-if="payload.nlp.length || payload.sql.length" class="question-section">
            <h2 class="section-title">
              <span class="title-bar" />
              {{ lang === 'ar' ? 'تفاصيل الأسئلة' : 'Per-Question Deep Dive' }}
            </h2>
            <div class="questions-stack">
              <QuestionSqlCard
                v-for="q in payload.sql"
                :key="`sql-${q.question_id}`"
                :q="q"
                :language="lang"
              />
              <QuestionNlpCard
                v-for="q in payload.nlp"
                :key="`nlp-${q.question_id}`"
                :q="q"
                :language="lang"
              />
            </div>
          </section>

          <footer class="footer-card">
            <div class="counters">
              <div v-for="(v, k) in payload.counters" :key="k" class="counter">
                <span class="counter-label">{{ k }}</span>
                <span class="counter-value">{{ v }}</span>
              </div>
            </div>
            <p class="footer-note">
              {{ lang === 'ar' ? 'تم إنشاؤه في' : 'Generated at' }}
              {{ formatDate(payload.generated_at) }}
            </p>
          </footer>
        </template>
      </main>

      <!-- Chat panel (40% width when open) -->
      <Transition name="chat-fade">
        <aside v-if="chatOpen" class="chat-panel-column no-print">
          <button class="chat-close-inline" @click="chatOpen = false">×</button>
          <ChatPanel :survey-number="surveyNumber" :language="lang" :report-context="payload" />
        </aside>
      </Transition>

      <!-- Floating chat toggle button -->
      <Transition name="fab-fade">
        <button v-if="!chatOpen" class="chat-fab no-print" @click="chatOpen = true">
          🤖
        </button>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type ReportPayload, type ReportStatus } from '@/api/client'
import ReportProgress from '@/components/analytics/ReportProgress.vue'
import ExecutiveSummaryCard from '@/components/analytics/ExecutiveSummaryCard.vue'
import KeyMetricsStrip from '@/components/analytics/KeyMetricsStrip.vue'
import RecommendationsList from '@/components/analytics/RecommendationsList.vue'
import QuestionNlpCard from '@/components/analytics/QuestionNlpCard.vue'
import QuestionSqlCard from '@/components/analytics/QuestionSqlCard.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import type { ProgressStep, StepStatus } from '@/components/analytics/progressTypes'
import '@/components/analytics/PrintStyles.css'

const route = useRoute()
const router = useRouter()

const surveyNumber = String(route.params.number)
const reportId = Number(route.params.reportId)

const loading = ref(true)
const status = ref<ReportStatus | null>(null)
const payload = ref<ReportPayload | null>(null)
const errorMessage = ref('')
const emptyMessage = ref('')
const lang = ref<'en' | 'ar'>('en')
const durationMs = ref<number | null>(null)
const llmCalls = ref<number | null>(null)
const trimmedNotice = ref(false)
const chatOpen = ref(false)

const stepState = reactive<Record<string, { status: StepStatus; detail: string; progress: number | null }>>({
  sql: { status: 'pending', detail: '', progress: null },
  analysis: { status: 'pending', detail: '', progress: null },
  clustering: { status: 'pending', detail: '', progress: null },
  summarization: { status: 'pending', detail: '', progress: null },
  synthesis: { status: 'pending', detail: '', progress: null },
})

const nlpQuestionIds = ref<number[]>([])
const sqlQuestionIds = ref<number[]>([])
const analysisDone = ref(new Set<number>())
const clusteringDone = ref(new Set<number>())
const summarizationDone = ref(new Set<number>())
const sqlDone = ref(new Set<number>())
const analysisBatchProgress = reactive<Record<number, { completed: number; total: number }>>({})

const steps = computed<ProgressStep[]>(() =>
  ['sql', 'analysis', 'clustering', 'summarization', 'synthesis'].map((k) => ({
    key: k,
    status: stepState[k].status,
    detail: stepState[k].detail,
    progress: stepState[k].progress,
  })),
)

let abortController: AbortController | null = null

async function loadStatus() {
  loading.value = true
  try {
    const res = await api.analytics.status(surveyNumber, reportId)
    status.value = res.data.status
    lang.value = res.data.reportLanguage
    durationMs.value = res.data.durationMs
    llmCalls.value = res.data.llmCalls

    if (res.data.status === 'done') {
      payload.value = res.data.payload ?? null
    } else if (res.data.status === 'empty') {
      const m = res.data.message
      emptyMessage.value = m ? (lang.value === 'ar' ? m.ar : m.en) : ''
    } else if (res.data.status === 'failed') {
      errorMessage.value = res.data.error || 'Report failed'
    } else {
      openStream()
    }
  } catch (e: unknown) {
    status.value = 'failed'
    errorMessage.value = (e as Error).message || 'Failed to load report'
  } finally {
    loading.value = false
  }
}

function setStepStatus(key: string, s: StepStatus) {
  if (stepState[key]) stepState[key].status = s
}
function setStepDetail(key: string, detail: string) {
  if (stepState[key]) stepState[key].detail = detail
}
function setStepProgress(key: string, p: number | null) {
  if (stepState[key]) stepState[key].progress = p
}

function rollupAnalysis() {
  const total = nlpQuestionIds.value.length
  if (!total) return
  const done = analysisDone.value.size
  const sumCompleted = Object.values(analysisBatchProgress).reduce((s, x) => s + x.completed, 0)
  const sumTotal = Object.values(analysisBatchProgress).reduce((s, x) => s + x.total, 0)
  const ratio = sumTotal > 0 ? Math.round((sumCompleted / sumTotal) * 100) : (done === total ? 100 : 0)
  setStepProgress('analysis', ratio)
  setStepDetail('analysis', lang.value === 'ar'
    ? `${done} / ${total} أسئلة`
    : `${done} / ${total} questions`)
  if (done >= total) setStepStatus('analysis', 'done')
  else setStepStatus('analysis', 'active')
}

function rollupClustering() {
  const total = nlpQuestionIds.value.length
  if (!total) return
  const done = clusteringDone.value.size
  setStepDetail('clustering', lang.value === 'ar'
    ? `${done} / ${total} أسئلة`
    : `${done} / ${total} questions`)
  setStepProgress('clustering', Math.round((done / total) * 100))
  if (done >= total) setStepStatus('clustering', 'done')
  else if (done > 0) setStepStatus('clustering', 'active')
}

function rollupSummarization() {
  const total = nlpQuestionIds.value.length
  if (!total) return
  const done = summarizationDone.value.size
  setStepDetail('summarization', lang.value === 'ar'
    ? `${done} / ${total} أسئلة`
    : `${done} / ${total} questions`)
  setStepProgress('summarization', Math.round((done / total) * 100))
  if (done >= total) setStepStatus('summarization', 'done')
  else if (done > 0) setStepStatus('summarization', 'active')
}

function rollupSql() {
  const total = sqlQuestionIds.value.length
  if (!total) return
  const done = sqlDone.value.size
  setStepDetail('sql', lang.value === 'ar'
    ? `${done} / ${total} أسئلة`
    : `${done} / ${total} questions`)
  setStepProgress('sql', Math.round((done / total) * 100))
  if (done >= total) setStepStatus('sql', 'done')
  else setStepStatus('sql', 'active')
}

function handleEvent(event: string, dataStr: string) {
  let data: Record<string, unknown> = {}
  try { data = JSON.parse(dataStr) } catch { /* ignore */ }

  switch (event) {
    case 'nlp_branch_started': {
      const qs = (data.questions as number[]) ?? []
      nlpQuestionIds.value = qs
      if (qs.length) {
        setStepStatus('analysis', 'active')
      } else {
        setStepStatus('analysis', 'done')
        setStepStatus('clustering', 'done')
        setStepStatus('summarization', 'done')
      }
      rollupAnalysis(); rollupClustering(); rollupSummarization()
      break
    }
    case 'sql_branch_started': {
      const qs = (data.questions as number[]) ?? []
      sqlQuestionIds.value = qs
      if (qs.length) setStepStatus('sql', 'active')
      else setStepStatus('sql', 'done')
      rollupSql()
      break
    }
    case 'sql_question_done': {
      const qid = data.questionId as number
      if (typeof qid === 'number') sqlDone.value.add(qid)
      rollupSql()
      break
    }
    case 'sql_branch_done': {
      setStepStatus('sql', 'done')
      const total = sqlQuestionIds.value.length
      if (total) {
        setStepDetail('sql', lang.value === 'ar'
          ? `${total} / ${total} أسئلة`
          : `${total} / ${total} questions`)
        setStepProgress('sql', 100)
      }
      break
    }
    case 'analysis_progress': {
      const qid = data.questionId as number
      const completed = (data.completedBatches as number) ?? 0
      const total = (data.totalBatches as number) ?? 1
      if (typeof qid === 'number') {
        analysisBatchProgress[qid] = { completed, total }
      }
      rollupAnalysis()
      break
    }
    case 'analysis_done': {
      const qid = data.questionId as number
      if (typeof qid === 'number') {
        analysisDone.value.add(qid)
        const bp = analysisBatchProgress[qid]
        if (bp) bp.completed = bp.total
      }
      rollupAnalysis()
      break
    }
    case 'clustering_done': {
      const qid = data.questionId as number
      if (typeof qid === 'number') clusteringDone.value.add(qid)
      rollupClustering()
      break
    }
    case 'aggregation_done': {
      break
    }
    case 'summarization_done': {
      const qid = data.questionId as number
      if (typeof qid === 'number') summarizationDone.value.add(qid)
      rollupSummarization()
      break
    }
    case 'nlp_branch_done': {
      setStepStatus('analysis', 'done')
      setStepStatus('clustering', 'done')
      setStepStatus('summarization', 'done')
      break
    }
    case 'synthesis_done': {
      setStepStatus('synthesis', 'done')
      setStepProgress('synthesis', 100)
      if (data.trimmed) trimmedNotice.value = true
      break
    }
    case 'done': {
      const finalStatus = (data.status as ReportStatus) ?? 'done'
      status.value = finalStatus
      closeStream()
      if (finalStatus === 'done' || finalStatus === 'empty' || finalStatus === 'failed') {
        loadStatus()
      }
      break
    }
    case 'error': {
      errorMessage.value = (data.message as string) || 'unknown error'
      status.value = 'failed'
      closeStream()
      break
    }
  }
  const nlpAllDone = nlpQuestionIds.value.length === 0 || (
    analysisDone.value.size === nlpQuestionIds.value.length
    && clusteringDone.value.size === nlpQuestionIds.value.length
    && summarizationDone.value.size === nlpQuestionIds.value.length
  )
  const sqlAllDone = sqlQuestionIds.value.length === 0 || sqlDone.value.size === nlpQuestionIds.value.length
  if (nlpAllDone && sqlAllDone && stepState.synthesis.status === 'pending') {
    setStepStatus('synthesis', 'active')
  }
}

async function openStream() {
  abortController = new AbortController()
  try {
    const response = await fetch(api.analytics.streamUrl(surveyNumber, reportId), {
      signal: abortController.signal,
    })
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (reader) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''
      for (const part of parts) {
        const lines = part.split('\n')
        let evName = ''
        let dataPart = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) evName = line.slice(7).trim()
          else if (line.startsWith('data: ')) dataPart = line.slice(6)
        }
        if (evName) handleEvent(evName, dataPart)
      }
    }
  } catch (e: unknown) {
    if ((e as Error).name === 'AbortError') return
    errorMessage.value = (e as Error).message || 'stream error'
    status.value = 'failed'
  }
}

function closeStream() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
}

function goBack() {
  router.push({ name: 'survey-list' })
}

function printReport() {
  window.print()
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  try { return new Date(iso).toLocaleString() } catch { return iso }
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  const s = Math.round(ms / 100) / 10
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const r = Math.round(s - m * 60)
  return `${m}m ${r}s`
}

onMounted(loadStatus)
onBeforeUnmount(closeStream)
</script>

<style scoped>
.report-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f4f6fb;
  overflow: hidden;
}

.report-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 24px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  z-index: 10;
}
.toolbar-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.95rem;
  color: #1a1a2e;
  font-weight: 600;
}
.title-sep { color: #cbd5e1; }
.survey-number { color: #4361ee; font-weight: 700; }
.spacer { flex: 1; }
.report-actions { display: flex; gap: 8px; }
.back-btn { padding: 6px 14px; }

/* Full-width body with flex layout */
.workspace-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

/* Report column: 100% when chat closed, 60% when open */
.left-column {
  flex: 1;
  overflow-y: auto;
  padding: 28px 40px;
  display: flex;
  flex-direction: column;
  gap: 22px;
  min-width: 0;
  transition: flex 0.3s ease;
}

/* Chat column: 40% width when open */
.chat-panel-column {
  flex: 0 0 40%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
  border-left: 1px solid #e0e4f0;
  position: relative;
}
[dir="rtl"] .chat-panel-column {
  border-left: none;
  border-right: 1px solid #e0e4f0;
}

.chat-close-inline {
  position: absolute;
  top: 10px;
  right: 8px;
  z-index: 10;
  width: 28px;
  height: 28px;
  border: none;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 50%;
  font-size: 0.9rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
  transition: background 0.15s;
  line-height: 1;
}
[dir="rtl"] .chat-close-inline {
  right: auto;
  left: 8px;
}
.chat-close-inline:hover {
  background: rgba(0, 0, 0, 0.12);
}

/* Shrink session select to make room for close button */
.chat-panel-column :deep(.session-bar) {
  padding-right: 40px;
}
[dir="rtl"] .chat-panel-column :deep(.session-bar) {
  padding-right: 14px;
  padding-left: 40px;
}


/* Floating Action Button */
.chat-fab {
  position: fixed;
  bottom: 28px;
  right: 28px;
  width: 56px;
  height: 56px;
  border: none;
  border-radius: 50%;
  background: #4361ee;
  color: #fff;
  font-size: 1.6rem;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(67, 97, 238, 0.4);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s, box-shadow 0.2s;
}
[dir="rtl"] .chat-fab {
  right: auto;
  left: 28px;
}
.chat-fab:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 24px rgba(67, 97, 238, 0.5);
}

/* Transitions */
.chat-fade-enter-active,
.chat-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.chat-fade-enter-from,
.chat-fade-leave-to {
  opacity: 0;
  transform: translateX(40px);
}
[dir="rtl"] .chat-fade-enter-from,
[dir="rtl"] .chat-fade-leave-to {
  transform: translateX(-40px);
}

.fab-fade-enter-active,
.fab-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.fab-fade-enter-from,
.fab-fade-leave-to {
  opacity: 0;
  transform: scale(0.6);
}

/* Shared */
.center-msg {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
  padding: 80px;
  color: #6b7280;
}
.spinner {
  width: 22px;
  height: 22px;
  border: 3px solid #eef0fa;
  border-top-color: #4361ee;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.cover-card {
  background: linear-gradient(135deg, #4361ee 0%, #7209b7 100%);
  color: #fff;
  border-radius: 14px;
  padding: 30px 36px;
  box-shadow: 0 6px 20px rgba(67, 97, 238, 0.18);
}
.cover-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap; }
.cover-title { margin: 0; font-size: 1.6rem; font-weight: 700; }
.lang-pill {
  background: rgba(255, 255, 255, 0.2);
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.cover-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-top: 16px;
}
.meta-pill {
  background: rgba(255, 255, 255, 0.12);
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 0.78rem;
}
.meta-pill strong { font-weight: 600; opacity: 0.8; margin-right: 4px; }
[dir="rtl"] .meta-pill strong { margin-right: 0; margin-left: 4px; }
.meta-pill-accent {
  background: #fff;
  color: #4361ee;
  font-weight: 600;
}
.meta-pill-accent strong { color: #4361ee; opacity: 1; }

.detailed-card {
  background: #fff;
  border: 1px solid #e0e4f0;
  border-radius: 12px;
  padding: 24px 28px;
  box-shadow: 0 1px 6px rgba(15, 23, 42, 0.04);
}
.section-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 1rem;
  font-weight: 700;
  color: #1a1a2e;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0 0 14px 0;
}
.title-bar { width: 4px; height: 18px; background: #4361ee; border-radius: 2px; }
.detailed-text {
  font-size: 0.98rem;
  line-height: 1.75;
  color: #1a1a2e;
  margin: 0;
  white-space: pre-wrap;
}

.question-section { display: flex; flex-direction: column; gap: 14px; }
.questions-stack { display: flex; flex-direction: column; gap: 14px; }

.footer-card {
  background: #fff;
  border: 1px solid #e0e4f0;
  border-radius: 12px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.counters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.counter {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 4px 10px;
  font-size: 0.78rem;
}
.counter-label { color: #64748b; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 600; }
.counter-value { color: #1a1a2e; font-weight: 700; font-variant-numeric: tabular-nums; }
.footer-note { color: #94a3b8; font-size: 0.78rem; margin: 0; }

.state-card {
  background: #fff;
  border-radius: 14px;
  padding: 32px 36px;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  box-shadow: 0 2px 14px rgba(15, 23, 42, 0.05);
}
.state-card h2 { margin: 0; font-size: 1.2rem; }
.state-card p { margin: 0; color: #475569; font-size: 0.95rem; line-height: 1.6; max-width: 600px; }
.state-error h2 { color: #b91c1c; }
.state-empty h2 { color: #475569; }

/* Buttons (mirror globals) */
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

/* Print: hide chat and dashboard, flatten layout */
@media print {
  .workspace-body { display: block; }
  .left-column { overflow: visible; padding: 0; }
  .no-print { display: none !important; }
}
</style>
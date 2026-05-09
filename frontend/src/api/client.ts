import axios from 'axios'

const client = axios.create({ baseURL: '/api' })
export default client

// External API types (returned via backend proxy at GET /api/surveys)

export interface ExternalSurvey {
  id: number
  subject: string | null
  subjectAr: string | null
  description: string | null
  descriptionAr: string | null
  status: string
  departmentId: string
  sendEmailsTo: string[]
  createBy: string
  createdDate: string
  logo: string | null
  confirmMessage: string | null
  isPublic: boolean
  surveyQuestions: unknown[]
  completionMessage: string | null
  surveyNumber: string
  isLocation: boolean
  cityId: number | null
  answered: boolean
}

export interface SurveyMeta {
  surveyNumber: string
  subject: string | null
  subjectAr: string | null
  status: string
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant' | 'tool'
  content: string
  toolName?: string
  language?: string
  createdAt?: string
}

export interface ChatSession {
  id: number
  createdAt: string
}

// Analytics-report types

export type Sentiment = 'positive' | 'neutral' | 'negative' | 'mixed'

export interface KeyMetric {
  label: string
  value: string
  context: string
}

export interface SynthesisOutput {
  executive_summary: string
  detailed_analysis: string
  key_metrics: KeyMetric[]
  recommendations: string[]
}

export interface TopTopic {
  category: string
  subtopic: string
  count: number
  dominant_sentiment: Sentiment
  sentiment_breakdown: Record<string, number>
}

export interface TopEntity {
  name: string
  type: string
  count: number
}

export interface QuestionNlpResult {
  question_id: number
  question_text: string
  valid_count: number
  sarcastic_count: number
  sentiment_distribution: Record<string, number>
  top_topics: TopTopic[]
  top_entities: TopEntity[]
  narrative_summary: string
  partial: boolean
}

export interface QuestionSqlResult {
  question_id: number
  question_text: string
  type: 'MULTIPLE_CHOICE' | 'YES_NO' | 'DROPDOWN' | 'EMOJIS'
  results: Record<string, unknown>
}

export interface ReportPayload {
  report_language: 'ar' | 'en'
  date_from: string | null
  date_to: string | null
  submissions_limit: number | null
  synthesis: SynthesisOutput
  nlp: QuestionNlpResult[]
  sql: QuestionSqlResult[]
  counters: Record<string, number>
  generated_at: string
}

export type ReportStatus = 'pending' | 'running' | 'done' | 'failed' | 'empty'

export interface ReportStatusResponse {
  reportId: number
  surveyNumber: string
  status: ReportStatus
  reportLanguage: 'ar' | 'en'
  dateFrom: string | null
  dateTo: string | null
  submissionsLimit: number | null
  createdAt: string | null
  durationMs: number | null
  llmCalls: number | null
  payload?: ReportPayload
  message?: { ar: string; en: string }
  error?: string
  streamUrl?: string
}

export interface TriggerReportBody {
  language?: 'auto' | 'ar' | 'en'
  dateFrom?: string
  dateTo?: string
  submissionsLimit?: number
}

export interface TriggerReportResponse {
  reportId: number
  status: ReportStatus
  cached: boolean
  streamUrl: string
  resultUrl: string
}

export interface ReportSummary {
  reportId: number
  surveyNumber: string
  status: ReportStatus
  reportLanguage: 'ar' | 'en'
  dateFrom: string | null
  dateTo: string | null
  submissionsLimit: number | null
  answerCount: number
  llmCalls: number | null
  durationMs: number | null
  createdAt: string | null
}

export const api = {
  surveys: {
    list: () => client.get<ExternalSurvey[]>('/surveys'),
  },
  chat: {
    sessions: (num: string) => client.get<ChatSession[]>(`/surveys/${num}/chat/sessions`),
    history: (num: string, sessionId: number) =>
      client.get<ChatMessage[]>(`/surveys/${num}/chat/history`, { params: { sessionId } }),
  },
  analytics: {
    list: (num: string, limit = 20) =>
      client.get<ReportSummary[]>(`/surveys/${num}/analytics-report`, { params: { limit } }),
    trigger: (num: string, body: TriggerReportBody) =>
      client.post<TriggerReportResponse>(`/surveys/${num}/analytics-report`, body),
    status: (num: string, id: number) =>
      client.get<ReportStatusResponse>(`/surveys/${num}/analytics-report/${id}`),
    streamUrl: (num: string, id: number) =>
      `/api/surveys/${num}/analytics-report/${id}/stream`,
  },
}

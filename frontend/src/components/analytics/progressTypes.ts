export type StepStatus = 'pending' | 'active' | 'done'

export interface ProgressStep {
  key: string
  status: StepStatus
  detail?: string
  progress?: number | null
}

<template>
  <div class="chat-panel" :dir="language === 'ar' ? 'rtl' : 'ltr'">
    <!-- Session selector -->
    <div class="session-bar">
      <select v-model="activeSessionId" class="session-select">
        <option :value="null">{{ language === 'ar' ? '+ محادثة جديدة' : '+ New conversation' }}</option>
        <option v-for="s in sessions" :key="s.id" :value="s.id">
          {{ language === 'ar' ? 'محادثة' : 'Session' }} #{{ s.id }}
          — {{ formatDate(s.createdAt) }}
        </option>
      </select>
    </div>

    <!-- Messages -->
    <div ref="msgContainer" class="messages">
      <div v-if="loadingHistory" class="center"><div class="spinner" /></div>

      <template v-else>
        <div
          v-for="(msg, i) in displayMessages"
          :key="i"
          :class="['msg', msg.role]"
        >
          <div class="bubble">
            <template v-if="msg.role === 'tool'">
              <span class="tool-label">🔧 {{ msg.toolName }}</span>
              <pre class="tool-content">{{ tryFormat(msg.content) }}</pre>
            </template>
            <span v-else>{{ msg.content }}</span>
          </div>
        </div>

        <!-- Streaming in-progress -->
        <div v-if="streaming" class="msg assistant">
          <div class="bubble">
            <span v-if="streamBuffer">{{ streamBuffer }}</span>
            <span v-else-if="thinking" class="thinking-indicator">
              {{ language === 'ar' ? 'يفكر…' : 'Thinking…' }}
            </span>
            <span class="cursor" />
          </div>
        </div>

        <!-- Tool-call events while streaming -->
        <div v-for="(tc, i) in pendingToolCalls" :key="'tc' + i" class="msg tool">
          <div class="bubble">
            <span class="tool-label">🔧 {{ tc.name }}</span>
            <pre class="tool-content">{{ JSON.stringify(tc.args, null, 2) }}</pre>
          </div>
        </div>
      </template>
    </div>

    <!-- Input -->
    <form class="input-row" @submit.prevent="send">
      <textarea
        v-model="userInput"
        :placeholder="language === 'ar' ? 'اكتب سؤالك هنا…' : 'Ask a question about this survey…'"
        rows="2"
        @keydown.enter.exact.prevent="send"
      />
      <button class="btn btn-primary send-btn" type="submit" :disabled="streaming || !userInput.trim()">
        {{ language === 'ar' ? 'إرسال' : 'Send' }}
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { api, type ChatMessage, type ChatSession } from '@/api/client'

const props = defineProps<{
  surveyNumber: string
  language: 'en' | 'ar'
  reportContext?: Record<string, unknown> | null
}>()

const sessions = ref<ChatSession[]>([])
const activeSessionId = ref<number | null>(null)
const displayMessages = ref<(ChatMessage & { toolName?: string })[]>([])
const loadingHistory = ref(false)

const userInput = ref('')
const streaming = ref(false)
const thinking = ref(false)
const streamBuffer = ref('')
const pendingToolCalls = ref<Array<{ name: string; args: unknown }>>([])

const msgContainer = ref<HTMLElement | null>(null)

function scrollBottom() {
  nextTick(() => {
    if (msgContainer.value) {
      msgContainer.value.scrollTop = msgContainer.value.scrollHeight
    }
  })
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

function tryFormat(json: string): string {
  try { return JSON.stringify(JSON.parse(json), null, 2) } catch { return json }
}

async function loadSessions() {
  try {
    const res = await api.chat.sessions(props.surveyNumber)
    sessions.value = res.data
  } catch { /* ignore */ }
}

async function loadHistory(sessionId: number) {
  loadingHistory.value = true
  try {
    const res = await api.chat.history(props.surveyNumber, sessionId)
    displayMessages.value = res.data as (ChatMessage & { toolName?: string })[]
  } catch { /* ignore */ } finally {
    loadingHistory.value = false
    scrollBottom()
  }
}

const WELCOME_EN = "Hello, I'm your AI survey agent. How can I help you"
const WELCOME_AR = "مرحبًا، أنا مساعدك الذكي للاستبيانات. كيف يمكنني مساعدتك؟"

function showWelcome() {
  displayMessages.value = [{
    id: 0,
    role: 'assistant',
    content: props.language === 'ar' ? WELCOME_AR : WELCOME_EN,
  }]
  scrollBottom()
}

watch(activeSessionId, (sid) => {
  displayMessages.value = []
  if (sid) {
    loadHistory(sid)
  } else {
    showWelcome()
  }
})

onMounted(() => {
  loadSessions()
  showWelcome()
})

async function send() {
  const msg = userInput.value.trim()
  if (!msg || streaming.value) return
  userInput.value = ''

  displayMessages.value.push({ id: 0, role: 'user', content: msg })
  scrollBottom()

  streaming.value = true
  thinking.value = false
  streamBuffer.value = ''
  pendingToolCalls.value = []

  const body = JSON.stringify({
    message: msg,
    sessionId: activeSessionId.value,
    reportContext: props.reportContext ?? undefined,
  })

  try {
    const response = await fetch(`/api/surveys/${props.surveyNumber}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
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
        let eventName = ''
        let dataPart = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) eventName = line.slice(7).trim()
          if (line.startsWith('data: ')) dataPart = line.slice(6)
        }

        if (eventName === 'token') {
          try { streamBuffer.value += JSON.parse(dataPart) } catch { streamBuffer.value += dataPart }
          thinking.value = false
          scrollBottom()
        } else if (eventName === 'heartbeat') {
          thinking.value = true
        } else if (eventName === 'tool_call') {
          try {
            const parsed = JSON.parse(dataPart)
            pendingToolCalls.value.push(parsed)
          } catch { /* ignore */ }
        } else if (eventName === 'tool_result') {
          try {
            const parsed = JSON.parse(dataPart)
            displayMessages.value.push({
              id: 0,
              role: 'tool',
              content: parsed.result ?? dataPart,
              toolName: parsed.name,
            })
            pendingToolCalls.value = pendingToolCalls.value.filter(
              (tc) => tc.name !== parsed.name
            )
          } catch { /* ignore */ }
        } else if (eventName === 'done') {
          thinking.value = false
          if (streamBuffer.value) {
            displayMessages.value.push({ id: 0, role: 'assistant', content: streamBuffer.value })
            streamBuffer.value = ''
          }
          const newSessionId = parseInt(dataPart)
          if (!isNaN(newSessionId) && newSessionId !== activeSessionId.value) {
            activeSessionId.value = newSessionId
            await loadSessions()
          }
        } else if (eventName === 'error') {
          displayMessages.value.push({ id: 0, role: 'assistant', content: `⚠️ ${dataPart}` })
        }
      }
    }
  } catch (err) {
    displayMessages.value.push({ id: 0, role: 'assistant', content: `⚠️ Connection error` })
  } finally {
    if (streamBuffer.value) {
      displayMessages.value.push({ id: 0, role: 'assistant', content: streamBuffer.value })
      streamBuffer.value = ''
    }
    streaming.value = false
    thinking.value = false
    scrollBottom()
  }
}



</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.07);
  overflow: hidden;
}

.session-bar {
  padding: 10px 14px;
  border-bottom: 1px solid #e0e4f0;
  background: #f8f9ff;
}
.session-select {
  width: 100%;
  padding: 6px 10px;
  border: 1.5px solid #ddd;
  border-radius: 8px;
  font-size: 0.875rem;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.msg.assistant, .msg.tool { justify-content: flex-start; }

.bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 0.9rem;
  line-height: 1.5;
  word-break: break-word;
}

.msg.user .bubble {
  background: #4361ee;
  color: #fff;
  border-bottom-right-radius: 4px;
}
[dir="rtl"] .msg.user .bubble { border-bottom-right-radius: 14px; border-bottom-left-radius: 4px; }

.msg.assistant .bubble {
  background: #f0f2ff;
  color: #1a1a2e;
  border-bottom-left-radius: 4px;
}
[dir="rtl"] .msg.assistant .bubble { border-bottom-left-radius: 14px; border-bottom-right-radius: 4px; }

.msg.tool .bubble {
  background: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: 8px;
  max-width: 90%;
  font-size: 0.8rem;
}

.tool-label {
  display: block;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 4px;
  font-size: 0.78rem;
}

.tool-content {
  margin: 0;
  white-space: pre-wrap;
  font-family: monospace;
  font-size: 0.75rem;
  color: #555;
  max-height: 120px;
  overflow-y: auto;
}

.cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: #4361ee;
  margin-left: 2px;
  vertical-align: middle;
  animation: blink 0.9s step-end infinite;
}
@keyframes blink { 50% { opacity: 0; } }

.thinking-indicator {
  color: #888;
  font-style: italic;
  font-size: 0.85rem;
}
.thinking-indicator::after {
  content: '';
  animation: dots 1.5s steps(4, end) infinite;
}
@keyframes dots {
  0%   { content: ''; }
  25%  { content: '.'; }
  50%  { content: '..'; }
  75%  { content: '...'; }
}

.input-row {
  display: flex;
  gap: 8px;
  padding: 12px 14px;
  border-top: 1px solid #e0e4f0;
  background: #f8f9ff;
}

textarea {
  flex: 1;
  padding: 8px 12px;
  border: 1.5px solid #ddd;
  border-radius: 8px;
  font-size: 0.9rem;
  resize: none;
  font-family: inherit;
  transition: border-color 0.2s;
}
textarea:focus { outline: none; border-color: #4361ee; }

.send-btn { align-self: flex-end; padding: 8px 18px; }

.center { display: flex; justify-content: center; padding: 40px; }
</style>

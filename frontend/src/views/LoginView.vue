<template>
  <div class="login-page">
    <div class="card login-card">
      <h1>Survey AI</h1>
      <p class="subtitle">Paste your ms-survey-service JWT token to continue</p>

      <form @submit.prevent="submit">
        <label for="token-input">JWT Token</label>
        <textarea
          id="token-input"
          v-model="tokenInput"
          rows="4"
          placeholder="eyJhbGciOiJIUzI1NiJ9..."
          required
        />
        <p v-if="error" class="error-msg">{{ error }}</p>
        <button class="btn btn-primary" type="submit" :disabled="loading">
          <span v-if="loading" class="spinner" style="width:16px;height:16px;border-width:2px" />
          Sign In
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/client'

const router = useRouter()
const auth = useAuthStore()

const tokenInput = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    auth.setToken(tokenInput.value.trim())
    await api.me() // verify token works
    router.push({ name: 'survey-list' })
  } catch {
    auth.logout()
    error.value = 'Invalid or expired token. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #4361ee 0%, #3a0ca3 100%);
}

.login-card {
  width: 100%;
  max-width: 440px;
  padding: 40px;
}

h1 {
  font-size: 1.8rem;
  font-weight: 700;
  margin-bottom: 8px;
  color: #4361ee;
}

.subtitle {
  color: #666;
  font-size: 0.9rem;
  margin-bottom: 24px;
}

label {
  display: block;
  font-size: 0.85rem;
  font-weight: 600;
  margin-bottom: 6px;
  color: #333;
}

textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1.5px solid #ddd;
  border-radius: 8px;
  font-family: monospace;
  font-size: 0.8rem;
  resize: vertical;
  margin-bottom: 12px;
  transition: border-color 0.2s;
}
textarea:focus {
  outline: none;
  border-color: #4361ee;
}

.btn { width: 100%; justify-content: center; margin-top: 4px; }
</style>

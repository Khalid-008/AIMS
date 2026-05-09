import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const language = ref<'en' | 'ar'>('en')

  function setLanguage(lang: 'en' | 'ar') {
    language.value = lang
  }

  return { language, setLanguage }
})

<template>
  <div class="lang-toggle">
    <button
      :class="['lang-btn', modelValue === 'en' && 'active']"
      @click="$emit('update:modelValue', 'en')"
    >EN</button>
    <button
      :class="['lang-btn', modelValue === 'ar' && 'active']"
      @click="$emit('update:modelValue', 'ar')"
    >AR</button>
  </div>
</template>

<script setup lang="ts">
defineProps<{ modelValue: 'en' | 'ar' }>()
defineEmits<{ (e: 'update:modelValue', v: 'en' | 'ar'): void }>()
</script>

<style scoped>
.lang-toggle {
  display: flex;
  border: 1.5px solid #ddd;
  border-radius: 8px;
  overflow: hidden;
}
.lang-btn {
  padding: 5px 12px;
  border: none;
  background: transparent;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  color: #888;
  transition: background 0.15s, color 0.15s;
}
.lang-btn.active { background: #4361ee; color: #fff; }
</style>

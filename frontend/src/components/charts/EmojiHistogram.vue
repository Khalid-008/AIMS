<template>
  <div class="emoji-hist">
    <div v-for="item in sorted" :key="item.emoji" class="emoji-row">
      <span class="emoji">{{ item.emoji }}</span>
      <div class="bar-track">
        <div class="bar-fill" :style="{ width: item.percent + '%' }" />
      </div>
      <span class="count">{{ item.count }} ({{ item.percent }}%)</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface EmojiItem { emoji: string; count: number; percent: number }

const props = defineProps<{ data: EmojiItem[] }>()

const sorted = computed(() =>
  [...props.data].sort((a, b) => b.count - a.count)
)
</script>

<style scoped>
.emoji-hist { display: flex; flex-direction: column; gap: 10px; }
.emoji-row { display: flex; align-items: center; gap: 10px; }
.emoji { font-size: 1.5rem; width: 2rem; text-align: center; }
.bar-track { flex: 1; height: 18px; background: #e0e4f0; border-radius: 9px; overflow: hidden; }
.bar-fill { height: 100%; background: linear-gradient(90deg, #4361ee, #7209b7); border-radius: 9px; transition: width 0.4s ease; }
.count { font-size: 0.8rem; color: #555; white-space: nowrap; min-width: 80px; }
</style>

<template>
  <div v-if="urls.length === 0" class="empty">
    {{ language === 'ar' ? 'لا توجد ملفات' : 'No files uploaded' }}
  </div>
  <div v-else class="gallery">
    <a
      v-for="(url, i) in urls"
      :key="i"
      :href="url"
      target="_blank"
      rel="noopener noreferrer"
      class="file-thumb"
    >
      <img v-if="isImage(url)" :src="url" :alt="`file-${i}`" class="thumb-img" />
      <div v-else class="file-icon">
        <span>📎</span>
        <span class="file-name">{{ fileName(url) }}</span>
      </div>
    </a>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ urls: string[]; language?: 'en' | 'ar' }>()

function isImage(url: string): boolean {
  return /\.(png|jpg|jpeg|gif|webp|svg)$/i.test(url)
}

function fileName(url: string): string {
  return url.split('/').pop() ?? url
}
</script>

<style scoped>
.gallery { display: flex; flex-wrap: wrap; gap: 10px; }
.file-thumb {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 90px;
  height: 90px;
  border-radius: 8px;
  overflow: hidden;
  border: 1.5px solid #e0e4f0;
  transition: border-color 0.15s;
  text-decoration: none;
}
.file-thumb:hover { border-color: #4361ee; }
.thumb-img { width: 100%; height: 100%; object-fit: cover; }
.file-icon { display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 0.7rem; color: #555; padding: 6px; text-align: center; }
.file-icon span:first-child { font-size: 1.8rem; }
.file-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 80px; }
.empty { color: #aaa; font-size: 0.875rem; }
</style>

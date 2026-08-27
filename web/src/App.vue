<template>
  <div class="app">
    <AppHeader v-if="!bare" :title="title" :back="back" />
    <main :class="bare ? '' : 'app-main'">
      <router-view v-slot="{ Component, route }">
        <component :is="Component" :key="route.fullPath" />
      </router-view>
    </main>
    <BottomNav v-if="!bare" :active="nav" />
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import BottomNav from './components/BottomNav.vue'
import { useAuthStore } from './store/auth'
import { useSessionStore } from './store/session'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const session = useSessionStore()

const bare = computed(() => !!route.meta.bare)
const title = computed(() => route.meta.title || 'SOULHEALTH')
const back = computed(() => route.meta.back || '')
const nav = computed(() => route.meta.nav || '')

onMounted(async () => {
  window.addEventListener('sh:unauthorized', () => {
    auth.logout()
    router.replace('/login')
  })
  session.loadHealth()
  if (auth.isLoggedIn) {
    await auth.fetchMe()
    await session.ensureProfile()
  }
})
</script>

<style>
.app { min-height: 100%; display: flex; flex-direction: column; }
.app-main { flex: 1; padding-top: var(--header-h); }
.page-enter-active, .page-leave-active { transition: opacity .18s ease, transform .18s ease; }
.page-enter-from { opacity: 0; transform: translateY(8px); }
.page-leave-to { opacity: 0; transform: translateY(-4px); }
</style>

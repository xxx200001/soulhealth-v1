import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/theme.css'

const app = createApp(App)

app.config.errorHandler = (err, vm, info) => {
  console.warn('[Vue Error Handler]:', err, info)
}

window.addEventListener('unhandledrejection', (event) => {
  console.warn('[Unhandled Promise Rejection]:', event.reason)
})

app.use(createPinia()).use(router).mount('#app')

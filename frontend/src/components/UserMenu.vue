<template>
  <div v-if="show" class="user-menu">
    <span class="user-email" :title="label">{{ label }}</span>
    <button type="button" class="logout" @click="onLogout">{{ $t('auth.logout') }}</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { AUTH_REQUIRED, authState, isAuthenticated, signOut } from '../store/auth'

const router = useRouter()
const show = computed(() => AUTH_REQUIRED && isAuthenticated.value)
const label = computed(() => authState.user?.name || authState.user?.email || '')

async function onLogout() {
  await signOut()
  await router.replace({ name: 'Auth' })
}
</script>

<style scoped>
.user-menu {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
}

.user-email {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--ink-soft);
}

.logout {
  padding: 4px 12px;
  border: 1px solid var(--glass-line-strong);
  border-radius: 8px;
  background: transparent;
  color: var(--ink);
  font: inherit;
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s;
}

.logout:hover,
.logout:focus-visible {
  color: var(--bio-teal);
  border-color: var(--bio-teal);
  outline: none;
}
</style>

<template>
  <main class="auth-shell">
    <section class="auth-card" aria-labelledby="auth-title">
      <div class="auth-brand"><span class="brand-orb"></span>NOMA</div>

      <div class="auth-tabs" role="tablist">
        <button
          v-for="m in ['login', 'register']"
          :key="m"
          type="button"
          role="tab"
          class="auth-tab"
          :class="{ active: mode === m }"
          :aria-selected="mode === m"
          @click="setMode(m)"
        >
          {{ $t(`auth.tabs.${m}`) }}
        </button>
      </div>

      <h1 id="auth-title" class="auth-title">{{ $t(`auth.title.${mode}`) }}</h1>
      <p class="auth-subtitle">{{ $t(`auth.subtitle.${mode}`) }}</p>

      <form class="auth-form" novalidate @submit.prevent="onSubmit">
        <label v-if="mode === 'register'" class="field">
          <span>{{ $t('auth.fields.name') }}</span>
          <input v-model="form.name" type="text" name="name" autocomplete="name" maxlength="120" />
        </label>

        <label class="field" :class="{ invalid: errors.email }">
          <span>{{ $t('auth.fields.email') }}</span>
          <input
            v-model="form.email"
            type="email"
            name="email"
            inputmode="email"
            autocomplete="email"
            autocapitalize="none"
            spellcheck="false"
            :aria-invalid="!!errors.email"
            aria-describedby="err-email"
          />
          <small v-if="errors.email" id="err-email" class="field-error">{{ fieldError('email') }}</small>
        </label>

        <label class="field" :class="{ invalid: errors.password }">
          <span>{{ $t('auth.fields.password') }}</span>
          <input
            v-model="form.password"
            type="password"
            name="password"
            :autocomplete="mode === 'register' ? 'new-password' : 'current-password'"
            :aria-invalid="!!errors.password"
            aria-describedby="err-password"
          />
          <small v-if="errors.password" id="err-password" class="field-error">{{ fieldError('password') }}</small>
        </label>

        <label v-if="mode === 'register'" class="field" :class="{ invalid: errors.confirm }">
          <span>{{ $t('auth.fields.confirm') }}</span>
          <input
            v-model="form.confirm"
            type="password"
            name="confirm"
            autocomplete="new-password"
            :aria-invalid="!!errors.confirm"
            aria-describedby="err-confirm"
          />
          <small v-if="errors.confirm" id="err-confirm" class="field-error">{{ fieldError('confirm') }}</small>
        </label>

        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>

        <button class="submit" type="submit" :disabled="loading">
          {{ loading ? $t('auth.loading') : $t(`auth.submit.${mode}`) }}
        </button>
      </form>

      <button type="button" class="switch" @click="setMode(mode === 'login' ? 'register' : 'login')">
        {{ mode === 'login' ? $t('auth.switch.toRegister') : $t('auth.switch.toLogin') }}
      </button>

      <div class="auth-lang"><LanguageSwitcher /></div>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { signIn, signUp } from '../store/auth'
import { authErrorKey, safeRedirect, validateAuthForm } from '../lib/authRules'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const mode = ref(route.query.mode === 'register' ? 'register' : 'login')
const form = reactive({ name: '', email: '', password: '', confirm: '' })
const errors = ref({})
const formError = ref('')
const loading = ref(false)

const fieldError = (field) => {
  const e = errors.value[field]
  return e ? t(`auth.errors.${e.key}`, e.params || {}) : ''
}

function setMode(next) {
  mode.value = next
  errors.value = {}
  formError.value = ''
  form.password = ''
  form.confirm = ''
}

async function onSubmit() {
  if (loading.value) return
  formError.value = ''
  errors.value = validateAuthForm(mode.value, form)
  if (Object.keys(errors.value).length) return

  loading.value = true
  try {
    if (mode.value === 'register') await signUp(form)
    else await signIn(form)
    await router.replace(safeRedirect(route.query.redirect))
  } catch (error) {
    // Não logamos o erro: o objeto do axios carrega o corpo da requisição (senha).
    if (error?.accountCreated) {
      setMode('login')
      formError.value = t('auth.createdNoLogin')
    } else {
      formError.value = t(`auth.errors.${authErrorKey(error)}`)
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-shell {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px 16px;
  color: var(--ink);
  font-family: 'JetBrains Mono', 'Space Grotesk', 'Noto Sans SC', monospace;
}

.auth-card {
  width: min(420px, 100%);
  padding: 32px 28px 24px;
  border: 1px solid var(--glass-line);
  border-radius: 20px;
  background: var(--glass-strong);
  backdrop-filter: blur(16px) saturate(1.2);
  -webkit-backdrop-filter: blur(16px) saturate(1.2);
  box-shadow: 0 24px 60px rgba(0, 8, 18, 0.55);
}

.auth-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  font-weight: 800;
  font-size: 16px;
  letter-spacing: 3px;
  text-shadow: 0 0 20px rgba(25, 227, 196, 0.45);
}

.brand-orb {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #fff, var(--bio-teal) 45%, transparent 72%);
  box-shadow: 0 0 14px var(--bio-teal);
}

.auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  padding: 4px;
  margin-bottom: 22px;
  border: 1px solid var(--glass-line);
  border-radius: 12px;
  background: rgba(2, 11, 20, 0.45);
}

.auth-tab {
  padding: 9px 0;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--ink-soft);
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.25s, color 0.25s;
}

.auth-tab.active {
  background: rgba(25, 227, 196, 0.14);
  color: var(--bio-teal);
}

.auth-title {
  font-size: 1.35rem;
  font-weight: 700;
  margin-bottom: 6px;
}

.auth-subtitle {
  color: var(--ink-soft);
  font-size: 0.82rem;
  line-height: 1.5;
  margin-bottom: 20px;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.78rem;
  color: var(--ink-soft);
}

.field input {
  padding: 11px 13px;
  border: 1px solid var(--glass-line);
  border-radius: 10px;
  background: rgba(2, 11, 20, 0.55);
  color: var(--ink);
  font: inherit;
  font-size: 0.92rem;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.field input:focus-visible {
  border-color: var(--bio-teal);
  box-shadow: 0 0 0 3px rgba(25, 227, 196, 0.18);
}

.field.invalid input {
  border-color: #ff7a7a;
}

.field-error,
.form-error {
  color: #ff9d9d;
  font-size: 0.78rem;
  line-height: 1.4;
}

.form-error {
  padding: 10px 12px;
  border: 1px solid rgba(255, 122, 122, 0.4);
  border-radius: 10px;
  background: rgba(255, 122, 122, 0.08);
}

.submit {
  margin-top: 4px;
  padding: 12px 0;
  border: 0;
  border-radius: 12px;
  background: linear-gradient(120deg, var(--bio-teal), var(--bio-cyan));
  color: #02202a;
  font-weight: 700;
  font-size: 0.92rem;
  cursor: pointer;
  box-shadow: var(--glow-teal);
  transition: transform 0.2s var(--ease-out), opacity 0.2s;
}

.submit:hover:not(:disabled) {
  transform: translateY(-1px);
}

.submit:focus-visible,
.auth-tab:focus-visible,
.switch:focus-visible {
  outline: 2px solid var(--bio-cyan);
  outline-offset: 2px;
}

.submit:disabled {
  opacity: 0.6;
  cursor: progress;
}

.switch {
  display: block;
  width: 100%;
  margin-top: 16px;
  padding: 8px 0;
  border: 0;
  background: transparent;
  color: var(--ink-soft);
  font-size: 0.8rem;
  cursor: pointer;
}

.switch:hover {
  color: var(--bio-teal);
}

.auth-lang {
  display: flex;
  justify-content: center;
  margin-top: 10px;
}

@media (max-width: 480px) {
  .auth-card {
    padding: 26px 18px 18px;
  }
}
</style>

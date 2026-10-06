<template>
  <OceanBackground />
  <router-view v-slot="{ Component }">
    <transition name="dive" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>

<script setup>
import OceanBackground from './components/OceanBackground.vue'
</script>

<style>
/* Reset de estilos globais */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: 'JetBrains Mono', 'Space Grotesk', 'Noto Sans SC', monospace;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Estilos globais de botão */
button {
  font-family: inherit;
}
</style>

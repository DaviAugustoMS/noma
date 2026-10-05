<template>
  <div
    class="pipeline-rail"
    role="progressbar"
    aria-valuemin="1"
    aria-valuemax="5"
    :aria-valuenow="step"
  >
    <template v-for="n in 5" :key="n">
      <span
        class="node"
        :class="{ done: n < step, current: n === step }"
      >
        <span class="node-core"></span>
      </span>
      <span v-if="n < 5" class="link" :class="{ done: n < step }">
        <span class="link-fill"></span>
      </span>
    </template>
  </div>
</template>

<script setup>
defineProps({
  step: { type: Number, required: true }
})
</script>

<style scoped>
.pipeline-rail {
  display: inline-flex;
  align-items: center;
  gap: 0;
}

.node {
  position: relative;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  border: 1px solid rgba(127, 176, 196, 0.45);
  transition: border-color 0.5s, box-shadow 0.5s, transform 0.5s;
}

.node-core {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: transparent;
  transition: background 0.5s, box-shadow 0.5s;
}

.node.done {
  border-color: #19e3c4;
}

.node.done .node-core {
  background: #19e3c4;
}

.node.current {
  border-color: #3cc8ff;
  transform: scale(1.18);
  box-shadow: 0 0 12px rgba(60, 200, 255, 0.7);
}

.node.current .node-core {
  background: #3cc8ff;
  box-shadow: 0 0 8px #3cc8ff;
  animation: beat 1.8s ease-in-out infinite;
}

.node.current::after {
  content: '';
  position: absolute;
  inset: -6px;
  border-radius: 50%;
  border: 1px solid rgba(60, 200, 255, 0.55);
  animation: ripple 2.2s ease-out infinite;
}

.link {
  position: relative;
  width: 22px;
  height: 2px;
  background: rgba(127, 176, 196, 0.22);
  overflow: hidden;
}

.link-fill {
  position: absolute;
  inset: 0;
  transform: scaleX(0);
  transform-origin: left;
  background: linear-gradient(90deg, #19e3c4, #3cc8ff);
  transition: transform 0.9s cubic-bezier(0.22, 1, 0.36, 1);
}

.link.done .link-fill {
  transform: scaleX(1);
}

@keyframes beat {
  50% { transform: scale(0.65); }
}

@keyframes ripple {
  from { transform: scale(0.7); opacity: 0.9; }
  to   { transform: scale(1.7); opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .node.current .node-core,
  .node.current::after { animation: none; }
}
</style>

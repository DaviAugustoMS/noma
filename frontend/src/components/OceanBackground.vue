<template>
  <div class="ocean" aria-hidden="true">
    <div class="ocean-depth"></div>
    <div class="ocean-rays">
      <span class="ray r1"></span>
      <span class="ray r2"></span>
      <span class="ray r3"></span>
      <span class="ray r4"></span>
    </div>
    <canvas ref="canvasRef" class="ocean-canvas"></canvas>
    <div class="ocean-vignette"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const canvasRef = ref(null)

const reducedMotion = typeof window !== 'undefined' &&
  window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches

let ctx = null
let width = 0
let height = 0
let dpr = 1
let rafId = 0
let lastTime = 0
let running = false
let glowSprite = null

const pointer = { x: -9999, y: -9999, active: false, lastMove: 0 }
let fish = []
let plankton = []

const COLORS = [
  [25, 227, 196],  // teal
  [60, 200, 255],  // cyan
  [182, 255, 106], // lime
  [139, 123, 255]  // violet
]

function makeGlowSprite() {
  const size = 64
  const c = document.createElement('canvas')
  c.width = c.height = size
  const g = c.getContext('2d')
  const grad = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  grad.addColorStop(0, 'rgba(255,255,255,1)')
  grad.addColorStop(0.25, 'rgba(255,255,255,0.45)')
  grad.addColorStop(1, 'rgba(255,255,255,0)')
  g.fillStyle = grad
  g.fillRect(0, 0, size, size)
  return c
}

function tintedSprite(rgb) {
  const size = 64
  const c = document.createElement('canvas')
  c.width = c.height = size
  const g = c.getContext('2d')
  g.drawImage(glowSprite, 0, 0)
  g.globalCompositeOperation = 'source-in'
  g.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`
  g.fillRect(0, 0, size, size)
  return c
}

let sprites = []

function seed() {
  const area = width * height
  const fishCount = Math.max(28, Math.min(110, Math.round(area / 16000)))
  const planktonCount = Math.max(30, Math.min(110, Math.round(area / 14000)))

  fish = Array.from({ length: fishCount }, () => {
    const angle = Math.random() * Math.PI * 2
    const speed = 0.6 + Math.random() * 0.8
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      size: 1.4 + Math.random() * 1.8,
      color: Math.floor(Math.random() * COLORS.length),
      phase: Math.random() * Math.PI * 2
    }
  })

  plankton = Array.from({ length: planktonCount }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    r: 0.6 + Math.random() * 1.6,
    drift: 0.04 + Math.random() * 0.14,
    sway: Math.random() * Math.PI * 2,
    twinkle: Math.random() * Math.PI * 2,
    color: Math.floor(Math.random() * COLORS.length)
  }))
}

function resize() {
  const canvas = canvasRef.value
  if (!canvas) return
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  width = window.innerWidth
  height = window.innerHeight
  canvas.width = Math.floor(width * dpr)
  canvas.height = Math.floor(height * dpr)
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  seed()
  if (reducedMotion) draw(0, true)
}

function step(dt, time) {
  const maxSpeed = 1.9
  const minSpeed = 0.5
  const perception = 70
  const sepDist = 18
  const pointerRadius = 220

  // alvo errante: o cardume circula suavemente quando o mouse está parado
  const wanderX = width * (0.5 + 0.32 * Math.sin(time * 0.00021))
  const wanderY = height * (0.5 + 0.28 * Math.cos(time * 0.00017))
  const pointerAlive = pointer.active && time - pointer.lastMove < 4000

  for (let i = 0; i < fish.length; i++) {
    const f = fish[i]
    let ax = 0
    let ay = 0
    let cohX = 0
    let cohY = 0
    let aliX = 0
    let aliY = 0
    let sepX = 0
    let sepY = 0
    let n = 0

    for (let j = 0; j < fish.length; j++) {
      if (i === j) continue
      const o = fish[j]
      const dx = o.x - f.x
      const dy = o.y - f.y
      const d2 = dx * dx + dy * dy
      if (d2 < perception * perception) {
        n++
        cohX += o.x
        cohY += o.y
        aliX += o.vx
        aliY += o.vy
        if (d2 < sepDist * sepDist && d2 > 0.01) {
          sepX -= dx / d2
          sepY -= dy / d2
        }
      }
    }

    if (n > 0) {
      ax += (cohX / n - f.x) * 0.0009
      ay += (cohY / n - f.y) * 0.0009
      ax += (aliX / n - f.vx) * 0.04
      ay += (aliY / n - f.vy) * 0.04
      ax += sepX * 9
      ay += sepY * 9
    }

    // atração ao alvo errante
    ax += (wanderX - f.x) * 0.000045
    ay += (wanderY - f.y) * 0.000045

    // interação com o cursor: atrai de longe, afasta de perto
    if (pointerAlive) {
      const dx = pointer.x - f.x
      const dy = pointer.y - f.y
      const d = Math.sqrt(dx * dx + dy * dy) || 1
      if (d < pointerRadius) {
        const pull = d > 70 ? 0.018 : -0.07
        ax += (dx / d) * pull
        ay += (dy / d) * pull
      }
    }

    // correnteza sutil
    ax += Math.sin(time * 0.0007 + f.phase) * 0.004
    ay += Math.cos(time * 0.0006 + f.phase) * 0.004

    f.vx += ax * dt
    f.vy += ay * dt

    const speed = Math.hypot(f.vx, f.vy) || 1
    const clamped = Math.max(minSpeed, Math.min(maxSpeed, speed))
    f.vx = (f.vx / speed) * clamped
    f.vy = (f.vy / speed) * clamped

    f.x += f.vx * dt
    f.y += f.vy * dt

    // contorno suave nas bordas (reaparece do outro lado)
    const m = 40
    if (f.x < -m) f.x = width + m
    else if (f.x > width + m) f.x = -m
    if (f.y < -m) f.y = height + m
    else if (f.y > height + m) f.y = -m
  }

  for (const p of plankton) {
    p.y -= p.drift * dt
    p.x += Math.sin(time * 0.0004 + p.sway) * 0.18 * dt * 0.06
    if (p.y < -4) {
      p.y = height + 4
      p.x = Math.random() * width
    }
  }
}

function draw(time, still = false) {
  ctx.clearRect(0, 0, width, height)
  ctx.globalCompositeOperation = 'lighter'

  for (const p of plankton) {
    const tw = still ? 0.6 : 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(time * 0.0016 + p.twinkle))
    ctx.globalAlpha = 0.5 * tw
    const s = p.r * 7
    ctx.drawImage(sprites[p.color], p.x - s / 2, p.y - s / 2, s, s)
  }

  for (const f of fish) {
    const speed = Math.hypot(f.vx, f.vy) || 1
    const nx = f.vx / speed
    const ny = f.vy / speed
    const rgb = COLORS[f.color]

    // rastro bioluminescente
    const tail = 10 + speed * 7
    const grad = ctx.createLinearGradient(f.x, f.y, f.x - nx * tail, f.y - ny * tail)
    grad.addColorStop(0, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.55)`)
    grad.addColorStop(1, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0)`)
    ctx.globalAlpha = 1
    ctx.strokeStyle = grad
    ctx.lineWidth = f.size * 0.9
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(f.x, f.y)
    ctx.lineTo(f.x - nx * tail, f.y - ny * tail)
    ctx.stroke()

    // cabeça brilhante
    ctx.globalAlpha = 0.9
    const s = f.size * 9
    ctx.drawImage(sprites[f.color], f.x - s / 2, f.y - s / 2, s, s)
  }

  ctx.globalAlpha = 1
  ctx.globalCompositeOperation = 'source-over'
}

function loop(now) {
  if (!running) return
  const dt = Math.min(2.2, (now - (lastTime || now)) / 16.667)
  lastTime = now
  step(dt, now)
  draw(now)
  rafId = requestAnimationFrame(loop)
}

function start() {
  if (running || reducedMotion) return
  running = true
  lastTime = 0
  rafId = requestAnimationFrame(loop)
}

function stop() {
  running = false
  cancelAnimationFrame(rafId)
}

function onVisibility() {
  if (document.hidden) stop()
  else start()
}

function onPointerMove(e) {
  pointer.x = e.clientX
  pointer.y = e.clientY
  pointer.active = true
  pointer.lastMove = performance.now()
}

function onPointerLeave() {
  pointer.active = false
}

onMounted(() => {
  const canvas = canvasRef.value
  ctx = canvas.getContext('2d')
  glowSprite = makeGlowSprite()
  sprites = COLORS.map(tintedSprite)
  resize()
  window.addEventListener('resize', resize)
  window.addEventListener('pointermove', onPointerMove, { passive: true })
  document.addEventListener('pointerleave', onPointerLeave)
  document.addEventListener('visibilitychange', onVisibility)
  start()
})

onBeforeUnmount(() => {
  stop()
  window.removeEventListener('resize', resize)
  window.removeEventListener('pointermove', onPointerMove)
  document.removeEventListener('pointerleave', onPointerLeave)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<style scoped>
.ocean {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}

.ocean-depth {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(1200px 700px at 78% -10%, rgba(25, 227, 196, 0.16), transparent 60%),
    radial-gradient(900px 600px at 8% 105%, rgba(139, 123, 255, 0.14), transparent 60%),
    linear-gradient(180deg, #06263a 0%, #04182a 38%, #020b14 100%);
}

.ocean-rays {
  position: absolute;
  inset: -20% -10% 30% -10%;
  mix-blend-mode: screen;
  opacity: 0.55;
}

.ray {
  position: absolute;
  top: 0;
  width: 18%;
  height: 130%;
  transform-origin: top center;
  background: linear-gradient(180deg, rgba(120, 255, 235, 0.22), rgba(60, 200, 255, 0) 75%);
  filter: blur(22px);
  animation: sway 14s ease-in-out infinite alternate;
}

.r1 { left: 8%;  transform: rotate(-16deg); animation-duration: 15s; }
.r2 { left: 30%; transform: rotate(-6deg);  animation-duration: 19s; animation-delay: -4s; width: 12%; }
.r3 { left: 56%; transform: rotate(8deg);   animation-duration: 17s; animation-delay: -9s; }
.r4 { left: 78%; transform: rotate(18deg);  animation-duration: 21s; animation-delay: -2s; width: 14%; }

@keyframes sway {
  from { opacity: 0.35; translate: -2% 0; }
  to   { opacity: 0.85; translate: 3% 0; }
}

.ocean-canvas {
  position: absolute;
  inset: 0;
}

.ocean-vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, transparent 55%, rgba(0, 4, 10, 0.55) 100%);
}

@media (prefers-reduced-motion: reduce) {
  .ray { animation: none; }
}
</style>

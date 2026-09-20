<template>
  <div ref="containerRef" class="barn-scene"></div>
</template>

<script setup lang="ts">
// ============================================================
// 牛棚孪生 3D 场景：three 按需动态 import（路由级 chunk 拆分），
// 103 头牛使用单个 InstancedMesh，轮询数据通过 instanceColor 驱动变色。
// WebGL 不可用 / three 加载失败时 emit('fail')，由父组件回落到 SVG 视图。
// ============================================================
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type * as ThreeNs from 'three'
import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { CowProfile, TwinState } from '@/api/cow'

const props = defineProps<{
  cows: CowProfile[]
  twinMap: Map<string, TwinState>
}>()

const emit = defineEmits<{
  (e: 'select', cowId: string): void
  (e: 'fail'): void
}>()

const containerRef = ref<HTMLDivElement>()

const ZONES = ['ZONE-A', 'ZONE-B', 'ZONE-C', 'ZONE-D']
const BARN_Z = (zi: number) => -13 + zi * 8.5
// 与 SVG 版完全一致的颜色口径
const COLOR_UNKNOWN = '#c0c4cc'
const COLOR_LAMENESS = '#f56c6c'
const COLOR_ESTRUS = '#e6a23c'
const COLOR_NORMAL = '#67c23a'

let THREE: typeof ThreeNs
let renderer: ThreeNs.WebGLRenderer | undefined
let scene: ThreeNs.Scene | undefined
let camera: ThreeNs.PerspectiveCamera | undefined
let controls: OrbitControls | undefined
let cowMesh: ThreeNs.InstancedMesh | undefined
let selectRing: ThreeNs.Mesh | undefined
let raycaster: ThreeNs.Raycaster | undefined
let dummy: ThreeNs.Object3D | undefined
let frameId = 0
let disposed = false

let cowIds: string[] = []
let basePos: { x: number; z: number }[] = []
let phases: number[] = []
let downX = 0
let downY = 0

function webglAvailable() {
  try {
    const c = document.createElement('canvas')
    return !!(
      window.WebGLRenderingContext &&
      (c.getContext('webgl2') || c.getContext('webgl'))
    )
  } catch {
    return false
  }
}

function cowColorHex(cowId: string) {
  const ts = props.twinMap.get(cowId)
  if (!ts) return COLOR_UNKNOWN
  if (ts.state?.health_status === 'LAMENESS_RISK') return COLOR_LAMENESS
  if (ts.state?.estrus_status === 'SUSPECTED_HEAT') return COLOR_ESTRUS
  return COLOR_NORMAL
}

function makeZoneLabel(text: string) {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 64
  const ctx = canvas.getContext('2d')!
  ctx.font = '600 34px Inter, "PingFang SC", sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillStyle = '#58d8e7'
  ctx.shadowColor = '#58d8e7'
  ctx.shadowBlur = 12
  ctx.fillText(text, 128, 32)
  const texture = new THREE.CanvasTexture(canvas)
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false })
  )
  sprite.scale.set(7, 1.75, 1)
  return sprite
}

function initScene(OrbitControlsImpl: typeof OrbitControls) {
  const el = containerRef.value!
  scene = new THREE.Scene()
  scene.background = new THREE.Color('#061019')
  scene.fog = new THREE.Fog('#061019', 42, 105)

  camera = new THREE.PerspectiveCamera(42, el.clientWidth / el.clientHeight, 0.1, 220)
  camera.position.set(30, 30, 38)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
  renderer.setSize(el.clientWidth, el.clientHeight)
  renderer.shadowMap.enabled = true
  el.appendChild(renderer.domElement)

  controls = new OrbitControlsImpl(camera, renderer.domElement)
  controls.enableDamping = true
  controls.target.set(0, 0, 3)
  controls.maxPolarAngle = Math.PI / 2.05
  controls.minDistance = 12
  controls.maxDistance = 90

  scene.add(new THREE.HemisphereLight('#b8f4ff', '#0a1720', 1.6))
  const dl = new THREE.DirectionalLight('#b6fbff', 2.0)
  dl.position.set(16, 32, 14)
  dl.castShadow = true
  dl.shadow.mapSize.set(1024, 1024)
  dl.shadow.camera.left = -34
  dl.shadow.camera.right = 34
  dl.shadow.camera.top = 30
  dl.shadow.camera.bottom = -30
  scene.add(dl)

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(72, 54),
    new THREE.MeshStandardMaterial({ color: '#0a2630', roughness: 0.86, metalness: 0.18 })
  )
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  scene.add(ground)

  const grid = new THREE.GridHelper(72, 36, '#1e6470', '#10333d')
  const gridMat = grid.material as ThreeNs.Material
  gridMat.opacity = 0.4
  gridMat.transparent = true
  scene.add(grid)

  // 4 栋牛舍：低矮栏位平台（奶牛立于平台之上，避免被墙体遮挡）+ 发光灯带 + 分区标签
  const barnMat = new THREE.MeshStandardMaterial({ color: '#12343d', roughness: 0.65, metalness: 0.25 })
  const stripMat = new THREE.MeshBasicMaterial({ color: '#58d8e7' })
  const barnGeo = new THREE.BoxGeometry(52, 0.5, 5.2)
  const stripGeo = new THREE.BoxGeometry(50, 0.06, 0.06)
  ZONES.forEach((zone, i) => {
    const z = BARN_Z(i)
    const barn = new THREE.Mesh(barnGeo, barnMat)
    barn.position.set(0, 0.25, z)
    barn.receiveShadow = true
    scene!.add(barn)
    for (const side of [-1, 1]) {
      const strip = new THREE.Mesh(stripGeo, stripMat)
      strip.position.set(0, 0.56, z + side * 2.62)
      scene!.add(strip)
    }
    const label = makeZoneLabel(zone)
    label.position.set(0, 3.4, z)
    scene!.add(label)
  })

  // 传感器柱 + 顶部球体
  const sensorMat = new THREE.MeshStandardMaterial({
    color: '#83e7e1',
    emissive: '#267c7a',
    emissiveIntensity: 1.5
  })
  const poleGeo = new THREE.CylinderGeometry(0.14, 0.14, 3.8, 12)
  const orbGeo = new THREE.SphereGeometry(0.3, 16, 16)
  for (const x of [-21, -7, 7, 21]) {
    const pole = new THREE.Mesh(poleGeo, sensorMat)
    pole.position.set(x, 1.9, 4.2)
    scene.add(pole)
    const orb = new THREE.Mesh(orbGeo, sensorMat)
    orb.position.set(x, 4, 4.2)
    scene.add(orb)
  }

  // 选中光环
  selectRing = new THREE.Mesh(
    new THREE.TorusGeometry(1.15, 0.06, 8, 40),
    new THREE.MeshBasicMaterial({ color: '#58d8e7' })
  )
  selectRing.rotation.x = -Math.PI / 2
  selectRing.position.y = 0.08
  selectRing.visible = false
  scene.add(selectRing)

  raycaster = new THREE.Raycaster()
  dummy = new THREE.Object3D()

  buildCowInstances()
  updateColors()

  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('click', onCanvasClick)
  window.addEventListener('resize', onResize)
  animate()
}

// 103 头牛 → 单个 InstancedMesh；按分区分布在对应牛舍内
function buildCowInstances() {
  if (!scene || !THREE) return
  if (cowMesh) {
    scene.remove(cowMesh)
    cowMesh.geometry.dispose()
    ;(cowMesh.material as ThreeNs.Material).dispose()
    cowMesh = undefined
  }
  const list = props.cows
  if (!list.length) return

  // 排序：先按分区再按牛号，保证实例分组落在对应牛舍
  const sorted = [...list].sort((a, b) => {
    const za = ZONES.indexOf(a.zone)
    const zb = ZONES.indexOf(b.zone)
    if (za !== zb) return (za === -1 ? 99 : za) - (zb === -1 ? 99 : zb)
    return a.cowId.localeCompare(b.cowId)
  })

  // 每个分区内的序号 → 两排网格位
  const zoneCounter: Record<string, number> = {}
  const zoneTotal: Record<string, number> = {}
  for (const c of sorted) zoneTotal[c.zone] = (zoneTotal[c.zone] || 0) + 1

  cowIds = []
  basePos = []
  phases = []
  sorted.forEach((c, i) => {
    let zi = ZONES.indexOf(c.zone)
    if (zi === -1) zi = i % ZONES.length
    const idx = zoneCounter[c.zone] ?? 0
    zoneCounter[c.zone] = idx + 1
    const total = zoneTotal[c.zone] || 1
    const cols = Math.max(1, Math.ceil(total / 2))
    const row = Math.floor(idx / cols)
    const col = idx % cols
    const gap = cols > 1 ? 44 / (cols - 1) : 0
    cowIds.push(c.cowId)
    basePos.push({
      x: cols > 1 ? -22 + col * gap : 0,
      z: BARN_Z(zi) + (row === 0 ? -1.35 : 1.35)
    })
    phases.push(i * 0.7)
  })

  const geo = new THREE.CapsuleGeometry(0.52, 0.9, 5, 10)
  const mat = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.55, metalness: 0.15 })
  cowMesh = new THREE.InstancedMesh(geo, mat, sorted.length)
  cowMesh.castShadow = true
  cowMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
  for (let i = 0; i < sorted.length; i++) {
    dummy!.position.set(basePos[i].x, 1.05, basePos[i].z)
    dummy!.rotation.set(0, 0, Math.PI / 2)
    dummy!.updateMatrix()
    cowMesh.setMatrixAt(i, dummy!.matrix)
  }
  scene.add(cowMesh)
}

// 轮询数据驱动：逐实例写入 instanceColor
function updateColors() {
  if (!cowMesh || !THREE) return
  const tmp = new THREE.Color()
  for (let i = 0; i < cowIds.length; i++) {
    cowMesh.setColorAt(i, tmp.set(cowColorHex(cowIds[i])))
  }
  if (cowMesh.instanceColor) cowMesh.instanceColor.needsUpdate = true
}

function onPointerDown(e: PointerEvent) {
  downX = e.clientX
  downY = e.clientY
}

function onCanvasClick(e: MouseEvent) {
  // 拖拽旋转后松开不触发选中
  if (Math.hypot(e.clientX - downX, e.clientY - downY) > 6) return
  if (!renderer || !camera || !cowMesh || !raycaster) return
  const rect = renderer.domElement.getBoundingClientRect()
  const mouse = new THREE.Vector2(
    ((e.clientX - rect.left) / rect.width) * 2 - 1,
    -((e.clientY - rect.top) / rect.height) * 2 + 1
  )
  raycaster.setFromCamera(mouse, camera)
  const hit = raycaster.intersectObject(cowMesh)[0]
  if (hit && hit.instanceId !== undefined) {
    const id = cowIds[hit.instanceId]
    if (selectRing) {
      selectRing.position.set(basePos[hit.instanceId].x, 0.08, basePos[hit.instanceId].z)
      selectRing.visible = true
    }
    emit('select', id)
  }
}

function onResize() {
  const el = containerRef.value
  if (!el || !camera || !renderer) return
  camera.aspect = el.clientWidth / el.clientHeight
  camera.updateProjectionMatrix()
  renderer.setSize(el.clientWidth, el.clientHeight)
}

function animate() {
  if (disposed) return
  frameId = requestAnimationFrame(animate)
  const t = Date.now() * 0.001
  if (cowMesh && dummy) {
    for (let i = 0; i < cowIds.length; i++) {
      dummy.position.set(basePos[i].x, 1.05 + Math.sin(t + phases[i]) * 0.03, basePos[i].z)
      dummy.rotation.set(0, 0, Math.PI / 2)
      dummy.updateMatrix()
      cowMesh.setMatrixAt(i, dummy.matrix)
    }
    cowMesh.instanceMatrix.needsUpdate = true
  }
  if (selectRing?.visible) {
    const s = 1 + Math.sin(t * 3) * 0.08
    selectRing.scale.set(s, s, 1)
  }
  controls?.update()
  if (renderer && scene && camera) renderer.render(scene, camera)
}

function disposeScene() {
  if (renderer) {
    renderer.domElement.removeEventListener('pointerdown', onPointerDown)
    renderer.domElement.removeEventListener('click', onCanvasClick)
    if (renderer.domElement.parentElement) {
      renderer.domElement.parentElement.removeChild(renderer.domElement)
    }
  }
  window.removeEventListener('resize', onResize)
  controls?.dispose()
  scene?.traverse((obj) => {
    const mesh = obj as ThreeNs.Mesh
    if (mesh.geometry) mesh.geometry.dispose()
    const mat = mesh.material as ThreeNs.Material | ThreeNs.Material[] | undefined
    const disposeMat = (m: ThreeNs.Material) => {
      const withMap = m as ThreeNs.MeshBasicMaterial
      if (withMap.map) withMap.map.dispose()
      m.dispose()
    }
    if (Array.isArray(mat)) mat.forEach(disposeMat)
    else if (mat) disposeMat(mat)
  })
  renderer?.dispose()
  renderer = undefined
  scene = undefined
  camera = undefined
  controls = undefined
  cowMesh = undefined
  selectRing = undefined
}

watch(
  () => props.cows,
  () => {
    buildCowInstances()
    updateColors()
  }
)

watch(
  () => props.twinMap,
  () => updateColors()
)

onMounted(async () => {
  try {
    if (!webglAvailable()) throw new Error('WebGL 不可用')
    THREE = await import('three')
    const mod = await import('three/examples/jsm/controls/OrbitControls.js')
    initScene(mod.OrbitControls)
  } catch {
    emit('fail')
  }
})

onBeforeUnmount(() => {
  disposed = true
  cancelAnimationFrame(frameId)
  disposeScene()
})
</script>

<style scoped>
.barn-scene {
  width: 100%;
  height: 560px;
  border: 1px solid var(--ranch-border);
  border-radius: 8px;
  overflow: hidden;
  background: #061019;
}
.barn-scene :deep(canvas) {
  display: block;
}
</style>

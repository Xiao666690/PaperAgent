<template>
  <div class="cosmic-background" :data-renderer="ready ? 'webgl' : 'fallback'" aria-hidden="true">
    <div class="cosmic-fallback" :style="{ backgroundImage: `url(${backgroundURL})` }" />
    <canvas ref="canvas" v-show="ready" />
    <div class="cosmic-vignette" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
const props = defineProps<{ paused: boolean }>()
const canvas = ref<HTMLCanvasElement | null>(null)
const ready = ref(false)
const backgroundURL = `${import.meta.env.BASE_URL}brand/discovery-flow-blue.png`
let texture: WebGLTexture | null = null
let image: HTMLImageElement | null = null
let disposed = false
let gl: WebGLRenderingContext | null = null
let program: WebGLProgram | null = null
let buffer: WebGLBuffer | null = null
let frame = 0, elapsed = 0, last = 0
let resolution: WebGLUniformLocation | null = null, time: WebGLUniformLocation | null = null
let observer: ResizeObserver | undefined
let reduced: MediaQueryList
const vertex = 'attribute vec2 aPosition; void main(){gl_Position=vec4(aPosition,0.,1.);}'
// Flowing research artwork in the original luminous blue-white palette.
const fragment = `
precision highp float;
uniform vec2 uResolution;
uniform float uTime;
uniform sampler2D uBackground;
void main(){
 vec2 st=gl_FragCoord.xy/uResolution;
 float aspect=uResolution.x/uResolution.y;
 float imageAspect=1672./941.;
 vec2 cover=aspect<imageAspect?vec2(aspect/imageAspect,1.):vec2(1.,imageAspect/aspect);
 vec2 uv=(st-.5)*cover+vec2(aspect<1.?.28:.5,.5);
 vec2 center=vec2(.20,.56);
 vec2 p=(uv-center)*vec2(imageAspect,1.);
 float r=length(p),angle=atan(p.y,p.x);
 float ring=exp(-pow((r-.22)*7.,2.));
 float turn=sin(uTime*.18)*.018*ring;
 mat2 rotation=mat2(cos(turn),-sin(turn),sin(turn),cos(turn));
 vec2 warp=rotation*p;
 warp*=1.+sin(angle*5.-uTime*.65+r*18.)*.010*ring;
 vec2 sampleUV=center+warp/vec2(imageAspect,1.);
 vec3 col=texture2D(uBackground,clamp(vec2(1.-sampleUV.x,sampleUV.y),.001,.999)).rgb;
 // Orbiting light points and luminous wake on top of the detailed artwork.
 for(int i=0;i<12;i++){
  float f=float(i),a=f*6.28318/12.+uTime*(.018+mod(f,3.)*.006);
  float radius=.28+mod(f,3.)*.072;
  vec2 point=vec2(cos(a)*radius,sin(a)*radius*.67);
  float d=length(p-point);
  float spark=exp(-d*d*60000.)+.08*exp(-d*d*2200.);
  float twinkle=.5+.5*sin(uTime*.6+f*2.);
  col+=vec3(.35,.65,.95)*spark*twinkle*.4;
 }
 float pulse=sin(uTime*.3)*.015*ring;
 col+=vec3(.3,.6,.9)*pulse;
 gl_FragColor=vec4(col,1.);
}`
function shader(type: number, source: string) {
  const s = gl!.createShader(type)!
  gl!.shaderSource(s, source); gl!.compileShader(s)
  if (!gl!.getShaderParameter(s, gl!.COMPILE_STATUS)) { gl!.deleteShader(s); return null }
  return s
}
function render() {
  if (!gl || !program || !ready.value) return
  gl.uniform2f(resolution, canvas.value!.width, canvas.value!.height)
  gl.uniform1f(time, elapsed); gl.drawArrays(gl.TRIANGLES, 0, 6)
}
function resize() {
  if (!canvas.value) return
  const box=canvas.value.getBoundingClientRect()
  // Limit fill rate on large screens; the background is deliberately soft.
  const scale=Math.min(1,1400/box.width)
  canvas.value.width=Math.max(1,Math.round(box.width*scale))
  canvas.value.height=Math.max(1,Math.round(box.height*scale))
  gl?.viewport(0,0,canvas.value.width,canvas.value.height); render()
}
function tick(now: number) {
  frame=requestAnimationFrame(tick)
  if (now-last<1000/24) return
  if(last) elapsed+=Math.min((now-last)/1000,.1)
  last=now; render()
}
function sync() {
  cancelAnimationFrame(frame); frame=0; last=0
  if(ready.value && !props.paused && !reduced.matches && !document.hidden) frame=requestAnimationFrame(tick)
  else render()
}
function contextLost(event: Event) { event.preventDefault();ready.value=false;cancelAnimationFrame(frame) }
watch(()=>props.paused,sync)
onMounted(()=>{
  reduced=matchMedia('(prefers-reduced-motion: reduce)')
  gl=canvas.value!.getContext('webgl',{alpha:false,antialias:false,powerPreference:'low-power'})
  if(gl){
    const vs=shader(gl.VERTEX_SHADER,vertex),fs=shader(gl.FRAGMENT_SHADER,fragment)
    if(vs && fs){
      program=gl.createProgram()!;gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);gl.deleteShader(vs);gl.deleteShader(fs)
      if(gl.getProgramParameter(program,gl.LINK_STATUS)){
        gl.useProgram(program);buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW)
        const attribute=gl.getAttribLocation(program,'aPosition');gl.enableVertexAttribArray(attribute);gl.vertexAttribPointer(attribute,2,gl.FLOAT,false,0,0)
        resolution=gl.getUniformLocation(program,'uResolution');time=gl.getUniformLocation(program,'uTime');
        texture=gl.createTexture();image=new Image();
        image.onload=()=>{
          if(disposed || !gl || !texture) return
          gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true)
          gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image!)
          gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR)
          gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE)
          gl.uniform1i(gl.getUniformLocation(program!,'uBackground'),0);ready.value=true;resize();sync()
        }
        image.src=backgroundURL
      }
    }
  }
  observer=new ResizeObserver(resize);observer.observe(canvas.value!);resize();sync()
  reduced.addEventListener('change',sync);document.addEventListener('visibilitychange',sync);canvas.value!.addEventListener('webglcontextlost',contextLost)
})
onBeforeUnmount(()=>{disposed=true;if(image)image.onload=null;cancelAnimationFrame(frame);observer?.disconnect();reduced?.removeEventListener('change',sync);document.removeEventListener('visibilitychange',sync);canvas.value?.removeEventListener('webglcontextlost',contextLost);if(gl){gl.deleteTexture(texture);gl.deleteBuffer(buffer);gl.deleteProgram(program)}})
</script>

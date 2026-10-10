<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { Sparkles, RefreshCw, ArrowUpRight, BookPlus, Radar, CalendarDays } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { getDailyRecommendations, type DailyRecommendations, type RecommendedPaper } from '@/api/dashboard'
import { getKnowledgeList } from '@/api/data'
import { importExternalPaper } from '@/api/qa'
import { useChatHistoryStore } from '@/stores/chatHistory'

const emit = defineEmits<{ imported: [] }>()
const data = ref<DailyRecommendations | null>(null)
const loading = ref(false)
const error = ref('')
const activeTopic = ref('全部')
const papers = computed(() => (data.value?.items || []).filter(p => activeTopic.value === '全部' || p.topic === activeTopic.value))
const history = useChatHistoryStore()
let alive = true
let timer: ReturnType<typeof setInterval> | undefined
const localDate = () => new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Shanghai', year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())
let requestedDate = localDate()

async function refresh(force = false) {
  if (loading.value) return
  const token = localStorage.getItem('token')
  loading.value = true
  error.value = ''
  try {
    history.loadFromStorage()
    const questions = history.state.sessions.slice(0, 12).flatMap(session => session.messages.filter(m => m.role === 'user').slice(-3).map(m => m.content.slice(0, 500))).slice(0, 30)
    const result = await getDailyRecommendations(questions, force)
    if (!alive || token !== localStorage.getItem('token')) return
    data.value = result
    requestedDate = localDate()
    activeTopic.value = '全部'
  } catch (cause: any) {
    if (alive) error.value = cause?.response?.data?.detail || '推荐暂时无法加载，请稍后重试'
  } finally { if (alive) loading.value = false }
}
function openPaper(paper: RecommendedPaper) {
  if (/^https?:\/\//i.test(paper.url)) window.open(paper.url, '_blank', 'noopener,noreferrer')
}
const dialog = ref(false)
const selectedPaper = ref<RecommendedPaper | null>(null)
const libraries = ref<Array<{knowledgeID: string; knowledgeName: string}>>([])
const selectedLibrary = ref('')
const loadingLibraries = ref(false)
const importing = ref(false)
const importedIds = ref<string[]>([])
async function chooseLibrary(paper: RecommendedPaper) {
  selectedPaper.value = paper
  dialog.value = true
  loadingLibraries.value = true
  selectedLibrary.value = ''
  libraries.value = []
  try {
    const response = await getKnowledgeList()
    libraries.value = response.data?.knowledgeList || []
    selectedLibrary.value = libraries.value[0]?.knowledgeID || ''
  } catch { ElMessage.error('读取论文库失败，请重试') }
  finally { loadingLibraries.value = false }
}
async function addPaper() {
  if (!selectedPaper.value || !selectedLibrary.value || importing.value) return
  importing.value = true
  try {
    await importExternalPaper(selectedPaper.value.pdf_url, selectedLibrary.value, selectedPaper.value.title)
    importedIds.value.push(selectedPaper.value.id)
    dialog.value = false
    ElMessage.success('已加入论文库，正在处理论文')
    emit('imported')
  } catch (cause: any) { ElMessage.error(cause?.message || '导入失败，请重试') }
  finally { importing.value = false }
}
onMounted(() => {
  void refresh()
  timer = setInterval(() => { if (localDate() !== requestedDate) void refresh() }, 60000)
})
onBeforeUnmount(() => { alive = false; clearInterval(timer) })
</script>

<template>
  <section class="daily-discovery" aria-labelledby="daily-discovery-title" :aria-busy="loading">
    <header class="discovery-heading">
      <div class="discovery-heading-copy"><span class="discovery-mark"><Radar :size="22" /></span><div><p class="discovery-kicker">YOUR DAILY DISCOVERY</p><h3 id="daily-discovery-title">今日推荐 <span>前沿论文</span></h3></div></div>
      <button class="discovery-refresh" :disabled="loading" @click="refresh(true)"><RefreshCw :size="15" :class="{ spinning: loading }" />{{ loading ? '检索中…' : '更新推荐' }}</button>
    </header>
    <p class="discovery-intro">从你的科研积累出发，发现下一篇值得读的论文</p>
    <div v-if="data?.profile.topics.length" class="interest-profile"><Sparkles :size="17" /><div><strong>{{ data.profile.summary }}</strong><p>本地兴趣归纳 · 根据论文库、研究目标与近期问题 · 仅发送检索关键词</p></div></div>
    <div v-if="data?.profile.topics.length" class="interest-filters" aria-label="推荐方向筛选">
      <button v-for="label in ['全部', ...data.profile.topics.map(t => t.label)]" :key="label" :class="{ selected: activeTopic === label }" :aria-pressed="activeTopic === label" @click="activeTopic = label">{{ label }}</button>
    </div>
    <p v-if="error" class="discovery-notice" role="alert">{{ error }}<span v-if="data?.items.length">，以下为此前加载的推荐</span></p>
    <p v-if="data?.warning" class="discovery-notice" role="status">{{ data.warning }}</p>
    <div v-if="loading && !data" class="discovery-skeleton" role="status"><p>正在归纳你的研究方向，并检索近期论文…</p><div v-for="n in 3" :key="n"><i /><i /><i /></div></div>
    <div v-else-if="papers.length" class="recommendation-grid">
      <article v-for="paper in papers" :key="paper.id" class="recommendation-card">
        <div class="paper-topline"><span class="paper-topic">{{ paper.topic }}</span><span class="paper-fresh" :class="{ today: paper.is_today }">{{ paper.is_today ? '今日新发布' : '近30天' }}</span></div>
        <a class="recommendation-title" :href="paper.url" target="_blank" rel="noopener noreferrer">{{ paper.title }}</a>
        <p class="recommendation-authors">{{ paper.authors.slice(0, 3).join(' · ') || '作者信息暂缺' }}</p>
        <p class="recommendation-summary">{{ paper.summary || '来源暂未提供摘要，可打开原文查看' }}</p>
        <p class="recommendation-reason"><Sparkles :size="13" />{{ paper.reason }}</p>
        <div class="recommendation-meta"><CalendarDays :size="13" />{{ paper.published }}<span>{{ paper.venue }}</span></div>
        <footer><button @click="openPaper(paper)">查看原文 <ArrowUpRight :size="14" /></button><button v-if="paper.importable" class="add-paper" :disabled="importedIds.includes(paper.id)" @click="chooseLibrary(paper)"><BookPlus :size="14" />{{ importedIds.includes(paper.id) ? '已加入' : '加入论文库' }}</button><span v-else class="manual-import">下载 PDF 后可手动上传</span></footer>
      </article>
    </div>
    <div v-else-if="!loading" class="discovery-empty"><BookPlus :size="26" /><strong>{{ data?.status === 'no_interests' ? '积累一点科研线索，让推荐更懂你' : data?.status === 'unavailable' || error ? '最新论文检索暂不可用' : '这个方向暂未找到近期匹配论文' }}</strong><p>{{ data?.status === 'no_interests' ? '上传论文、整理研究方向标签，或发起问答与深度研究后，这里会自动生成推荐' : '可以稍后更新推荐，或切换上方的研究方向' }}</p></div>
    <div v-if="data" class="discovery-footnote"><span>今日优先 · 无当天结果时展示近30天论文 · 日期依据首次公告／来源发布日期 · 未核查全文</span><span>{{ data.cached ? '已缓存 · ' : '' }}更新于 {{ new Date(data.generated_at).toLocaleString('zh-CN', { month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit' }) }}</span></div>
    <el-dialog v-model="dialog" title="加入论文库" width="min(480px, 92vw)" append-to-body :close-on-click-modal="!importing" :close-on-press-escape="!importing" :show-close="!importing">
      <p class="mb-4 text-sm">{{ selectedPaper?.title }}</p>
      <label class="block mb-2" for="recommendation-library">选择论文库</label>
      <el-select id="recommendation-library" v-model="selectedLibrary" class="w-full" :loading="loadingLibraries" :disabled="importing" placeholder="选择保存位置"><el-option v-for="library in libraries" :key="library.knowledgeID" :value="library.knowledgeID" :label="library.knowledgeName" /></el-select>
      <p v-if="!loadingLibraries && !libraries.length" class="mt-3 text-sm text-slate-500">暂无论文库，请先在“论文库”中创建一个</p>
      <template #footer><el-button :disabled="importing" @click="dialog = false">取消</el-button><el-button type="primary" :disabled="!selectedLibrary || loadingLibraries" :loading="importing" @click="addPaper">下载并加入</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.daily-discovery{margin-bottom:20px;padding:24px;border:1px solid #cfe3f7;border-radius:18px;background:linear-gradient(120deg,#fff,#f3faff);box-shadow:0 6px 24px #147bdf08;min-width:0}
.discovery-heading,.discovery-heading-copy{display:flex;align-items:center;gap:12px}.discovery-heading{justify-content:space-between}.discovery-mark{display:grid;place-items:center;width:44px;height:44px;border-radius:13px;background:#e4f3ff;color:#147bdf;flex:none}.discovery-kicker{margin:0;color:#5685af;font-size:10px;font-weight:700;letter-spacing:.12em}.discovery-heading h3{margin:3px 0 0;font-size:20px;font-weight:700;color:#20354d}.discovery-heading h3 span{margin-left:8px;font-size:12px;font-weight:500;color:#7090ad}.discovery-intro{margin:14px 0;color:#677e93;font-size:13px}
.discovery-refresh{display:flex;align-items:center;gap:6px;padding:9px 12px;border:1px solid #c5dcf1;border-radius:10px;background:#fff;color:#147bdf;font-size:12px;white-space:nowrap}.daily-discovery button{cursor:pointer;transition:background-color 160ms ease-out,transform 160ms ease-out}.daily-discovery button:active{transform:scale(.97)}.daily-discovery button:disabled{opacity:.55;cursor:default}.daily-discovery button:focus-visible,.recommendation-title:focus-visible{outline:2px solid #147bdf;outline-offset:3px}.interest-profile{display:flex;align-items:flex-start;gap:9px;padding:12px 14px;border-radius:11px;background:#eaf5ff;color:#236496}.interest-profile>svg{flex:none;margin-top:2px}.interest-profile strong{font-size:13px;font-weight:600}.interest-profile p{margin:5px 0 0;color:#6b879f;font-size:11px}.interest-filters{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.interest-filters button{padding:6px 11px;border:1px solid #dce7f1;border-radius:999px;background:white;color:#58758d;font-size:12px}.interest-filters button.selected{border-color:#147bdf;background:#147bdf;color:white}
.recommendation-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.recommendation-card{display:flex;flex-direction:column;min-width:0;padding:17px;border:1px solid #dde8f2;border-radius:13px;background:#fff}.paper-topline{display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;margin-bottom:11px;font-size:10px}.paper-topic{color:#3276ad}.paper-fresh{padding:3px 6px;border-radius:5px;background:#f0f4f7;color:#71879b}.paper-fresh.today{background:#e2f7ef;color:#168264}.recommendation-title{color:#23384e;font-size:14px;font-weight:650;line-height:1.55;text-decoration:none;overflow-wrap:anywhere}.recommendation-authors{margin:7px 0;color:#8393a3;font-size:11px;line-height:1.5}.recommendation-summary{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;color:#61758a;font-size:12px;line-height:1.7;margin:4px 0 12px}.recommendation-reason{display:flex;align-items:flex-start;gap:5px;margin:auto 0 10px;padding:8px;border-radius:8px;background:#f3faff;color:#447da9;font-size:11px;line-height:1.6}.recommendation-reason svg{flex:none;margin-top:2px}.recommendation-meta{display:flex;align-items:center;flex-wrap:wrap;gap:5px;font-size:10px;color:#8595a5}.recommendation-meta span{margin-left:4px}.recommendation-card footer{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-top:13px;padding-top:12px;border-top:1px solid #edf2f6}.recommendation-card footer button{display:flex;align-items:center;gap:4px;color:#147bdf;font-size:11px;padding:5px 0}.recommendation-card footer .add-paper{padding:6px 8px;border-radius:7px;background:#edf7ff}.manual-import{font-size:10px;color:#8a99a7}
.discovery-notice{margin:12px 0;color:#926d29;font-size:12px;line-height:1.6}.discovery-empty{display:flex;align-items:center;flex-direction:column;gap:10px;padding:28px 12px;text-align:center;color:#6c8caa}.discovery-empty strong{font-size:14px;font-weight:550;color:#4b6c8b}.discovery-empty p{max-width:540px;margin:0;font-size:12px;line-height:1.7}.discovery-footnote{display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;margin-top:17px;color:#8b9cac;font-size:10px;line-height:1.6}.discovery-skeleton>p{font-size:12px;color:#6d8ba7}.discovery-skeleton>div{display:inline-flex;flex-direction:column;gap:12px;width:31%;margin:8px 1%;padding:20px;background:#fff;border:1px solid #e4edf5;border-radius:12px}.discovery-skeleton i{height:12px;border-radius:5px;background:#edf4fa}.discovery-skeleton i:nth-child(2){width:80%}.spinning{animation:discovery-spin .9s linear infinite}@keyframes discovery-spin{to{transform:rotate(360deg)}}
@media(hover:hover) and (pointer:fine){.discovery-refresh:hover{background:#edf7ff}.recommendation-title:hover{color:#147bdf}.interest-filters button:not(.selected):hover{background:#edf7ff}}
@media(max-width:1150px){.recommendation-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.daily-discovery{padding:16px}.recommendation-grid{grid-template-columns:1fr}.discovery-heading h3 span{display:none}.discovery-skeleton>div{width:98%}}
@media(prefers-reduced-motion:reduce){.spinning{animation:none}.daily-discovery button{transition:none}.daily-discovery button:active{transform:none}}
</style>

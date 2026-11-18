<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { api, type LlmPreset, type LlmSettings } from '../api'

const props = defineProps<{
  settings: LlmSettings | null
  isDeveloper: boolean
}>()

const emit = defineEmits<{
  close: []
  updated: [settings: LlmSettings]
}>()

const form = reactive({
  provider: props.settings?.provider || 'openai_compatible',
  base_url: props.settings?.base_url || 'https://api.deepseek.com/v1',
  model: props.settings?.model || 'deepseek-chat',
  api_key: '',
  clear_key: false,
})

watch(() => props.settings, val => {
  if (!val) return
  form.provider = val.provider
  form.base_url = val.base_url
  form.model = val.model
  form.api_key = ''
  form.clear_key = false
}, { immediate: true })

const busy = ref(false)
const feedback = ref('')
const feedbackError = ref(false)

function applyPreset(preset: LlmPreset) {
  form.provider = preset.provider
  form.base_url = preset.base_url
  form.model = preset.model
  feedback.value = `已切换至 ${preset.label}`
  feedbackError.value = false
}

async function testConnection() {
  busy.value = true; feedback.value = ''; feedbackError.value = false
  try {
    const res = await api<{ ok: boolean; model: string; latency_ms: number; reply: string }>(
      '/settings/llm/test', 'POST', form,
    )
    feedback.value = `连接正常 (${res.model} · ${res.latency_ms}ms)`
  } catch (err) {
    feedbackError.value = true
    feedback.value = err instanceof Error ? err.message : '连接失败'
  } finally {
    busy.value = false
  }
}

async function save() {
  busy.value = true; feedback.value = ''; feedbackError.value = false
  try {
    const updated = await api<LlmSettings>('/settings/llm', 'PUT', form)
    form.api_key = ''
    form.clear_key = false
    emit('updated', updated)
    feedback.value = '配置已保存'
  } catch (err) {
    feedbackError.value = true
    feedback.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="modal-mask" role="dialog" aria-label="AI 设置" @click.self="emit('close')">
    <div class="card modal-panel">
      <div class="card-head">
        <span class="card-title">AI 模型接口</span>
        <button type="button" class="icon-close" aria-label="关闭模型设置" @click="emit('close')">✕</button>
      </div>

      <div class="pad-md stack-md">
        <div class="row-between">
          <span class="badge" :class="settings?.configured ? 'badge-green' : ''">
            {{ settings?.configured ? `已配置 (${settings.masked_key})` : '未配置密钥 · 静态模式' }}
          </span>
          <span class="muted">{{ settings?.model || 'deepseek-chat' }}</span>
        </div>

        <template v-if="isDeveloper">
          <div v-if="settings?.presets?.length" class="prompt-chips">
            <button
              v-for="preset in settings.presets"
              :key="preset.id"
              type="button"
              class="chip-btn"
              @click="applyPreset(preset)"
            >
              {{ preset.label }}
            </button>
          </div>

          <form class="grid-2" @submit.prevent="save">
            <label>
              协议
              <select v-model="form.provider" name="llmProvider">
                <option value="openai_compatible">OpenAI 兼容</option>
                <option value="gemini">Google Gemini</option>
                <option value="anthropic">Anthropic Claude</option>
              </select>
            </label>
            <label>
              模型
              <input v-model="form.model" name="llmModel" required />
            </label>
            <label class="span-all">
              Base URL
              <input v-model="form.base_url" name="llmBaseUrl" required />
            </label>
            <label class="span-all">
              API Key
              <input
                v-model="form.api_key"
                name="llmApiKey"
                type="password"
                autocomplete="off"
                :placeholder="settings?.configured ? `留空保持 ${settings.masked_key}` : '输入 API Key'"
              />
            </label>
            <label v-if="settings?.configured" class="span-all check-inline">
              <input v-model="form.clear_key" type="checkbox" name="clearKey" />
              <span>清除已存密钥</span>
            </label>

            <div v-if="feedback" class="span-all alert-bar" :class="{ err: feedbackError }">
              {{ feedback }}
            </div>

            <div class="span-all row-end">
              <button type="button" class="btn" :disabled="busy" @click="testConnection">测试连接</button>
              <button type="submit" class="btn btn-primary" :disabled="busy">保存</button>
            </div>
          </form>
        </template>
      </div>
    </div>
  </div>
</template>

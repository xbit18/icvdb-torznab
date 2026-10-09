<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue'
import type { CustomRule, Preset, ResultProcessing, RuleField, RuleOperator } from '../api/types'
import { useAppStore } from '../composables/appStore'
import ToggleSwitch from '../components/ToggleSwitch.vue'
import { useLocale } from '../i18n'
const props = defineProps<{ initial?: ResultProcessing; saving?: boolean }>()
const emit = defineEmits<{ save: [value: ResultProcessing] }>()
const store = useAppStore()
const { t } = useLocale()
const errors = reactive<string[]>([])
onMounted(() => {
  if (props.initial === undefined) store.loadAll()
})
const model = reactive<ResultProcessing>({
  preset: 'unfiltered',
  custom_rules: [],
  subtitle_language_correction: false,
})
const cloneProcessing = (value: ResultProcessing): ResultProcessing => ({
  preset: value.preset,
  custom_rules: value.custom_rules.map((rule) => ({ ...rule })),
  subtitle_language_correction: value.subtitle_language_correction,
})
watch(
  () => props.initial ?? store.state.settings?.result_processing,
  (value) => {
    if (value) Object.assign(model, cloneProcessing(value))
  },
  { immediate: true },
)
const presetOptions = computed<{ value: Preset; title: string; text: string }[]>(() => [
  {
    value: 'unfiltered',
    title: t('preset.unfiltered'),
    text: t('results.unfilteredText'),
  },
  {
    value: 'italian_preferred',
    title: t('preset.italianPreferred'),
    text: t('results.preferredText'),
  },
  {
    value: 'italian_only',
    title: t('preset.italianOnly'),
    text: t('results.onlyText'),
  },
  { value: 'custom', title: t('preset.custom'), text: t('results.customText') },
])
const operators = (field: RuleField): { value: RuleOperator; label: string }[] =>
  field === 'title' || field === 'provider'
    ? [
        { value: 'contains', label: t('results.contains') },
        { value: 'not_contains', label: t('results.notContains') },
        { value: 'equals', label: t('results.equals') },
      ]
    : [
        { value: 'equals', label: t('results.equals') },
        { value: 'gte', label: t('results.atLeast') },
        { value: 'lte', label: t('results.atMost') },
      ]
function addRule() {
  if (model.custom_rules.length < 100)
    model.custom_rules.push({
      enabled: true,
      field: 'title',
      operator: 'contains',
      value: '',
      action: 'exclude',
    })
}
function fieldChanged(rule: CustomRule) {
  rule.operator = 'equals'
  rule.value = rule.field === 'size' || rule.field === 'seeders' ? 0 : ''
}
function actionChanged(rule: CustomRule) {
  if (rule.action === 'score') rule.score = 0
  else delete rule.score
}
function validate() {
  errors.splice(0)
  model.custom_rules.forEach((rule, index) => {
    const numeric = rule.field === 'size' || rule.field === 'seeders'
    if (
      !numeric &&
      (typeof rule.value !== 'string' || !rule.value.trim() || rule.value.length > 512)
    )
      errors.push(t('results.textError', { number: index + 1 }))
    if (numeric && (typeof rule.value !== 'number' || !Number.isFinite(rule.value)))
      errors.push(t('results.numberError', { number: index + 1 }))
    if (
      rule.action === 'score' &&
      (!Number.isFinite(rule.score) || Math.abs(rule.score ?? 1001) > 1000)
    )
      errors.push(t('results.scoreError', { number: index + 1 }))
  })
  return !errors.length
}
function submit() {
  if (!validate()) return
  const payload = cloneProcessing(model)
  if (props.initial !== undefined) emit('save', payload)
  else store.saveResultProcessing(payload).catch(() => undefined)
}
const isSaving = computed(() => props.saving ?? store.state.saving)
</script>
<template>
  <section class="page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">{{ t('common.settings') }}</p>
        <h1>{{ t('results.title') }}</h1>
        <p>{{ t('results.intro') }}</p>
      </div>
    </div>
    <div class="preset-grid" role="radiogroup" :aria-label="t('results.presetLabel')">
      <label
        v-for="option in presetOptions"
        :key="option.value"
        class="choice-card"
        :class="{ 'choice-card--selected': model.preset === option.value }"
        ><input
          v-model="model.preset"
          type="radio"
          name="preset"
          :value="option.value"
          :aria-label="option.title"
        /><span
          ><strong>{{ option.title }}</strong
          ><small>{{ option.text }}</small></span
        ></label
      >
    </div>
    <div class="notice">
      <strong>{{ t('results.rankingTitle') }}</strong>
      <p>{{ t('results.rankingText') }}</p>
    </div>
    <article v-if="model.preset === 'custom'" class="card rules-card">
      <div class="card-heading">
        <div>
          <h2>{{ t('results.customRules') }}</h2>
          <p>{{ t('results.rulesDescription') }}</p>
        </div>
        <button
          class="button button--secondary"
          type="button"
          :disabled="model.custom_rules.length >= 100"
          @click="addRule"
        >
          {{ t('results.addRule') }}
        </button>
      </div>
      <p v-if="!model.custom_rules.length" class="empty-state">{{ t('results.noRules') }}</p>
      <fieldset v-for="(rule, index) in model.custom_rules" :key="index" class="rule">
        <legend>{{ t('results.rule', { number: index + 1 }) }}</legend>
        <div class="rule-grid">
          <ToggleSwitch
            v-model="rule.enabled"
            :label="t('results.ruleEnabled', { number: index + 1 })"
          /><label
            >{{ t('results.field')
            }}<select
              v-model="rule.field"
              :aria-label="`${t('results.rule', { number: index + 1 })} ${t('results.field')}`"
              @change="fieldChanged(rule)"
            >
              <option value="title">{{ t('results.titleField') }}</option>
              <option value="provider">{{ t('results.provider') }}</option>
              <option value="size">{{ t('results.size') }}</option>
              <option value="seeders">{{ t('results.seeders') }}</option>
            </select></label
          ><label
            >{{ t('results.operator')
            }}<select
              v-model="rule.operator"
              :aria-label="`${t('results.rule', { number: index + 1 })} ${t('results.operator')}`"
            >
              <option
                v-for="operator in operators(rule.field)"
                :key="operator.value"
                :value="operator.value"
              >
                {{ operator.label }}
              </option>
            </select></label
          ><label
            >{{ t('results.value')
            }}<input
              v-if="rule.field === 'size' || rule.field === 'seeders'"
              v-model.number="rule.value"
              type="number"
              :aria-label="`${t('results.rule', { number: index + 1 })} ${t('results.value')}`" /><input
              v-else
              v-model="rule.value"
              type="text"
              maxlength="512"
              :aria-label="`${t('results.rule', { number: index + 1 })} ${t('results.value')}`" /></label
          ><label
            >{{ t('results.action')
            }}<select
              v-model="rule.action"
              :aria-label="`${t('results.rule', { number: index + 1 })} ${t('results.action')}`"
              @change="actionChanged(rule)"
            >
              <option value="exclude">{{ t('results.exclude') }}</option>
              <option value="score">{{ t('results.adjustScore') }}</option>
            </select></label
          ><label v-if="rule.action === 'score'"
            >{{ t('results.score')
            }}<input
              v-model.number="rule.score"
              type="number"
              min="-1000"
              max="1000"
              :aria-label="`${t('results.rule', { number: index + 1 })} ${t('results.score')}`"
          /></label>
        </div>
        <button
          class="text-button danger-text"
          type="button"
          :aria-label="t('results.removeRule', { number: index + 1 })"
          @click="model.custom_rules.splice(index, 1)"
        >
          {{ t('results.remove') }}
        </button>
      </fieldset>
    </article>
    <article class="card rules-card">
      <h2>{{ t('results.languageCorrectionTitle') }}</h2>
      <ToggleSwitch
        v-model="model.subtitle_language_correction"
        :label="t('results.languageCorrectionLabel')"
        :description="t('results.languageCorrectionDescription')"
      />
    </article>
    <ul v-if="errors.length" class="inline-error" role="alert">
      <li v-for="error in errors" :key="error">{{ error }}</li>
    </ul>
    <p v-else-if="store.state.error" class="inline-error" role="alert">{{ store.state.error }}</p>
    <p v-if="store.state.feedback" class="success-message" role="status">
      {{ store.state.feedback }}
    </p>
    <button class="button" type="button" :disabled="isSaving" @click="submit">
      {{ isSaving ? t('common.saving') : t('results.save') }}
    </button>
  </section>
</template>

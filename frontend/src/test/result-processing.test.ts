import { fireEvent, render, screen } from '@testing-library/vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ResultProcessingView from '../views/ResultProcessingView.vue'
import { useLocale } from '../i18n'

describe('result processing', () => {
  beforeEach(() => useLocale().setLocale('en'))
  it('reveals custom rules only for Custom and saves a valid structured payload', async () => {
    const save = vi.fn().mockResolvedValue(undefined)
    render(ResultProcessingView, {
      props: {
        initial: {
          preset: 'unfiltered',
          custom_rules: [],
          subtitle_language_correction: false,
        },
        saving: false,
      },
      attrs: { onSave: save },
    })

    expect(screen.queryByRole('heading', { name: 'Custom rules' })).toBeNull()
    await fireEvent.click(screen.getByLabelText('Custom'))
    await fireEvent.click(screen.getByRole('button', { name: 'Add rule' }))
    expect(screen.getByRole('heading', { name: 'Custom rules' })).toBeTruthy()

    await fireEvent.update(screen.getByLabelText('Rule 1 Value'), '1080p')
    await fireEvent.update(screen.getByLabelText('Rule 1 Action'), 'score')
    await fireEvent.update(screen.getByLabelText('Rule 1 Score'), '25')
    await fireEvent.click(screen.getByRole('button', { name: 'Save result processing' }))
    expect(save).toHaveBeenCalledWith({
      preset: 'custom',
      subtitle_language_correction: false,
      custom_rules: [
        {
          enabled: true,
          field: 'title',
          operator: 'contains',
          value: '1080p',
          action: 'score',
          score: 25,
        },
      ],
    })

    await fireEvent.update(screen.getByLabelText('Rule 1 Field'), 'seeders')
    expect((screen.getByLabelText('Rule 1 Operator') as HTMLSelectElement).value).toBe('equals')
    await fireEvent.update(screen.getByLabelText('Rule 1 Action'), 'exclude')
    expect(screen.queryByLabelText('Rule 1 Score')).toBeNull()
    await fireEvent.click(screen.getByRole('button', { name: 'Remove rule 1' }))
    expect(screen.getByText('No custom rules yet.')).toBeTruthy()
  })

  it('preserves disabled rules and validates numeric values and scores', async () => {
    const save = vi.fn()
    render(ResultProcessingView, {
      props: {
        initial: {
          preset: 'custom',
          subtitle_language_correction: false,
          custom_rules: [
            {
              enabled: false,
              field: 'seeders',
              operator: 'gte',
              value: 5,
              action: 'score',
              score: 10,
            },
          ],
        },
      },
      attrs: { onSave: save },
    })
    expect(
      (screen.getByRole('switch', { name: 'Rule 1 enabled' }) as HTMLInputElement).checked,
    ).toBe(false)
    await fireEvent.update(screen.getByLabelText('Rule 1 Value'), '')
    await fireEvent.update(screen.getByLabelText('Rule 1 Score'), '1001')
    await fireEvent.click(screen.getByRole('button', { name: 'Save result processing' }))
    expect(screen.getByRole('alert').textContent).toContain('finite number')
    expect(screen.getByRole('alert').textContent).toContain('-1000 and 1000')
    expect(save).not.toHaveBeenCalled()
  })

  it('enforces the 100-rule builder limit', () => {
    const rules = Array.from({ length: 100 }, () => ({
      enabled: true,
      field: 'title' as const,
      operator: 'contains' as const,
      value: 'x',
      action: 'exclude' as const,
    }))
    render(ResultProcessingView, {
      props: {
        initial: { preset: 'custom', custom_rules: rules, subtitle_language_correction: false },
      },
    })
    expect((screen.getByRole('button', { name: 'Add rule' }) as HTMLButtonElement).disabled).toBe(
      true,
    )
    expect(screen.getAllByRole('group')).toHaveLength(100)
  })

  it('keeps subtitle language correction independent from the preset', async () => {
    const save = vi.fn()
    render(ResultProcessingView, {
      props: {
        initial: { preset: 'unfiltered', custom_rules: [], subtitle_language_correction: false },
      },
      attrs: { onSave: save },
    })
    const toggle = screen.getByRole('switch', {
      name: /Correct Italian subtitle detection/i,
    })
    expect((toggle as HTMLInputElement).checked).toBe(false)
    await fireEvent.click(toggle)
    await fireEvent.click(screen.getByRole('button', { name: 'Save result processing' }))
    expect(save).toHaveBeenCalledWith({
      preset: 'unfiltered',
      custom_rules: [],
      subtitle_language_correction: true,
    })
  })
})

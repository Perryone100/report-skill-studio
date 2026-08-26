import { afterEach, describe, expect, it, vi } from 'vitest'

import { mockApiClient } from './mockClient'
import type { ReportDraft } from './types'

afterEach(() => vi.useRealTimers())

describe('mock HTML export', () => {
  it('escapes title and JSON content as text', async () => {
    vi.useFakeTimers()
    const draft: ReportDraft = {
      reportId: 'security-test',
      title: '</title><script>unexpected()</script>',
      meeting_date: '2026-08-26',
      executive_summary: '</pre><img src=x onerror=unexpected()>',
      summary_cards: [],
      sections: [],
    }

    const exportPromise = mockApiClient.exportReport(draft, 'html')
    await vi.runAllTimersAsync()
    const artifact = await exportPromise
    const html = await artifact.blob.text()

    expect(html).not.toMatch(/<script\b|<img\b/i)
    expect(html).toContain('&lt;/title&gt;&lt;script&gt;unexpected()&lt;/script&gt;')
    expect(html).toContain('&lt;/pre&gt;&lt;img src=x onerror=unexpected()&gt;')
  })
})

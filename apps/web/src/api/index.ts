import type { WorkbenchApi } from './client'
import { createHttpApiClient } from './httpClient'
import { mockApiClient } from './mockClient'

export const apiMode = import.meta.env.VITE_USE_MOCK_API === 'true' ? 'mock' : 'http'

// Mock 必须显式开启；默认连接本机 FastAPI，避免误把演示数据当成真实报告。
export const apiClient: WorkbenchApi = apiMode === 'mock'
  ? mockApiClient
  : createHttpApiClient(import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api')

export type { WorkbenchApi } from './client'
export * from './types'

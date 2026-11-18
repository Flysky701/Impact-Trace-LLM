import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../src/api'

afterEach(() => vi.unstubAllGlobals())
describe('API transport', () => {
  it('sends same-origin cookies and the mutation header', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"ok":true}', { status: 200 }))
    vi.stubGlobal('fetch', fetch)
    expect(await api('/projects', 'POST', { name: 'Demo' })).toEqual({ ok: true })
    expect(fetch).toHaveBeenCalledWith('/api/projects', expect.objectContaining({
      method: 'POST', credentials: 'same-origin', body: '{"name":"Demo"}',
      headers: expect.objectContaining({ 'X-Requested-With': 'ImpactTrace' }),
    }))
  })
  it('handles logout responses without parsing a body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
    expect(await api('/auth/logout', 'POST')).toBeUndefined()
  })
  it('keeps server errors readable and their status available', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"detail":"请登录"}', { status: 401 })))
    await expect(api('/auth/me')).rejects.toMatchObject({ status: 401, message: '请登录' })
  })
  it.each(['{"detail":[]}', 'not json'])('handles invalid error payload %s', async body => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 500 })))
    await expect(api('/projects')).rejects.toThrow('请求未完成')
  })
  it('explains a disconnected backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network')))
    await expect(api('/health')).rejects.toBeInstanceOf(ApiError)
    await expect(api('/health')).rejects.toThrow('无法连接服务')
  })
})

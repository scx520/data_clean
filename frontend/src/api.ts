export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers)
  if (options?.body && !(options.body instanceof FormData))
    headers.set('Content-Type', 'application/json')
  const response = await fetch(`/api${path}`, { ...options, headers })
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const error = await response.json()
      message = typeof error.detail === 'string' ? error.detail : '配置内容不完整，请检查后重试'
    } catch {
      /* Retain HTTP status if response is not JSON. */
    }
    throw new Error(message)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

export async function download(path: string, filename: string) {
  const response = await fetch(`/api${path}`)
  if (!response.ok) throw new Error('下载失败，请稍后重试')
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

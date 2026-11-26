import { signOutEverywhere, supabase } from '@/lib/supabase'
import type { ApiErrorBody } from '@/types/api'

const BASE = `${import.meta.env.VITE_API_URL ?? ''}/api/v1`

export class ApiError extends Error {
  status: number
  code: string
  details: unknown
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

type Query = Record<string, string | number | boolean | string[] | null | undefined>

function buildUrl(path: string, query?: Query) {
  const url = new URL(BASE + path, window.location.origin)
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v === undefined || v === null || v === '') continue
    if (Array.isArray(v)) v.forEach((item) => url.searchParams.append(k, item))
    else url.searchParams.set(k, String(v))
  }
  return url.toString()
}

export async function api<T>(
  path: string,
  init: { method?: string; body?: unknown; query?: Query; signal?: AbortSignal } = {},
): Promise<T> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  const res = await fetch(buildUrl(path, init.query), {
    method: init.method ?? 'GET',
    signal: init.signal,
    headers: {
      ...(init.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  })

  if (res.ok) return (res.status === 204 ? undefined : await res.json()) as T

  let body: ApiErrorBody | null = null
  try {
    body = (await res.json()) as ApiErrorBody
  } catch {
    /* corpo não-JSON */
  }
  if (res.status === 401 || res.status === 403) {
    await signOutEverywhere()
  }
  throw new ApiError(
    res.status,
    body?.error.code ?? 'http_error',
    body?.error.message ?? 'Não foi possível concluir a operação.',
    body?.error.details,
  )
}

/** Baixa um arquivo da API com a sessão do proprietário (link simples não leva o token). */
export async function apiDownload(path: string, query?: Query): Promise<string> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  const res = await fetch(buildUrl(path, query), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) {
    let message = 'Não foi possível gerar o arquivo.'
    try {
      message = ((await res.json()) as ApiErrorBody).error.message
    } catch {
      /* corpo não-JSON */
    }
    throw new ApiError(res.status, 'download_failed', message)
  }
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? 'finance-hub.csv'
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return name
}

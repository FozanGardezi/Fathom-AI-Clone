import { api, tokens } from './client'
import type { User } from './types'

export async function login(email: string, password: string) {
  const { data } = await api.post('/auth/login/', { email, password })
  tokens.set(data.access, data.refresh)
  return data
}

export async function register(email: string, full_name: string, password: string) {
  const { data } = await api.post('/auth/register/', { email, full_name, password })
  return data
}

export function logout() {
  tokens.clear()
}

export async function fetchMe(): Promise<User> {
  const { data } = await api.get('/me/')
  return data
}

export async function fetchHealth() {
  const { data } = await api.get('/health/')
  return data as { status: string; database: string }
}

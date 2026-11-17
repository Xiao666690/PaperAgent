import type { LoginResponse } from '@/types/type'
import api from '@/api/api'
import { clearSession } from '@/services/session'

export const register = async (
  user: { username: string; password: string; teamName?: string },
) => {
  try {
    const response = await api.post(
      '/register',
      { username: user.username, password: user.password, team_name: user.teamName ?? '' },
      { timeout: 10000 },
    )
    return response.data
  } catch (error: any) {
    throw new Error(error?.response?.data?.detail || error?.response?.data?.msg || '注册失败，请稍后重试')
  }
}

export const login = async (user: { username: string; password: string }): Promise<LoginResponse> => {
  let response: LoginResponse
  try {
    response = (await api.post<LoginResponse>('/login', user)).data
  } catch (e: any) {
    throw new Error(e?.response?.data?.msg || e?.response?.data?.detail || '登录失败，请检查服务器连接')
  }
  const session = response.data
  if (!session?.access_token) throw new Error('服务器未返回登录凭证')
  clearSession()
  localStorage.setItem('token', session.access_token)
  localStorage.setItem('username', user.username)
  if (session.expire) localStorage.setItem('tokenExpiresAt', String(session.expire))
  if (session.role) localStorage.setItem('role', session.role)
  if (session.workspace_lid) localStorage.setItem('workspaceLid', session.workspace_lid)
  return response
}

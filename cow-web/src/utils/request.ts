import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

declare module 'axios' {
  export interface AxiosRequestConfig {
    /** 静默请求：失败时拦截器不弹全局错误提示（用于轮询/装饰性调用） */
    silent?: boolean
  }
}

export interface Result<T = any> {
  code: number
  message: string
  data: T
}

export interface PageResult<T = any> {
  records: T[]
  total: number
  page: number
  size: number
}

const request: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 15000
})

// token 拦截
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Result 解包 + 401 跳登录
request.interceptors.response.use(
  (response) => {
    const body = response.data as Result
    if (body && typeof body.code === 'number') {
      if (body.code === 200) {
        return body.data
      }
      if (!response.config.silent) {
        ElMessage.error(body.message || '请求失败')
      }
      return Promise.reject(new Error(body.message))
    }
    return body
  },
  (error) => {
    const status = error.response?.status
    if (status === 401) {
      localStorage.removeItem('token')
      if (router.currentRoute.value.path !== '/login') {
        ElMessage.warning('登录已过期，请重新登录')
        router.push('/login')
      }
    } else if (status === 409) {
      ElMessage.error(error.response?.data?.message || '数据已被他人修改，请刷新后重试')
    } else if (!error.config?.silent) {
      ElMessage.error(error.response?.data?.message || error.message || '网络异常')
    }
    return Promise.reject(error)
  }
)

export function get<T = any>(url: string, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<T> {
  return request.get(url, { params, ...config }) as unknown as Promise<T>
}

export function post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
  return request.post(url, data, config) as unknown as Promise<T>
}

export function put<T = any>(url: string, data?: any): Promise<T> {
  return request.put(url, data) as unknown as Promise<T>
}

export function del<T = any>(url: string): Promise<T> {
  return request.delete(url) as unknown as Promise<T>
}

export default request

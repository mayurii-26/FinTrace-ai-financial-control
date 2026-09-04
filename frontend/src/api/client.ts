import axios from 'axios';
import { supabase } from '../lib/supabase';

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

if (!BASE_URL) {
  console.warn('[FinTrace] VITE_API_BASE_URL is not set. API calls will fail.');
}

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

// ── Request interceptor: attach Supabase JWT when a session exists ────────────
api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// ── Response interceptor: normalise error messages ────────────────────────────
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg =
      (err.response?.data as { detail?: string; message?: string } | undefined)?.detail ??
      (err.response?.data as { detail?: string; message?: string } | undefined)?.message ??
      err.message ??
      'Unknown error';
    return Promise.reject(new Error(String(msg)));
  },
);

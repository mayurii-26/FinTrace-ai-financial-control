import { api } from './client';
import type {
  DashboardKPI,
  BenchmarkResult,
  ExceptionListItem,
  ExceptionDetail,
  LifecycleTrace,
  InvestigateResponse,
  ActionResponse,
  ControllerAction,
  VerificationResult,
  AuditLogEntry,
} from './types';

export const fetchDashboard = () =>
  api.get<DashboardKPI>('/dashboard').then((r) => r.data);

export const fetchBenchmark = () =>
  api.get<BenchmarkResult>('/benchmark').then((r) => r.data);

export const fetchExceptions = (params?: {
  exception_type?: string;
  severity?: string;
  status?: string;
  limit?: number;
  offset?: number;
}) => api.get<ExceptionListItem[]>('/exceptions', { params }).then((r) => r.data);

export const fetchExceptionDetail = (id: string) =>
  api.get<ExceptionDetail>(`/exceptions/${id}`).then((r) => r.data);

export const fetchLifecycleTrace = (transactionId: string) =>
  api.get<LifecycleTrace>(`/transactions/${transactionId}/trace`).then((r) => r.data);

export const runInvestigation = (exceptionId: string, provider = 'mock') =>
  api
    .post<InvestigateResponse>(`/exceptions/${exceptionId}/investigate`, { provider })
    .then((r) => r.data);

export const applyAction = (
  exceptionId: string,
  action: ControllerAction,
  actor = 'controller',
  notes?: string
) =>
  api
    .post<ActionResponse>(`/exceptions/${exceptionId}/action`, { action, actor, notes })
    .then((r) => r.data);

export const verifyException = (exceptionId: string) =>
  api.post<VerificationResult>(`/exceptions/${exceptionId}/verify`).then((r) => r.data);

export const fetchAuditTrail = (transactionId: string) =>
  api.get<AuditLogEntry[]>(`/audit/${transactionId}`).then((r) => r.data);

export const fetchRecentAudit = (params?: {
  action?: string;
  exception_id?: string;
  limit?: number;
}) => api.get<AuditLogEntry[]>('/audit', { params }).then((r) => r.data);

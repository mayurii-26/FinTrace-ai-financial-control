import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './components';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Layout } from './components/Layout';
import { AuthProvider } from './context/AuthContext';

// Pages
import { Landing }      from './pages/Landing';
import { Login }        from './pages/Login';
import { Register }     from './pages/Register';
import { ControlCenter } from './pages/ControlCenter';
import { Exceptions }   from './pages/Exceptions';
import { Investigation } from './pages/Investigation';
import { AuditTrail }   from './pages/AuditTrail';

export const App: React.FC = () => (
  <AuthProvider>
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          {/* ── Public routes ─────────────────────────────── */}
          <Route path="/" element={<Landing />} />
          <Route path="/login"    element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* ── Protected application shell ───────────────── */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            {/* /dashboard → Control Center */}
            <Route path="dashboard"    element={<ControlCenter />} />

            {/* Exceptions list */}
            <Route path="exceptions"   element={<Exceptions />} />

            {/* Investigation — no direct nav, redirect */}
            <Route path="investigation" element={<Navigate to="/exceptions" replace />} />
            <Route path="investigation/:exceptionId" element={<Investigation />} />

            {/* Audit trail */}
            <Route path="audit" element={<AuditTrail />} />
          </Route>

          {/* ── Fallback ──────────────────────────────────── */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  </AuthProvider>
);

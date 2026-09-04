import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, AlertTriangle, GitBranch, BookOpen, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const NAV = [
  { to: '/dashboard',    label: 'Control Center', icon: <LayoutDashboard className="h-[15px] w-[15px]" />, end: true  },
  { to: '/exceptions',   label: 'Exceptions',     icon: <AlertTriangle   className="h-[15px] w-[15px]" />, end: false },
  { to: '/investigation',label: 'Investigation',  icon: <GitBranch       className="h-[15px] w-[15px]" />, end: false },
  { to: '/audit',        label: 'Audit Trail',    icon: <BookOpen        className="h-[15px] w-[15px]" />, end: false },
];

export const Layout: React.FC = () => {
  const { user, signOut } = useAuth();

  const handleSignOut = async () => {
    try { await signOut(); } catch { /* ignore */ }
  };

  // Derive a display name: use email prefix or full email
  const displayEmail = user?.email ?? '';
  const displayName  = displayEmail.split('@')[0] ?? 'User';

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* ── Sidebar ─────────────────────────────────────────── */}
      <aside className="w-[220px] shrink-0 flex flex-col bg-white border-r border-slate-200">

        {/* Brand */}
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 bg-blue-600 rounded-lg flex items-center justify-center shrink-0 shadow-sm">
              <span className="text-white font-bold text-sm leading-none select-none">FT</span>
            </div>
            <div>
              <div className="text-[16px] font-bold text-slate-900 leading-tight tracking-tight">FinTrace</div>
              <div className="text-[11px] text-slate-400 leading-tight font-medium tracking-wide">Operations Center</div>
            </div>
          </div>
        </div>

        {/* Nav group label */}
        <div className="px-5 pt-5 pb-1">
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">Navigation</span>
        </div>

        {/* Nav items */}
        <nav className="flex-1 px-3 pb-4 space-y-0.5">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`
              }
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* User + sign out */}
        <div className="border-t border-slate-100 px-3 py-3 space-y-1">
          {/* User info */}
          <div className="flex items-center gap-2.5 px-3 py-2">
            <div className="h-7 w-7 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
              <span className="text-[11px] font-bold text-blue-700 uppercase select-none">
                {displayName.charAt(0)}
              </span>
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[12px] font-semibold text-slate-800 truncate capitalize">{displayName}</div>
              <div className="text-[10px] text-slate-400 truncate">{displayEmail}</div>
            </div>
          </div>

          {/* Sign out button */}
          <button
            onClick={handleSignOut}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] font-medium
              text-slate-500 hover:text-red-600 hover:bg-red-50 transition-colors"
          >
            <LogOut className="h-[15px] w-[15px]" />
            <span>Sign Out</span>
          </button>
        </div>

        {/* Version footer */}
        <div className="px-5 py-3 border-t border-slate-100">
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-green-500 shrink-0" />
            <span className="text-[11px] text-slate-400 font-medium">v1.1.0 · Live</span>
          </div>
        </div>
      </aside>

      {/* ── Main content area ────────────────────────────────── */}
      <main className="flex-1 overflow-auto min-w-0">
        <div className="max-w-[1320px] mx-auto px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

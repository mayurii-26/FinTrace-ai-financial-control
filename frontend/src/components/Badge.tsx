import React from 'react';

export type Variant =
  | 'low' | 'medium' | 'high' | 'critical'
  | 'success' | 'warning' | 'info' | 'neutral'
  | 'open' | 'approved' | 'rejected' | 'escalated' | 'auto_resolved';

// dot color for severity indicators
const dotColor: Record<Variant, string> = {
  low:           'bg-slate-400',
  medium:        'bg-amber-500',
  high:          'bg-orange-500',
  critical:      'bg-red-500',
  success:       'bg-emerald-500',
  warning:       'bg-yellow-500',
  info:          'bg-blue-500',
  neutral:       'bg-slate-400',
  open:          'bg-blue-500',
  approved:      'bg-emerald-500',
  rejected:      'bg-red-500',
  escalated:     'bg-purple-500',
  auto_resolved: 'bg-teal-500',
};

const variantStyles: Record<Variant, string> = {
  low:           'bg-slate-100  text-slate-700  border-slate-300',
  medium:        'bg-amber-50   text-amber-800  border-amber-300',
  high:          'bg-orange-50  text-orange-800 border-orange-300',
  critical:      'bg-red-50     text-red-800    border-red-400',
  success:       'bg-emerald-50 text-emerald-800 border-emerald-300',
  warning:       'bg-yellow-50  text-yellow-800 border-yellow-300',
  info:          'bg-blue-50    text-blue-800   border-blue-300',
  neutral:       'bg-slate-100  text-slate-600  border-slate-300',
  open:          'bg-blue-50    text-blue-800   border-blue-300',
  approved:      'bg-emerald-50 text-emerald-800 border-emerald-300',
  rejected:      'bg-red-50     text-red-800    border-red-300',
  escalated:     'bg-purple-50  text-purple-800 border-purple-300',
  auto_resolved: 'bg-teal-50    text-teal-800   border-teal-300',
};

interface BadgeProps {
  variant: Variant;
  children: React.ReactNode;
  className?: string;
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({ variant, children, className = '', dot = false }) => (
  <span
    className={`inline-flex items-center gap-1 px-2 py-[2px] text-[11px] font-semibold
      uppercase tracking-wide rounded border whitespace-nowrap
      ${variantStyles[variant] ?? variantStyles.neutral} ${className}`}
  >
    {dot && (
      <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${dotColor[variant] ?? 'bg-slate-400'}`} />
    )}
    {children}
  </span>
);

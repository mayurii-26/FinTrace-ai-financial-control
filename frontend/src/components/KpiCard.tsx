import React from 'react';

interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  icon?: React.ReactNode;
  accent?: 'default' | 'green' | 'red' | 'amber' | 'blue';
  large?: boolean;
}

const valueColor: Record<string, string> = {
  default: 'text-slate-900',
  green:   'text-emerald-600',
  red:     'text-red-600',
  amber:   'text-amber-600',
  blue:    'text-blue-600',
};

const iconStyle: Record<string, string> = {
  default: 'text-slate-400 bg-slate-100',
  green:   'text-emerald-600 bg-emerald-50',
  red:     'text-red-600 bg-red-50',
  amber:   'text-amber-600 bg-amber-50',
  blue:    'text-blue-600 bg-blue-50',
};

const leftAccent: Record<string, string> = {
  default: 'border-l-slate-300',
  green:   'border-l-emerald-500',
  red:     'border-l-red-500',
  amber:   'border-l-amber-500',
  blue:    'border-l-blue-600',
};

export const KpiCard: React.FC<KpiCardProps> = ({
  label, value, sub, icon, accent = 'default', large = false,
}) => (
  <div className={`bg-white border border-slate-200 border-l-[3px] rounded-xl px-5 py-4 shadow-sm ${leftAccent[accent]}`}>
    {/* Label + icon row */}
    <div className="flex items-start justify-between gap-3 mb-3">
      <span className="stat-label leading-tight">{label}</span>
      {icon && (
        <span className={`h-7 w-7 rounded-lg flex items-center justify-center shrink-0 ${iconStyle[accent]}`}>
          {icon}
        </span>
      )}
    </div>

    {/* Value */}
    <div className={`font-bold font-mono tabular-nums leading-none tracking-tight ${valueColor[accent]} ${
      large ? 'text-[36px]' : 'text-[32px]'
    }`}>
      {value}
    </div>

    {/* Sub label */}
    {sub && (
      <div className="text-[12px] text-slate-400 mt-2 font-medium">{sub}</div>
    )}
  </div>
);

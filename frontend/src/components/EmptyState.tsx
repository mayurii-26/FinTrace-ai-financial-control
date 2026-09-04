import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ title, description, action, icon }) => (
  <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
    <div className="text-slate-300">{icon ?? <Inbox className="h-10 w-10" />}</div>
    <p className="text-sm font-medium text-slate-700">{title}</p>
    {description && <p className="text-xs text-slate-400 max-w-xs">{description}</p>}
    {action}
  </div>
);

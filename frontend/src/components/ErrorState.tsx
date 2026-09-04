import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({ message, onRetry }) => (
  <div className="flex flex-col items-center justify-center py-16 gap-4">
    <AlertTriangle className="h-10 w-10 text-red-500" />
    <p className="text-sm text-slate-700 font-medium">Something went wrong</p>
    <p className="text-xs text-slate-400 max-w-xs text-center">{message}</p>
    {onRetry && (
      <button onClick={onRetry} className="btn-ghost mt-2">
        <RefreshCw className="h-4 w-4" /> Retry
      </button>
    )}
  </div>
);

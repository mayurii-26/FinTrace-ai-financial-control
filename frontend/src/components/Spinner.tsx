import React from 'react';

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const Spinner: React.FC<SpinnerProps> = ({ size = 'md', className = '' }) => {
  const sizes = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-10 w-10' };
  return (
    <div
      className={`${sizes[size]} border-2 border-slate-200 border-t-blue-600 rounded-full animate-spin ${className}`}
    />
  );
};

export const LoadingState: React.FC<{ message?: string }> = ({ message = 'Loading…' }) => (
  <div className="flex flex-col items-center justify-center py-20 gap-3">
    <Spinner size="lg" />
    <p className="text-sm text-slate-400">{message}</p>
  </div>
);

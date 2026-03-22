import React, { useEffect } from 'react';

interface Props {
  message: string;
  type: 'info' | 'success' | 'error';
  onClose: () => void;
}

export const Toast: React.FC<Props> = ({ message, type, onClose }) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const bgColors = {
    info: 'bg-purple',
    success: 'bg-success',
    error: 'bg-error',
  };

  return (
    <div className={`fixed top-4 left-1/2 transform -translate-x-1/2 ${bgColors[type]} text-white px-6 py-4 rounded-2xl shadow-lg z-50 fade-in`}>
      <div className="flex items-center gap-3">
        <span className="text-xl">{message}</span>
        <button onClick={onClose} className="text-2xl hover:scale-110 transition-transform">✕</button>
      </div>
    </div>
  );
};

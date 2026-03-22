import React from 'react';

interface Props {
  isOpen: boolean;
  hint: string;
  onToggle: () => void;
  onShowHint: () => void;
}

export const HintPanel: React.FC<Props> = ({ isOpen, hint, onToggle, onShowHint }) => {
  return (
    <div className="card">
      <button
        onClick={onToggle}
        className="w-full flex justify-between items-center text-left"
      >
        <h2 className="text-xl font-bold text-dark-blue">🦉 Need a Hint?</h2>
        <span className="text-2xl">{isOpen ? '▼' : '▶'}</span>
      </button>
      
      {isOpen && (
        <div className="mt-4 fade-in">
          <p className="text-lg text-purple mb-4">{hint}</p>
          <button
            onClick={onShowHint}
            className="w-full btn-secondary text-lg"
          >
            ✨ Show me!
          </button>
        </div>
      )}
    </div>
  );
};

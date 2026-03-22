import React from 'react';
import { ScoreRating } from '../types';
import { getRatingMessage } from '../utils/chessHelpers';

interface Props {
  isOpen: boolean;
  score: ScoreRating;
  onToggle: () => void;
}

export const AnalysisPanel: React.FC<Props> = ({ isOpen, score, onToggle }) => {
  const getBadge = () => {
    if (!score) return null;
    
    const configs = {
      awesome: { bg: 'bg-success', emoji: '🌟', text: 'AWESOME MOVE!' },
      okay: { bg: 'bg-warning', emoji: '🤔', text: 'OKAY MOVE' },
      mistake: { bg: 'bg-error', emoji: '🔴', text: 'OOPS! MISTAKE' },
    };
    
    const config = configs[score];
    return (
      <div className={`${config.bg} text-white p-4 rounded-2xl text-center`}>
        <div className="text-4xl mb-2">{config.emoji}</div>
        <div className="text-xl font-bold">{config.text}</div>
        <div className="text-sm mt-2">{getRatingMessage(score)}</div>
      </div>
    );
  };

  return (
    <div className="card">
      <button
        onClick={onToggle}
        className="w-full flex justify-between items-center text-left"
      >
        <h2 className="text-xl font-bold text-dark-blue">📊 My Score!</h2>
        <span className="text-2xl">{isOpen ? '▼' : '▶'}</span>
      </button>
      
      {isOpen && (
        <div className="mt-4 fade-in">
          {score ? (
            getBadge()
          ) : (
            <p className="text-gray-500 text-center py-4">Make a move to see your score! 🎯</p>
          )}
        </div>
      )}
    </div>
  );
};

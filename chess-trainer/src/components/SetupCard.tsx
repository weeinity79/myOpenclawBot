import React from 'react';
import { OpeningType, PlayerSide } from '../types';
import { openings } from '../data/openings';

interface Props {
  selectedOpening: OpeningType | null;
  playerSide: PlayerSide | null;
  onOpeningChange: (opening: OpeningType) => void;
  onSideChange: (side: PlayerSide) => void;
  onStart: () => void;
}

export const SetupCard: React.FC<Props> = ({
  selectedOpening,
  playerSide,
  onOpeningChange,
  onSideChange,
  onStart,
}) => {
  const canStart = selectedOpening && playerSide;

  return (
    <div className="card">
      <h2 className="text-2xl font-bold text-dark-blue mb-4">🏰 Choose Your Adventure!</h2>
      
      <div className="mb-4">
        <label className="block text-lg font-semibold text-purple mb-2">Pick an Opening:</label>
        <div className="space-y-2">
          {openings.map((opening) => (
            <button
              key={opening.id}
              onClick={() => onOpeningChange(opening.id)}
              className={`w-full text-left p-3 rounded-2xl transition-all duration-200 ${
                selectedOpening === opening.id
                  ? 'bg-grass-green text-white shadow-md'
                  : 'bg-gray-100 text-dark-blue hover:bg-gray-200'
              }`}
            >
              <span className="font-bold">{opening.name}</span>
              <span className="ml-2">{opening.description}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="mb-4">
        <label className="block text-lg font-semibold text-purple mb-2">You Play:</label>
        <div className="flex gap-3">
          <button
            onClick={() => onSideChange('white')}
            className={`flex-1 btn-toggle ${
              playerSide === 'white'
                ? 'bg-white text-black border-4 border-grass-green'
                : 'bg-gray-200 text-gray-600'
            }`}
          >
            ♔ I am WHITE
          </button>
          <button
            onClick={() => onSideChange('black')}
            className={`flex-1 btn-toggle ${
              playerSide === 'black'
                ? 'bg-black text-white border-4 border-grass-green'
                : 'bg-gray-200 text-gray-600'
            }`}
          >
            ♚ I am BLACK
          </button>
        </div>
      </div>

      <button
        onClick={onStart}
        disabled={!canStart}
        className={`w-full py-4 text-xl font-bold rounded-2xl transition-all duration-200 ${
          canStart
            ? 'btn-primary bounce'
            : 'bg-gray-300 text-gray-500 cursor-not-allowed'
        }`}
      >
        🎮 Start Playing!
      </button>
    </div>
  );
};

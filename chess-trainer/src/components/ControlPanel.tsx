import React from 'react';
import { SetupCard } from './SetupCard';
import { HintPanel } from './HintPanel';
import { AnalysisPanel } from './AnalysisPanel';
import { OpeningType, PlayerSide, ScoreRating } from '../types';
import { openings } from '../data/openings';

interface Props {
  gameStarted: boolean;
  selectedOpening: OpeningType | null;
  playerSide: PlayerSide | null;
  hintOpen: boolean;
  currentHint: string;
  analysisOpen: boolean;
  lastMoveScore: ScoreRating;
  isBotThinking: boolean;
  onOpeningChange: (opening: OpeningType) => void;
  onSideChange: (side: PlayerSide) => void;
  onStart: () => void;
  onToggleHint: () => void;
  onShowHint: () => void;
  onToggleAnalysis: () => void;
  onReset: () => void;
}

export const ControlPanel: React.FC<Props> = ({
  gameStarted,
  selectedOpening,
  playerSide,
  hintOpen,
  currentHint,
  analysisOpen,
  lastMoveScore,
  isBotThinking,
  onOpeningChange,
  onSideChange,
  onStart,
  onToggleHint,
  onShowHint,
  onToggleAnalysis,
  onReset,
}) => {
  if (!gameStarted) {
    return (
      <div className="h-full overflow-auto">
        <SetupCard
          selectedOpening={selectedOpening}
          playerSide={playerSide}
          onOpeningChange={onOpeningChange}
          onSideChange={onSideChange}
          onStart={onStart}
        />
      </div>
    );
  }

  const currentOpeningName = selectedOpening 
    ? openings.find(o => o.id === selectedOpening)?.name || ''
    : '';

  return (
    <div className="h-full overflow-auto flex flex-col gap-4">
      <div className="card bg-sunny-yellow">
        <div className="text-center">
          <span className="text-lg font-bold text-dark-blue">
            {currentOpeningName} - You are {playerSide === 'white' ? '♔ WHITE' : '♚ BLACK'}
          </span>
        </div>
      </div>

      {isBotThinking && (
        <div className="card bg-purple pulse-glow">
          <div className="text-center text-white">
            <span className="text-xl font-bold">🤖 Bot is thinking...</span>
          </div>
        </div>
      )}

      <HintPanel
        isOpen={hintOpen}
        hint={currentHint}
        onToggle={onToggleHint}
        onShowHint={onShowHint}
      />

      <AnalysisPanel
        isOpen={analysisOpen}
        score={lastMoveScore}
        onToggle={onToggleAnalysis}
      />

      <button
        onClick={onReset}
        className="w-full btn-primary text-xl"
      >
        🔄 Play Again!
      </button>
    </div>
  );
};

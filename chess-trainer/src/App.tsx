import React, { useState } from 'react';
import { ChessBoard } from './components/ChessBoard';
import { ControlPanel } from './components/ControlPanel';
import { Toast } from './components/Toast';
import { ErrorBoundary } from './components/ErrorBoundary';
import { useGame } from './hooks/useGame';
import { OpeningType, PlayerSide } from './types';

const AppContent: React.FC = () => {
  const {
    state,
    startGame,
    onPlayerMove,
    showHint,
    resetGame,
    clearToast,
    toggleHintPanel,
    toggleAnalysisPanel,
  } = useGame();

  const [tempOpening, setTempOpening] = useState<OpeningType | null>(null);
  const [tempSide, setTempSide] = useState<PlayerSide | null>(null);

  // Sync with useGame state
  React.useEffect(() => {
    if (state.selectedOpening) setTempOpening(state.selectedOpening);
    if (state.playerSide) setTempSide(state.playerSide);
  }, [state.selectedOpening, state.playerSide]);

  return (
    <div className="min-h-screen bg-sky-blue p-4">
      <div className="max-w-[1400px] mx-auto h-[calc(100vh-2rem)] lg:h-screen flex flex-col">
        <header className="text-center py-2">
          <h1 className="text-3xl md:text-4xl font-bold text-dark-blue drop-shadow-sm">
            ♟️ Chess Opening Trainer ♟️
          </h1>
        </header>

        <div className="flex-1 flex flex-col lg:flex-row gap-4 min-h-0">
          <div className="lg:w-[60%] h-[50vh] lg:h-full">
            <ChessBoard
              game={state.game}
              onMove={onPlayerMove}
              isShaking={state.isShaking}
              arrowFrom={state.arrowFrom}
              arrowTo={state.arrowTo}
              playerSide={state.playerSide}
            />
          </div>

          <div className="lg:w-[40%] h-[50vh] lg:h-full">
            <ControlPanel
              gameStarted={state.gameStarted}
              selectedOpening={tempOpening}
              playerSide={tempSide}
              hintOpen={state.hintOpen}
              currentHint={state.currentHint}
              analysisOpen={state.analysisOpen}
              lastMoveScore={state.lastMoveScore}
              isBotThinking={state.isBotThinking}
              onOpeningChange={setTempOpening}
              onSideChange={setTempSide}
              onStart={() => {
                if (tempOpening && tempSide) {
                  startGame(tempOpening, tempSide);
                }
              }}
              onToggleHint={toggleHintPanel}
              onShowHint={showHint}
              onToggleAnalysis={toggleAnalysisPanel}
              onReset={resetGame}
            />
          </div>
        </div>
      </div>

      {state.toast && (
        <Toast
          message={state.toast.message}
          type={state.toast.type}
          onClose={clearToast}
        />
      )}
    </div>
  );
};

const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <AppContent />
    </ErrorBoundary>
  );
};

export default App;

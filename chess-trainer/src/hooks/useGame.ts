import { useState, useCallback, useRef, useEffect } from 'react';
import { Chess } from 'chess.js';
import type { OpeningType, PlayerSide, AppState } from '../types';

export const useGame = () => {
  const [state, setState] = useState<AppState>({
    selectedOpening: null,
    playerSide: null,
    gameStarted: false,
    game: null,
    phase: 'setup',
    bookIndex: 0,
    isBotThinking: false,
    hintOpen: false,
    currentHint: '',
    showArrow: false,
    arrowFrom: null,
    arrowTo: null,
    analysisOpen: false,
    lastMoveScore: null,
    resetKey: 0,
    toast: null,
    isShaking: false,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const gameRef = useRef<any>(null);
  const playerSideRef = useRef<PlayerSide | null>(null);
  const isBotMovingRef = useRef<boolean>(false);

  // Bot makes a random valid move
  const botMove = useCallback(async () => {
    if (isBotMovingRef.current || !gameRef.current) return;
    isBotMovingRef.current = true;
    
    console.log('Bot thinking...');
    setState(prev => ({ ...prev, isBotThinking: true }));
    
    const game = gameRef.current;
    
    // Get all valid moves and pick one randomly
    const moves = game.moves();
    console.log('Valid moves:', moves.length);
    
    if (moves.length > 0) {
      const randomMove = moves[Math.floor(Math.random() * moves.length)];
      console.log('Bot move:', randomMove);
      
      try {
        game.move(randomMove);
        gameRef.current = new Chess(game.fen());
        
        setState(prev => ({ 
          ...prev, 
          game: new Chess(game.fen()), 
          isBotThinking: false 
        }));
        console.log('Bot moved successfully');
      } catch (err) {
        console.error('Failed to make bot move:', err);
        setState(prev => ({ ...prev, isBotThinking: false }));
      }
    } else {
      console.log('No valid moves');
      setState(prev => ({ ...prev, isBotThinking: false }));
    }
    
    isBotMovingRef.current = false;
  }, []);

  const startGame = useCallback((_opening: OpeningType, side: PlayerSide) => {
    const game = new Chess();
    gameRef.current = game;
    playerSideRef.current = side;
    isBotMovingRef.current = false;
    
    setState(prev => ({
      ...prev,
      selectedOpening: _opening,
      playerSide: side,
      gameStarted: true,
      game: new Chess(),
      phase: 'playing',
      bookIndex: 0,
      isBotThinking: false,
      hintOpen: false,
      currentHint: 'Make your move!',
      showArrow: false,
      arrowFrom: null,
      arrowTo: null,
      analysisOpen: false,
      lastMoveScore: null,
      toast: null,
      isShaking: false,
    }));
    
    if (side === 'black') {
      setTimeout(() => botMove(), 1000);
    }
  }, [botMove]);

  const onPlayerMove = useCallback(async (source: string, target: string) => {
    if (state.isBotThinking || !gameRef.current) return false;
    
    const game = gameRef.current;
    const result = game.move({ from: source, to: target, promotion: 'q' });
    
    if (!result) {
      setState(prev => ({ ...prev, isShaking: true }));
      setTimeout(() => setState(prev => ({ ...prev, isShaking: false })), 500);
      return false;
    }
    
    gameRef.current = new Chess(game.fen());
    setState(prev => ({ 
      ...prev, 
      game: new Chess(game.fen()),
      isShaking: false 
    }));
    
    console.log('Player moved, bot thinking...');
    setTimeout(() => botMove(), 500);
    return true;
  }, [state.isBotThinking, botMove]);

  const showHint = useCallback(() => {
    if (!gameRef.current) return;
    const moves = gameRef.current.moves();
    if (moves.length > 0) {
      const randomMove = moves[Math.floor(Math.random() * moves.length)];
      if (randomMove.length >= 4) {
        setState(prev => ({ 
          ...prev, 
          hintOpen: true, 
          showArrow: true, 
          arrowFrom: randomMove.substring(0, 2), 
          arrowTo: randomMove.substring(2, 4) 
        }));
      }
    }
  }, []);

  const resetGame = useCallback(() => {
    gameRef.current = null;
    playerSideRef.current = null;
    isBotMovingRef.current = false;
    
    setState(prev => ({ 
      selectedOpening: null, 
      playerSide: null, 
      gameStarted: false, 
      game: null,
      phase: 'setup', 
      bookIndex: 0, 
      isBotThinking: false, 
      hintOpen: false, 
      currentHint: '',
      showArrow: false, 
      arrowFrom: null, 
      arrowTo: null, 
      analysisOpen: false, 
      lastMoveScore: null,
      resetKey: prev.resetKey + 1, 
      toast: null, 
      isShaking: false 
    }));
  }, []);

  const clearToast = useCallback(() => setState(prev => ({ ...prev, toast: null })), []);
  const toggleHintPanel = useCallback(() => setState(prev => ({ ...prev, hintOpen: !prev.hintOpen })), []);
  const toggleAnalysisPanel = useCallback(() => setState(prev => ({ ...prev, analysisOpen: !prev.analysisOpen })), []);

  return { state, startGame, onPlayerMove, showHint, resetGame, clearToast, toggleHintPanel, toggleAnalysisPanel };
};

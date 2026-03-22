import { useState, useCallback, useRef } from 'react';
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
  const botMove = useCallback(() => {
    if (isBotMovingRef.current || !gameRef.current) {
      console.log('Bot blocked:', isBotMovingRef.current, !!gameRef.current);
      return;
    }
    isBotMovingRef.current = true;
    
    console.log('Bot thinking...');
    setState(s => ({ ...s, isBotThinking: true }));
    
    const game = gameRef.current;
    
    // Get all valid moves and pick one randomly
    const moves = game.moves();
    console.log('Valid moves count:', moves.length);
    
    if (moves.length > 0) {
      const randomMove = moves[Math.floor(Math.random() * moves.length)];
      console.log('Bot random move:', randomMove);
      
      try {
        const result = game.move(randomMove);
        console.log('Move result:', result);
        
        if (result) {
          gameRef.current = new Chess(game.fen());
          console.log('New FEN:', gameRef.current.fen());
          
          setState(s => ({ 
            ...s, 
            game: new Chess(game.fen()), 
            isBotThinking: false 
          }));
          console.log('Bot moved successfully');
        } else {
          console.log('Move failed');
          setState(s => ({ ...s, isBotThinking: false }));
        }
      } catch (err) {
        console.error('Error making bot move:', err);
        setState(s => ({ ...s, isBotThinking: false }));
      }
    } else {
      console.log('No valid moves - game over?');
      setState(s => ({ ...s, isBotThinking: false }));
    }
    
    isBotMovingRef.current = false;
  }, []);

  const startGame = useCallback((_opening: OpeningType, side: PlayerSide) => {
    console.log('Starting game:', _opening, side);
    const game = new Chess();
    gameRef.current = game;
    playerSideRef.current = side;
    isBotMovingRef.current = false;
    
    setState(s => ({
      ...s,
      selectedOpening: _opening,
      playerSide: side,
      gameStarted: true,
      game: game,
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
    
    // If player is BLACK, bot (WHITE) plays first
    if (side === 'black') {
      console.log('Player is black, bot moving first');
      setTimeout(() => botMove(), 1000);
    }
  }, [botMove]);

  const onPlayerMove = useCallback((source: string, target: string) => {
    console.log('Player move:', source, '->', target);
    
    if (isBotMovingRef.current) {
      console.log('Blocked - bot is thinking');
      return false;
    }
    
    if (!gameRef.current) {
      console.log('No game');
      return false;
    }
    
    const game = gameRef.current;
    const result = game.move({ from: source, to: target, promotion: 'q' });
    
    console.log('Player move result:', result);
    
    if (!result) {
      console.log('Invalid move');
      setState(s => ({ ...s, isShaking: true }));
      setTimeout(() => setState(s => ({ ...s, isShaking: false })), 500);
      return false;
    }
    
    // Update game state
    gameRef.current = new Chess(game.fen());
    console.log('New game FEN after player:', gameRef.current.fen());
    
    setState(s => ({ 
      ...s, 
      game: new Chess(game.fen()),
      isShaking: false 
    }));
    
    // Trigger bot move after a short delay
    console.log('Scheduling bot move...');
    setTimeout(() => {
      console.log('Calling botMove...');
      botMove();
    }, 600);
    
    return true;
  }, [botMove]);

  const showHint = useCallback(() => {
    if (!gameRef.current) return;
    const moves = gameRef.current.moves();
    if (moves.length > 0) {
      const randomMove = moves[Math.floor(Math.random() * moves.length)];
      if (randomMove.length >= 4) {
        setState(s => ({ 
          ...s, 
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
    
    setState(s => ({ 
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
      resetKey: s.resetKey + 1, 
      toast: null, 
      isShaking: false 
    }));
  }, []);

  const clearToast = useCallback(() => setState(s => ({ ...s, toast: null })), []);
  const toggleHintPanel = useCallback(() => setState(s => ({ ...s, hintOpen: !s.hintOpen })), []);
  const toggleAnalysisPanel = useCallback(() => setState(s => ({ ...s, analysisOpen: !s.analysisOpen })), []);

  return { state, startGame, onPlayerMove, showHint, resetGame, clearToast, toggleHintPanel, toggleAnalysisPanel };
};

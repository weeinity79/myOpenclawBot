import { useState, useCallback, useRef, useEffect } from 'react';
import { Chess } from 'chess.js';
import type { OpeningType, PlayerSide, AppState } from '../types';
import stockfish from 'stockfish.js';

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

  const stockfishRef = useRef<ReturnType<typeof stockfish> | null>(null);
  const gameRef = useRef<Chess | null>(null);
  const playerSideRef = useRef<PlayerSide | null>(null);
  const isBotMovingRef = useRef<boolean>(false);

  // Initialize Stockfish
  useEffect(() => {
    stockfishRef.current = stockfish();
    console.log('Stockfish initialized');
    
    return () => {
      stockfishRef.current?.terminate();
    };
  }, []);

  // Make a move with Stockfish
  const makeStockfishMove = useCallback(async (fen: string): Promise<string | null> => {
    return new Promise((resolve) => {
      if (!stockfishRef.current) { 
        console.log('Stockfish not ready');
        resolve(null); 
        return; 
      }
      
      let resolved = false;
      const timeoutId = setTimeout(() => {
        if (!resolved) {
          resolved = true;
          resolve(null);
        }
      }, 5000);
      
      stockfishRef.current.onmessage = (e: string | { type: string; data?: string }) => {
        const data = typeof e === 'string' ? e : e.data || '';
        console.log('Stockfish response:', data);
        
        if (data.includes('bestmove')) {
          if (!resolved) {
            resolved = true;
            clearTimeout(timeoutId);
            const move = data.split(' ')[1];
            console.log('Stockfish move:', move);
            resolve(move);
          }
        }
      };
      
      stockfishRef.current?.postMessage(`position fen ${fen}`);
      stockfishRef.current?.postMessage('go depth 3');
    });
  }, []);

  // Bot makes a move
  const botMove = useCallback(async () => {
    if (isBotMovingRef.current || !gameRef.current) return;
    isBotMovingRef.current = true;
    
    console.log('Bot thinking...');
    setState(prev => ({ ...prev, isBotThinking: true }));
    
    const game = gameRef.current;
    const fen = game.fen();
    console.log('Current FEN:', fen);
    
    const move = await makeStockfishMove(fen);
    
    if (move) {
      try {
        const result = game.move(move, { promotion: 'q' });
        if (result) {
          gameRef.current = new Chess(game.fen());
          setState(prev => ({ 
            ...prev, 
            game: new Chess(game.fen()), 
            isBotThinking: false 
          }));
          console.log('Bot moved!');
        } else {
          console.log('Failed to make bot move');
          setState(prev => ({ ...prev, isBotThinking: false }));
        }
      } catch (e) {
        console.error('Bot move error:', e);
        setState(prev => ({ ...prev, isBotThinking: false }));
      }
    } else {
      console.log('No move from Stockfish');
      setState(prev => ({ ...prev, isBotThinking: false }));
    }
    
    isBotMovingRef.current = false;
  }, [makeStockfishMove]);

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
      console.log('Player is black, bot moves first');
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

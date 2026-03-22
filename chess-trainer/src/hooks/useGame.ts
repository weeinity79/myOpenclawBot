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

  const stockfishRef = useRef<Worker | null>(null);
  const gameRef = useRef<Chess | null>(null);
  const playerSideRef = useRef<PlayerSide | null>(null);
  const isBotMovingRef = useRef<boolean>(false);

  // Initialize Stockfish from local file
  useEffect(() => {
    const initStockfish = () => {
      try {
        // Use local stockfish.js
        stockfishRef.current = new Worker('/stockfish.js');
        
        stockfishRef.current.onerror = (e) => {
          console.error('Stockfish error:', e);
        };
        
        stockfishRef.current.onmessage = (e) => {
          console.log('Stockfish:', e.data);
        };
        
        stockfishRef.current.postMessage('uci');
        
        // Wait for uciok
        const checkReady = setInterval(() => {
          if (stockfishRef.current) {
            stockfishRef.current.postMessage('isready');
          }
        }, 100);
        
        setTimeout(() => clearInterval(checkReady), 2000);
        
        console.log('Stockfish initializing...');
      } catch (error) {
        console.error('Failed to init Stockfish:', error);
      }
    };
    
    initStockfish();
    
    return () => {
      stockfishRef.current?.terminate();
    };
  }, []);

  // Bot makes a move using Stockfish
  const botMove = useCallback(async () => {
    if (isBotMovingRef.current || !gameRef.current) return;
    isBotMovingRef.current = true;
    
    console.log('Bot thinking...');
    setState(prev => ({ ...prev, isBotThinking: true }));
    
    const game = gameRef.current;
    const fen = game.fen();
    
    if (!stockfishRef.current) {
      console.log('No Stockfish');
      setState(prev => ({ ...prev, isBotThinking: false }));
      isBotMovingRef.current = false;
      return;
    }
    
    // Make move with Stockfish
    stockfishRef.current.postMessage(`position fen ${fen}`);
    stockfishRef.current.postMessage('go depth 3');
    
    const handleMessage = (e: MessageEvent) => {
      const data = e.data;
      console.log('Stockfish response:', data);
      
      if (data.includes('bestmove')) {
        stockfishRef.current?.removeEventListener('message', handleMessage);
        
        const move = data.split(' ')[1];
        console.log('Bot move:', move);
        
        if (move && move !== '(none)') {
          try {
            game.move(move, { promotion: 'q' });
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
          setState(prev => ({ ...prev, isBotThinking: false }));
        }
        
        isBotMovingRef.current = false;
      }
    };
    
    stockfishRef.current.addEventListener('message', handleMessage);
    
    // Timeout fallback
    setTimeout(() => {
      if (isBotMovingRef.current) {
        stockfishRef.current?.removeEventListener('message', handleMessage);
        isBotMovingRef.current = false;
        setState(prev => ({ ...prev, isBotThinking: false }));
        console.log('Bot move timeout');
      }
    }, 5000);
    
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

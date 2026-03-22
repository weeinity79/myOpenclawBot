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
  const stockfishRef = useRef<any>(null);
  const stockfishReadyRef = useRef<boolean>(false);

  // Initialize Stockfish WASM
  useEffect(() => {
    let sf: any = null;
    let initialized = false;
    
    const initStockfish = async () => {
      try {
        // Dynamic import the stockfish.wasm.js
        const module = await import('stockfish.js');
        sf = module.default();
        
        sf.onmessage = (event: any) => {
          if (event.type === 'uci') {
            stockfishReadyRef.current = true;
            console.log('Stockfish ready!');
          }
        };
        
        initialized = true;
        stockfishRef.current = sf;
      } catch (e) {
        console.error('Failed to load Stockfish:', e);
      }
    };
    
    initStockfish();
    
    return () => {
      if (sf) {
        try { sf.terminate(); } catch {}
      }
    };
  }, []);

  // Bot makes a smart move using Stockfish
  const botMove = useCallback(() => {
    if (isBotMovingRef.current || !gameRef.current) return;
    isBotMovingRef.current = true;
    
    console.log('Bot thinking with Stockfish...');
    setState(s => ({ ...s, isBotThinking: true }));
    
    const game = gameRef.current;
    const fen = game.fen();
    
    // Use Stockfish if available, otherwise random
    if (stockfishRef.current && stockfishReadyRef.current) {
      console.log('Using Stockfish for move...');
      
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const handleMessage = (event: any) => {
        const data = event.data;
        
        if (data && data.includes('bestmove')) {
          stockfishRef.current.removeListener('message', handleMessage);
          
          const move = data.split(' ')[1];
          console.log('Stockfish best move:', move);
          
          if (move && move !== '(none)') {
            try {
              game.move(move, { promotion: 'q' });
              gameRef.current = new Chess(game.fen());
              
              setState(s => ({ 
                ...s, 
                game: new Chess(game.fen()), 
                isBotThinking: false 
              }));
              console.log('Bot moved with Stockfish!');
            } catch (err) {
              console.error('Stockfish move failed:', err);
              // Fallback to random
              makeRandomMove();
            }
          } else {
            makeRandomMove();
          }
          isBotMovingRef.current = false;
        }
      };
      
      stockfishRef.current.addListener('message', handleMessage);
      stockfishRef.current.postMessage(`position fen ${fen}`);
      stockfishRef.current.postMessage('go depth 10');
      
      // Timeout fallback
      setTimeout(() => {
        if (isBotMovingRef.current) {
          stockfishRef.current?.removeListener('message', handleMessage);
          makeRandomMove();
        }
      }, 5000);
    } else {
      // Stockfish not ready, use random
      console.log('Stockfish not ready, using random');
      makeRandomMove();
    }
    
    function makeRandomMove() {
      const moves = game.moves();
      if (moves.length > 0) {
        const randomMove = moves[Math.floor(Math.random() * moves.length)];
        try {
          game.move(randomMove);
          gameRef.current = new Chess(game.fen());
          setState(s => ({ ...s, game: new Chess(game.fen()), isBotThinking: false }));
        } catch {
          setState(s => ({ ...s, isBotThinking: false }));
        }
      } else {
        setState(s => ({ ...s, isBotThinking: false }));
      }
      isBotMovingRef.current = false;
    }
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
    
    if (side === 'black') {
      console.log('Player is black, bot moving first');
      setTimeout(() => botMove(), 1000);
    }
  }, [botMove]);

  const onPlayerMove = useCallback((source: string, target: string) => {
    console.log('Player move:', source, '->', target);
    
    if (isBotMovingRef.current || !gameRef.current) return false;
    
    const game = gameRef.current;
    const result = game.move({ from: source, to: target, promotion: 'q' });
    
    if (!result) {
      setState(s => ({ ...s, isShaking: true }));
      setTimeout(() => setState(s => ({ ...s, isShaking: false })), 500);
      return false;
    }
    
    gameRef.current = new Chess(game.fen());
    setState(s => ({ ...s, game: new Chess(game.fen()), isShaking: false }));
    
    console.log('Scheduling bot move...');
    setTimeout(() => botMove(), 600);
    
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

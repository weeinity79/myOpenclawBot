import { useState, useCallback, useRef, useEffect } from 'react';
import { Chess } from 'chess.js';
import type { OpeningType, PlayerSide, AppState } from '../types';
import { getOpening } from '../data/openings';
import { getNextBookMoveForBot, isPlayerMoveBookCorrect } from '../utils/chessHelpers';

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
  const stockfishLoadedRef = useRef<boolean>(false);
  const gameRef = useRef<any>(null);

  // Initialize Stockfish with error handling
  useEffect(() => {
    const initStockfish = () => {
      try {
        stockfishRef.current = new Worker('https://cdn.jsdelivr.net/npm/stockfish.js@16.0.0/dist/stockfish.js');
        
        // Set up error handler
        stockfishRef.current.onerror = (error) => {
          console.error('Stockfish load error:', error);
          stockfishLoadedRef.current = false;
        };
        
        // Check if Stockfish is ready
        stockfishRef.current.onmessage = (e) => {
          if (e.data.includes('uciok')) {
            stockfishLoadedRef.current = true;
          }
        };
        
        stockfishRef.current.postMessage('uci');
      } catch (error) {
        console.error('Failed to initialize Stockfish:', error);
        stockfishLoadedRef.current = false;
      }
    };
    
    initStockfish();
    
    return () => {
      stockfishRef.current?.terminate();
      stockfishRef.current = null;
    };
  }, []);

  const playStockfishMove = async (game: any): Promise<string | null> => {
    return new Promise((resolve) => {
      if (!stockfishRef.current || !stockfishLoadedRef.current) { 
        resolve(null); 
        return; 
      }
      
      // Set up timeout (5 seconds max)
      const timeoutId = setTimeout(() => {
        stockfishRef.current?.removeEventListener('message', handler);
        resolve(null);
      }, 5000);
      
      stockfishRef.current.postMessage(`position fen ${game.fen()}`);
      stockfishRef.current.postMessage('go depth 5');
      
      const handler = (e: MessageEvent) => {
        if (e.data.includes('bestmove')) {
          clearTimeout(timeoutId);
          stockfishRef.current?.removeEventListener('message', handler);
          resolve(e.data.split(' ')[1]);
        }
      };
      stockfishRef.current.addEventListener('message', handler);
    });
  };

  const startGame = useCallback((opening: OpeningType, side: PlayerSide) => {
    const game = new Chess();
    gameRef.current = game;
    const openingData = getOpening(opening);
    setState(prev => ({
      ...prev, selectedOpening: opening, playerSide: side, gameStarted: true,
      game, phase: 'book', bookIndex: 0, isBotThinking: false,
      hintOpen: false, currentHint: openingData?.moves[0]?.hint || 'Make your move!',
      showArrow: false, arrowFrom: null, arrowTo: null, analysisOpen: false,
      lastMoveScore: null, toast: null, isShaking: false,
    }));
    // If player is BLACK, bot (WHITE) plays first
    if (side === 'black') setTimeout(() => playBotMove(opening, side), 500);
  }, []);

  const playBotMove = useCallback(async (opening: OpeningType, playerSide: PlayerSide) => {
    const game = gameRef.current;
    if (!game) return;
    
    setState(prev => ({ ...prev, isBotThinking: true }));
    
    const openingData = getOpening(opening);
    if (!openingData) {
      setState(prev => ({ ...prev, isBotThinking: false }));
      return;
    }
    
    const { move, newIndex, isBookMove } = getNextBookMoveForBot(game, openingData, playerSide);
    
    if (isBookMove && move) {
      try { 
        game.move(move); 
        gameRef.current = game;
        const newGame = new Chess(game.fen());
        const hintForNextMove = openingData.moves[newIndex]?.hint || '';
        setState(prev => ({ 
          ...prev, 
          game: newGame, 
          bookIndex: newIndex,
          isBotThinking: false, 
          hintOpen: true, 
          currentHint: hintForNextMove 
        }));
      } catch (error) { 
        console.error('Book move error:', error);
        setState(prev => ({ ...prev, isBotThinking: false })); 
      }
    } else {
      // Book exhausted or player deviated - use Stockfish
      if (!stockfishLoadedRef.current) {
        // Stockfish not available - show fallback message
        setState(prev => ({ 
          ...prev, 
          phase: 'stockfish', 
          isBotThinking: false,
          toast: { message: "🤖 Bot is taking a nap. Let's keep playing!", type: 'info' }
        }));
        return;
      }
      
      const best = await playStockfishMove(game);
      if (best) { 
        try {
          game.move(best); 
          gameRef.current = game;
          const newGame = new Chess(game.fen());
          setState(prev => ({ 
            ...prev, 
            game: newGame, 
            phase: 'stockfish', 
            isBotThinking: false, 
            hintOpen: false 
          })); 
        } catch (error) {
          console.error('Stockfish move error:', error);
          setState(prev => ({ 
            ...prev, 
            isBotThinking: false,
            toast: { message: "🤖 Bot got confused. Try again!", type: 'error' }
          }));
        }
      } else {
        setState(prev => ({ 
          ...prev, 
          isBotThinking: false,
          toast: { message: "🤖 Bot is thinking too long. Your turn!", type: 'info' }
        }));
      }
    }
  }, []);

  const onPlayerMove = useCallback(async (source: string, target: string) => {
    const { selectedOpening, playerSide, game } = state;
    if (!game || !selectedOpening || !playerSide) return false;
    
    const moveResult = game.move({ from: source, to: target, promotion: 'q' });
    if (!moveResult) { 
      setState(prev => ({ ...prev, isShaking: true }));
      setTimeout(() => setState(prev => ({ ...prev, isShaking: false })), 900); 
      return false; 
    }
    
    gameRef.current = game;
    const opening = getOpening(selectedOpening)!;
    const { isCorrect, newIndex } = isPlayerMoveBookCorrect(game, opening, moveResult.san);
    const newGame = new Chess(game.fen());
    
    setState(prev => ({ 
      ...prev, 
      game: newGame,
      phase: isCorrect && newIndex < opening.moves.length ? 'book' : 'stockfish',
      bookIndex: newIndex, 
      isShaking: false, 
      toast: null 
    }));
    
    // Bot responds after player moves
    setTimeout(() => playBotMove(selectedOpening, playerSide), 300);
    return true;
  }, [state, playBotMove]);

  const showHint = useCallback(() => {
    const { game, selectedOpening, phase, bookIndex } = state;
    if (!game || !selectedOpening) return;
    const opening = getOpening(selectedOpening)!;
    const isWhiteTurn = game.turn() === 'w';
    const hintMove = phase === 'book' && bookIndex < opening.moves.length
      ? (isWhiteTurn ? opening.moves[bookIndex].white : opening.moves[bookIndex].black) : '';
    if (hintMove && hintMove.length >= 4) {
      setState(prev => ({ 
        ...prev, 
        hintOpen: true, 
        showArrow: true, 
        arrowFrom: hintMove.substring(0, 2), 
        arrowTo: hintMove.substring(2, 4) 
      }));
    }
  }, [state]);

  const resetGame = useCallback(() => {
    stockfishRef.current?.terminate();
    
    // Reinitialize Stockfish
    try {
      stockfishRef.current = new Worker('https://cdn.jsdelivr.net/npm/stockfish.js@16.0.0/dist/stockfish.js');
      stockfishRef.current.postMessage('uci');
      stockfishLoadedRef.current = false;
      
      stockfishRef.current.onmessage = (e) => {
        if (e.data.includes('uciok')) {
          stockfishLoadedRef.current = true;
        }
      };
    } catch (error) {
      console.error('Failed to reinitialize Stockfish:', error);
    }
    
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

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
  const gameRef = useRef<Chess | null>(null);
  const selectedOpeningRef = useRef<OpeningType | null>(null);
  const playerSideRef = useRef<PlayerSide | null>(null);
  const isBotMovingRef = useRef<boolean>(false);

  // Initialize Stockfish
  useEffect(() => {
    const initStockfish = () => {
      try {
        stockfishRef.current = new Worker('https://cdn.jsdelivr.net/npm/stockfish.js@16.0.0/dist/stockfish.js');
        
        stockfishRef.current.onerror = (error) => {
          console.error('Stockfish load error:', error);
          stockfishLoadedRef.current = false;
        };
        
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

  // Get top 3 moves from Stockfish and pick one randomly
  const playStockfishMove = async (fen: string): Promise<string | null> => {
    return new Promise((resolve) => {
      if (!stockfishRef.current || !stockfishLoadedRef.current) { 
        resolve(null); 
        return; 
      }
      
      const timeoutId = setTimeout(() => {
        stockfishRef.current?.removeEventListener('message', handler);
        resolve(null);
      }, 8000);
      
      stockfishRef.current.postMessage('setoption name MultiPV value 3');
      stockfishRef.current.postMessage(`position fen ${fen}`);
      stockfishRef.current.postMessage('go depth 5');
      
      const moves: string[] = [];
      const handler = (e: MessageEvent) => {
        const data = e.data;
        
        if (data.includes('pv') && data.includes('multipv')) {
          const parts = data.split(' ');
          const pvIndex = parts.findIndex(p => p === 'pv');
          
          if (pvIndex !== -1 && pvIndex + 1 < parts.length) {
            const move = parts[pvIndex + 1];
            if (move && !moves.includes(move)) {
              moves.push(move);
            }
          }
        }
        
        if (moves.length >= 3 || data.includes('bestmove')) {
          clearTimeout(timeoutId);
          stockfishRef.current?.removeEventListener('message', handler);
          stockfishRef.current?.postMessage('setoption name MultiPV value 1');
          
          if (moves.length > 0) {
            const randomIndex = Math.floor(Math.random() * moves.length);
            resolve(moves[randomIndex]);
          } else {
            resolve(null);
          }
        }
      };
      stockfishRef.current.addEventListener('message', handler);
    });
  };

  const playBotMove = useCallback(async () => {
    // Prevent multiple bot moves at once
    if (isBotMovingRef.current) return;
    isBotMovingRef.current = true;
    
    const game = gameRef.current;
    const opening = selectedOpeningRef.current;
    const side = playerSideRef.current;
    
    if (!game || !opening || !side) {
      isBotMovingRef.current = false;
      return;
    }
    
    setState(prev => ({ ...prev, isBotThinking: true }));
    
    const openingData = getOpening(opening);
    if (!openingData) {
      setState(prev => ({ ...prev, isBotThinking: false }));
      isBotMovingRef.current = false;
      return;
    }
    
    const { move, newIndex, isBookMove } = getNextBookMoveForBot(game, openingData, side);
    
    if (isBookMove && move) {
      try { 
        const moveObj = game.move(move); 
        if (!moveObj) {
          console.error('Failed to make book move:', move);
          setState(prev => ({ ...prev, isBotThinking: false }));
          isBotMovingRef.current = false;
          return;
        }
        
        const fen = game.fen();
        const newGame = new Chess(fen);
        gameRef.current = newGame;
        
        const hintForNextMove = openingData.moves[newIndex]?.hint || '';
        setState(prev => ({ 
          ...prev, 
          game: newGame, 
          bookIndex: newIndex,
          isBotThinking: false, 
          hintOpen: true, 
          currentHint: hintForNextMove 
        }));
        isBotMovingRef.current = false;
      } catch (error) { 
        console.error('Book move error:', error);
        setState(prev => ({ ...prev, isBotThinking: false })); 
        isBotMovingRef.current = false;
      }
    } else {
      // Book exhausted or player deviated - use Stockfish
      if (!stockfishLoadedRef.current) {
        console.log('Stockfish not loaded');
        setState(prev => ({ 
          ...prev, 
          phase: 'stockfish', 
          isBotThinking: false,
          toast: { message: "🤖 Bot is taking a nap. Let's keep playing!", type: 'info' }
        }));
        isBotMovingRef.current = false;
        return;
      }
      
      const best = await playStockfishMove(game.fen());
      if (best) { 
        try {
          const moveObj = game.move(best);
          if (!moveObj) {
            console.error('Failed to make Stockfish move:', best);
            setState(prev => ({ ...prev, isBotThinking: false }));
            isBotMovingRef.current = false;
            return;
          }
          
          const fen = game.fen();
          const newGame = new Chess(fen);
          gameRef.current = newGame;
          
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
      isBotMovingRef.current = false;
    }
  }, []);

  const startGame = useCallback((opening: OpeningType, side: PlayerSide) => {
    const game = new Chess();
    gameRef.current = game;
    selectedOpeningRef.current = opening;
    playerSideRef.current = side;
    isBotMovingRef.current = false;
    
    const openingData = getOpening(opening);
    setState(prev => ({
      ...prev, selectedOpening: opening, playerSide: side, gameStarted: true,
      game, phase: 'book', bookIndex: 0, isBotThinking: false,
      hintOpen: false, currentHint: openingData?.moves[0]?.hint || 'Make your move!',
      showArrow: false, arrowFrom: null, arrowTo: null, analysisOpen: false,
      lastMoveScore: null, toast: null, isShaking: false,
    }));
    
    // If player is BLACK, bot (WHITE) plays first
    if (side === 'black') {
      setTimeout(() => playBotMove(), 800);
    }
  }, [playBotMove]);

  const onPlayerMove = useCallback(async (source: string, target: string) => {
    // Prevent player from moving while bot is thinking
    if (state.isBotThinking) return false;
    
    const game = gameRef.current;
    const opening = selectedOpeningRef.current;
    const side = playerSideRef.current;
    
    if (!game || !opening || !side) return false;
    
    const moveResult = game.move({ from: source, to: target, promotion: 'q' });
    if (!moveResult) { 
      setState(prev => ({ ...prev, isShaking: true }));
      setTimeout(() => setState(prev => ({ ...prev, isShaking: false })), 500); 
      return false; 
    }
    
    const openingData = getOpening(opening)!;
    const { isCorrect, newIndex } = isPlayerMoveBookCorrect(game, openingData, moveResult.san);
    const fen = game.fen();
    const newGame = new Chess(fen);
    gameRef.current = newGame;
    
    setState(prev => ({ 
      ...prev, 
      game: newGame,
      phase: isCorrect && newIndex < openingData.moves.length ? 'book' : 'stockfish',
      bookIndex: newIndex, 
      isShaking: false, 
      toast: null 
    }));
    
    // Bot responds after player moves
    setTimeout(() => playBotMove(), 500);
    return true;
  }, [state.isBotThinking, playBotMove]);

  const showHint = useCallback(() => {
    const game = gameRef.current;
    const opening = selectedOpeningRef.current;
    const { phase, bookIndex } = state;
    
    if (!game || !opening) return;
    const openingData = getOpening(opening)!;
    const isWhiteTurn = game.turn() === 'w';
    const hintMove = phase === 'book' && bookIndex < openingData.moves.length
      ? (isWhiteTurn ? openingData.moves[bookIndex].white : openingData.moves[bookIndex].black) : '';
    if (hintMove && hintMove.length >= 4) {
      setState(prev => ({ 
        ...prev, 
        hintOpen: true, 
        showArrow: true, 
        arrowFrom: hintMove.substring(0, 2), 
        arrowTo: hintMove.substring(2, 4) 
      }));
    }
  }, [state.phase, state.bookIndex]);

  const resetGame = useCallback(() => {
    stockfishRef.current?.terminate();
    
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
    
    gameRef.current = null;
    selectedOpeningRef.current = null;
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

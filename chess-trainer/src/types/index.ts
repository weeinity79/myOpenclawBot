export type OpeningType = 'ruy_lopez' | 'italian' | 'fried_liver';

export interface OpeningMove {
  white: string;
  black: string;
  hint: string;
}

export interface Opening {
  id: OpeningType;
  name: string;
  description: string;
  moves: OpeningMove[];
}

export type PlayerSide = 'white' | 'black';

export type GamePhase = 'setup' | 'book' | 'stockfish' | 'playing';

export type ScoreRating = 'awesome' | 'okay' | 'mistake' | null;

export interface AppState {
  selectedOpening: OpeningType | null;
  playerSide: PlayerSide | null;
  gameStarted: boolean;
  game: any;
  phase: GamePhase;
  bookIndex: number;
  isBotThinking: boolean;
  hintOpen: boolean;
  currentHint: string;
  showArrow: boolean;
  arrowFrom: string | null;
  arrowTo: string | null;
  analysisOpen: boolean;
  lastMoveScore: ScoreRating;
  resetKey: number;
  toast: { message: string; type: 'info' | 'success' | 'error' } | null;
  isShaking: boolean;
}

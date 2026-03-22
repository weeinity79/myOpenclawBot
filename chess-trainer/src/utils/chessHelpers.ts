import type { Opening } from '../types';

export const getBookMove = (
  game: any,
  opening: Opening,
  bookIndex: number,
  playerSide: 'white' | 'black'
): { move: string; newIndex: number; isBookMove: boolean } => {
  const isWhiteTurn = game.turn() === 'w';
  const expectedMove = opening.moves[bookIndex];
  
  if (!expectedMove) {
    return { move: '', newIndex: bookIndex, isBookMove: false };
  }
  
  const expectedMoveStr = isWhiteTurn ? expectedMove.white : expectedMove.black;
  
  return {
    move: expectedMoveStr,
    newIndex: bookIndex + 1,
    isBookMove: true,
  };
};

export const getNextBookMoveForBot = (
  game: any,
  opening: Opening,
  playerSide: 'white' | 'black'
): { move: string; newIndex: number; isBookMove: boolean } => {
  const moveCount = game.history().length;
  const expectedIndex = moveCount;
  
  if (expectedIndex >= opening.moves.length) {
    return { move: '', newIndex: expectedIndex, isBookMove: false };
  }
  
  const expectedMove = opening.moves[expectedIndex].white;
  
  return {
    move: expectedMove,
    newIndex: expectedIndex + 1,
    isBookMove: true,
  };
};

export const isPlayerMoveBookCorrect = (
  game: any,
  opening: Opening,
  playerMove: string
): { isCorrect: boolean; newIndex: number } => {
  const moves = game.history();
  const moveCount = moves.length - 1;
  
  const isWhiteTurn = game.turn() === 'w';
  const expectedIndex = moveCount;
  
  if (expectedIndex >= opening.moves.length) {
    return { isCorrect: false, newIndex: expectedIndex };
  }
  
  const expectedMove = isWhiteTurn 
    ? opening.moves[expectedIndex].white 
    : opening.moves[expectedIndex].black;
  
  const normalizedPlayerMove = playerMove.replace(/[+#=!?]/g, '');
  const normalizedExpectedMove = expectedMove.replace(/[+#=!?]/g, '');
  
  return {
    isCorrect: normalizedPlayerMove === normalizedExpectedMove,
    newIndex: expectedIndex + 1,
  };
};

export const getScoreRating = (centipawnDiff: number): 'awesome' | 'okay' | 'mistake' => {
  if (centipawnDiff < 0.5) return 'awesome';
  if (centipawnDiff < 1.5) return 'okay';
  return 'mistake';
};

export const getRatingMessage = (rating: 'awesome' | 'okay' | 'mistake'): string => {
  switch (rating) {
    case 'awesome':
      return 'Amazing move! You are a chess superstar! 🌟';
    case 'okay':
      return 'Good job! Keep thinking ahead! 🤔';
    case 'mistake':
      return 'Oops! Lets try a better move next time! 🔴';
  }
};

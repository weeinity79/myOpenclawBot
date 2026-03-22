import { Chess } from 'chess.js';
import type { Opening, OpeningType } from '../types';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function getOpening(id: OpeningType): Opening | undefined {
  const openings: Record<OpeningType, Opening> = {
    ruy_lopez: {
      id: 'ruy_lopez',
      name: 'Ruy Lopez',
      description: '♟️ The classic Spanish Opening!',
      moves: [
        { white: 'e2e4', black: 'e7e5', hint: 'Black attacks the center! 🏰' },
        { white: 'g1f3', black: 'b8c6', hint: 'Knights come out to the center! 🐴' },
        { white: 'f1b5', black: 'a7a6', hint: 'The Bishop eyes the center! 🎯' },
      ],
    },
    italian: {
      id: 'italian',
      name: 'Italian Game',
      description: '⚡ The quick and friendly opening!',
      moves: [
        { white: 'e2e4', black: 'e7e5', hint: 'Open the center! 🚀' },
        { white: 'g1f3', black: 'b8c6', hint: 'Knights ready to hop! 🐴' },
        { white: 'f1c4', black: 'f8c5', hint: 'Bishops point at the enemy! 🎯' },
      ],
    },
    fried_liver: {
      id: 'fried_liver',
      name: 'Fried Liver Attack',
      description: '🌶️ A spicy aggressive opening!',
      moves: [
        { white: 'e2e4', black: 'e7e5', hint: 'Control the center! ⭐' },
        { white: 'g1f3', black: 'b8c6', hint: 'Knight to the center! 🐴' },
        { white: 'f1c4', black: 'g8f6', hint: 'Bishop aims at f7! 🎯' },
        { white: 'f3g5', black: 'd7d5', hint: 'The Knight jumps in! 🌟' },
      ],
    },
  };
  return openings[id];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function getNextBookMoveForBot(
  game: any,
  opening: Opening,
  playerSide: 'white' | 'black'
): { move: string | null; newIndex: number; isBookMove: boolean } {
  const history = game.history();
  const moveCount = history.length;

  // Bot plays opposite of player: if player is white, bot is black
  const isBotWhite = playerSide === 'black';

  // Calculate which opening move the bot should play
  let botMoveIndex: number;
  if (isBotWhite) {
    // Bot is WHITE: bot plays on moves 0, 2, 4... (even positions in history)
    botMoveIndex = Math.floor(moveCount / 2);
  } else {
    // Bot is BLACK: bot plays on moves 1, 3, 5... (odd positions)
    botMoveIndex = Math.floor((moveCount - 1) / 2);
  }

  // Handle edge case: botMoveIndex could be negative
  if (botMoveIndex < 0) {
    botMoveIndex = 0;
  }

  // Check if we have a valid bot move that hasn't been played yet
  // The bot should play the move at botMoveIndex, but only if the OTHER player hasn't already played it
  if (botMoveIndex < opening.moves.length) {
    const openingMove = isBotWhite ? opening.moves[botMoveIndex].white : opening.moves[botMoveIndex].black;
    
    // Check if this specific move (white or black) has already been played
    // We need to verify by looking at the history from the perspective of that color
    if (openingMove) {
      // If bot is white, check if white has already played this move in history
      // If bot is black, check if black has already played this move in history
      const hasAlreadyPlayed = history.some((move, idx) => {
        if (isBotWhite) {
          // For white moves: even indices (0, 2, 4...)
          return idx % 2 === 0 && move.endsWith(openingMove.substring(2, 4));
        } else {
          // For black moves: odd indices (1, 3, 5...)
          return idx % 2 === 1 && move.endsWith(openingMove.substring(2, 4));
        }
      });
      
      if (!hasAlreadyPlayed) {
        return { move: openingMove, newIndex: botMoveIndex + 1, isBookMove: true };
      }
    }
  }

  // Book exhausted
  return { move: null, newIndex: opening.moves.length, isBookMove: false };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function isPlayerMoveBookCorrect(
  game: any,
  opening: Opening,
  playerMove: string
): { isCorrect: boolean; newIndex: number } {
  const history = game.history();
  const moveCount = history.length;

  // Determine which player move we're checking
  const playerMoveIndex = Math.floor((moveCount - 1) / 2);

  if (playerMoveIndex >= 0 && playerMoveIndex < opening.moves.length) {
    // Get the expected move in UCI format
    const expectedMoveUCI = opening.moves[playerMoveIndex].white;
    
    // Convert UCI to SAN-like for comparison: e2e4 -> e4
    // Check if player's move matches expected
    if (expectedMoveUCI && playerMove && expectedMoveUCI.endsWith(playerMove)) {
      return { isCorrect: true, newIndex: playerMoveIndex + 1 };
    }
  }

  return { isCorrect: false, newIndex: moveCount };
}

export function getRatingMessage(score: number): { message: string; emoji: string; color: string } {
  if (score < 0.5) {
    return { message: 'AWESOME MOVE!', emoji: '🌟', color: 'green' };
  } else if (score < 1.5) {
    return { message: 'OKAY MOVE', emoji: '🤔', color: 'yellow' };
  } else {
    return { message: 'OOPS! MISTAKE', emoji: '🔴', color: 'red' };
  }
}

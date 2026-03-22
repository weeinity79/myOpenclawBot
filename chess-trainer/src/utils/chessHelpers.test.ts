import { describe, it, expect } from 'vitest';
import { Chess } from 'chess.js';
import { getOpening, getNextBookMoveForBot, isPlayerMoveBookCorrect } from './chessHelpers';

describe('getOpening', () => {
  it('should return Ruy Lopez opening', () => {
    const opening = getOpening('ruy_lopez');
    expect(opening).toBeDefined();
    expect(opening?.name).toBe('Ruy Lopez');
    expect(opening?.moves.length).toBe(3);
  });

  it('should return Italian Game opening', () => {
    const opening = getOpening('italian');
    expect(opening).toBeDefined();
    expect(opening?.name).toBe('Italian Game');
    expect(opening?.moves.length).toBe(3);
  });

  it('should return Fried Liver Attack opening', () => {
    const opening = getOpening('fried_liver');
    expect(opening).toBeDefined();
    expect(opening?.name).toBe('Fried Liver Attack');
    expect(opening?.moves.length).toBe(4);
  });

  it('should return undefined for invalid opening', () => {
    const opening = getOpening('invalid' as any);
    expect(opening).toBeUndefined();
  });
});

describe('getNextBookMoveForBot', () => {
  it('should return first bot move when game starts with WHITE player', () => {
    const game = new Chess();
    const opening = getOpening('ruy_lopez')!;
    
    // Player is white, bot is black - bot should respond to e4
    const result = getNextBookMoveForBot(game, opening, 'white');
    
    // Bot (black) should respond with e5
    expect(result.isBookMove).toBe(true);
    expect(result.move).toBe('e7e5');
  });

  it('should return second bot move after two player moves', () => {
    const game = new Chess();
    // Player white: e4
    game.move('e4');
    // Bot black: e5 (we manually move for test setup)
    game.move('e5');
    const opening = getOpening('ruy_lopez')!;
    
    // Now player white's turn again, bot is black
    // Player should play Nf3 next (index 1), but we're asking what bot should do
    // After player plays Nf3, bot should respond with Nc6 (index 1)
    game.move('Nf3');
    const result = getNextBookMoveForBot(game, opening, 'white');
    
    // Bot (black) should respond with Nc6
    expect(result.isBookMove).toBe(true);
    expect(result.move).toBe('b8c6');
  });

  it('should return not book move when exhausted', () => {
    const game = new Chess();
    // Play through all book moves: e4, e5, Nf3, Nc6, Bb5, a6
    game.move('e4');
    game.move('e5');
    game.move('Nf3');
    game.move('Nc6');
    game.move('Bb5');
    game.move('a6');
    
    const opening = getOpening('ruy_lopez')!;
    const result = getNextBookMoveForBot(game, opening, 'white');
    
    // Book exhausted (3 pairs = 6 moves done)
    expect(result.isBookMove).toBe(false);
    expect(result.move).toBeNull();
  });

  it('should work with BLACK player (bot plays WHITE first)', () => {
    const game = new Chess();
    const opening = getOpening('ruy_lopez')!;
    
    // Player is black, bot is white - bot should play first
    const result = getNextBookMoveForBot(game, opening, 'black');
    
    // Bot (white) should play e4
    expect(result.isBookMove).toBe(true);
    expect(result.move).toBe('e2e4');
  });
});

describe('isPlayerMoveBookCorrect', () => {
  it('should return correct when player makes book move', () => {
    const game = new Chess();
    const opening = getOpening('ruy_lopez')!;
    game.move('e4');
    
    const result = isPlayerMoveBookCorrect(game, opening, 'e4');
    
    // After e4, player has made 1 move (white)
    expect(result.isCorrect).toBe(true);
  });

  it('should return incorrect when player makes non-book move', () => {
    const game = new Chess();
    const opening = getOpening('ruy_lopez')!;
    game.move('e4');
    // Player makes a non-book move (not in Ruy Lopez)
    const result = isPlayerMoveBookCorrect(game, opening, 'a4');
    
    expect(result.isCorrect).toBe(false);
  });
});

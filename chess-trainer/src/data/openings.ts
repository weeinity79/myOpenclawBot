import { Opening } from '../types';

export const openings: Opening[] = [
  {
    id: 'ruy_lopez',
    name: 'Ruy Lopez',
    description: 'The classic Spanish Opening! ♟️',
    moves: [
      { white: 'e4', black: 'e5', hint: 'Black attacks the center! 🏰' },
      { white: 'Nf3', black: 'Nc6', hint: 'Knights come out to the center! 🐴' },
      { white: 'Bb5', black: 'a6', hint: 'The Bishop eyes the center! 🎯' },
    ],
  },
  {
    id: 'italian',
    name: 'Italian Game',
    description: 'The quick and friendly opening! ⚡',
    moves: [
      { white: 'e4', black: 'e5', hint: 'Open the center! 🚀' },
      { white: 'Nf3', black: 'Nc6', hint: 'Knights ready to hop! 🐴' },
      { white: 'Bc4', black: 'Bc5', hint: 'Bishops point at the enemy! 🎯' },
    ],
  },
  {
    id: 'fried_liver',
    name: 'Fried Liver Attack',
    description: 'A spicy aggressive opening! 🌶️',
    moves: [
      { white: 'e4', black: 'e5', hint: 'Control the center! ⭐' },
      { white: 'Nf3', black: 'Nc6', hint: 'Knight to the center! 🐴' },
      { white: 'Bc4', black: 'Nf6', hint: 'Bishop aims at f7! 🎯' },
      { white: 'Ng5', black: 'd5', hint: 'The Knight jumps in! 🌟' },
    ],
  },
];

export const getOpening = (id: string): Opening | undefined => {
  return openings.find((o) => o.id === id);
};

export const getInitialHint = (opening: string): string => {
  const o = getOpening(opening);
  if (!o) return 'Make your move! ♟️';
  return o.moves[0].hint;
};

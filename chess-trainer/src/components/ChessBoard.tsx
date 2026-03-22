import { useState } from 'react';
import { Chessboard as ReactChessboard } from 'react-chessboard';

interface Props {
  game: any;
  onMove: (source: string, target: string) => boolean | Promise<boolean>;
  isShaking: boolean;
  arrowFrom: string | null;
  arrowTo: string | null;
  playerSide: 'white' | 'black' | null;
}

export const ChessBoard: React.FC<Props> = ({
  game,
  onMove,
  isShaking,
  arrowFrom,
  arrowTo,
  playerSide,
}) => {
  const [selectedSquare, setSelectedSquare] = useState<string | null>(null);
  const [possibleMoves, setPossibleMoves] = useState<string[]>([]);

  // Get possible moves for a square
  const getPossibleMoves = (square: string): string[] => {
    if (!game) return [];
    try {
      const moves = game.moves({ square, verbose: true });
      return moves.map((m: { to: string }) => m.to);
    } catch {
      return [];
    }
  };

  // Handle piece click
  const handleSquareClick = (square: string) => {
    if (!game || !playerSide) return;
    
    // Check if there's a piece on this square
    const piece = game.get(square);
    if (!piece) {
      // Empty square - if we had a selected piece, try to move there
      if (selectedSquare && possibleMoves.includes(square)) {
        onMove(selectedSquare, square);
        setSelectedSquare(null);
        setPossibleMoves([]);
      } else {
        // Clicked empty square with no selection - deselect
        setSelectedSquare(null);
        setPossibleMoves([]);
      }
      return;
    }
    
    // Check if it's the player's piece
    const isPlayerPiece = (playerSide === 'white' && piece.color === 'w') ||
                         (playerSide === 'black' && piece.color === 'b');
    
    if (!isPlayerPiece) {
      // Enemy piece - if we had a selected piece, try to capture
      if (selectedSquare && possibleMoves.includes(square)) {
        onMove(selectedSquare, square);
        setSelectedSquare(null);
        setPossibleMoves([]);
      } else {
        setSelectedSquare(null);
        setPossibleMoves([]);
      }
      return;
    }
    
    // It's player's piece - select it and show possible moves
    if (selectedSquare === square) {
      // Deselect if clicking same square
      setSelectedSquare(null);
      setPossibleMoves([]);
    } else {
      setSelectedSquare(square);
      setPossibleMoves(getPossibleMoves(square));
    }
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const getCustomArrows = (): any[] => {
    const arrows: any[] = [];
    
    // Add hint arrow (red arrow like chess.com)
    if (arrowFrom && arrowTo) {
      arrows.push([arrowFrom, arrowTo, 'rgba(255, 0, 0, 0.6)']);
    }
    
    return arrows;
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const getCustomSquareStyles = (): Record<string, any> => {
    if (!game) return {};
    
    const styles: Record<string, any> = {};
    const history = game.history({ verbose: true });
    
    // Highlight last move (yellow overlay)
    if (history.length > 0) {
      const lastMove = history[history.length - 1];
      styles[lastMove.from] = { backgroundColor: 'rgba(255, 230, 100, 0.4)' };
      styles[lastMove.to] = { backgroundColor: 'rgba(255, 230, 100, 0.4)' };
    }
    
    // Highlight selected square (blue)
    if (selectedSquare) {
      styles[selectedSquare] = { 
        ...styles[selectedSquare],
        backgroundColor: 'rgba(96, 165, 250, 0.6)' 
      };
    }
    
    // Show gray dots on possible move squares (lichess/chess.com style)
    possibleMoves.forEach(square => {
      const piece = game.get(square);
      if (piece) {
        // Capture: red-tinted circle
        styles[square] = { 
          ...styles[square],
          backgroundImage: 'radial-gradient(circle, rgba(239, 68, 68, 0.7) 30%, transparent 31%)',
          backgroundSize: '100% 100%'
        };
      } else {
        // Regular move: gray dot
        styles[square] = { 
          ...styles[square],
          backgroundImage: 'radial-gradient(circle, rgba(128, 128, 128, 0.5) 25%, transparent 26%)',
          backgroundSize: '100% 100%'
        };
      }
    });
    
    return styles;
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handlePieceDrop = (sourceSquare: any, targetSquare: any): boolean => {
    const result = onMove(sourceSquare, targetSquare) as boolean;
    if (result) {
      setSelectedSquare(null);
      setPossibleMoves([]);
    }
    return result;
  };

  const orientation = playerSide || 'white';

  return (
    <div className={`h-full flex items-center justify-center ${isShaking ? 'shake' : ''}`}>
      <div className="w-full max-w-[600px] aspect-square">
        <ReactChessboard
          id="BasicBoard"
          position={game?.fen() || 'start'}
          onPieceDrop={handlePieceDrop}
          onSquareClick={handleSquareClick}
          customArrows={getCustomArrows()}
          customSquareStyles={getCustomSquareStyles()}
          boardOrientation={orientation}
          boardWidth={600}
        />
      </div>
    </div>
  );
};

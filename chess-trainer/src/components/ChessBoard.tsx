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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const getCustomArrows = (): any[] => {
    if (!arrowFrom || !arrowTo) return [];
    return [[arrowFrom, arrowTo, 'rgba(255, 107, 107, 0.7)']];
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const getCustomSquareStyles = (): Record<string, any> => {
    if (!game || !playerSide) return {};
    
    const styles: Record<string, any> = {};
    const history = game.history({ verbose: true });
    
    if (history.length > 0) {
      const lastMove = history[history.length - 1];
      styles[lastMove.from] = { backgroundColor: 'rgba(255, 230, 100, 0.5)' };
      styles[lastMove.to] = { backgroundColor: 'rgba(255, 230, 100, 0.5)' };
    }
    
    return styles;
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handlePieceDrop = (sourceSquare: any, targetSquare: any): boolean => {
    return onMove(sourceSquare, targetSquare) as boolean;
  };

  const orientation = playerSide || 'white';

  return (
    <div className={`h-full flex items-center justify-center ${isShaking ? 'shake' : ''}`}>
      <div className="w-full max-w-[600px] aspect-square">
        <ReactChessboard
          id="BasicBoard"
          position={game?.fen() || 'start'}
          onPieceDrop={handlePieceDrop}
          customArrows={getCustomArrows()}
          customSquareStyles={getCustomSquareStyles()}
          boardOrientation={orientation}
          boardWidth={600}
        />
      </div>
    </div>
  );
};

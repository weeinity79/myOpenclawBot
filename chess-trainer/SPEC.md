# Chess Opening Trainer - Detailed Design Specification

## 1. Project Overview

**Project Name:** Chess Opening Trainer
**Target Audience:** 7-year-old child
**Device:** iPad (landscape mode)
**Core Functionality:** A kid-friendly chess opening trainer that teaches basic openings through interactive gameplay with a chess engine
**Vibe:** Cheerful, colorful, encouraging, "Cartoon Castle" theme

---

## 2. Tech Stack

- **Framework:** React 18+ with TypeScript
- **Styling:** Tailwind CSS
- **Chess Logic:** chess.js
- **Board UI:** react-chessboard
- **Engine:** stockfish.js (WebAssembly, depth 5)
- **Build Tool:** Vite (for fast development)

---

## 3. UI/UX Specification

### 3.1 Layout Structure

**Overall:** Fixed 2-column layout, NO vertical scrolling on 1024x768 or 1366x1024

```
┌─────────────────────────────────────────────────────────────┐
│                    HEADER (optional)                         │
├───────────────────────────────────┬─────────────────────────┤
│                                   │                         │
│      CHESSBOARD (60%)             │   CONTROL PANEL (40%)   │
│                                   │                         │
│                                   │   ┌─────────────────┐   │
│                                   │   │  Setup Card     │   │
│                                   │   └─────────────────┘   │
│                                   │   ┌─────────────────┐   │
│                                   │   │  Hint Panel     │   │
│                                   │   └─────────────────┘   │
│                                   │   ┌─────────────────┐   │
│                                   │   │  Analysis       │   │
│                                   │   └─────────────────┘   │
│                                   │                         │
└───────────────────────────────────┴─────────────────────────┘
```

**Breakpoints:**
- iPad Landscape (1024x768): 60/40 split
- Desktop (1366x1024+): 60/40 split, max-width container centered

### 3.2 Color Palette - "Cartoon Castle"

| Role | Color | Hex |
|------|-------|-----|
| Primary Background | Sky Blue | #87CEEB |
| Secondary Background | Sunny Yellow | #FFE066 |
| Accent | Grass Green | #7CB342 |
| Light Squares | Cream | #FFF8DC |
| Dark Squares | Light Green | #C5E1A5 |
| Card Background | White | #FFFFFF |
| Text Primary | Dark Blue | #1A237E |
| Text Secondary | Purple | #5E35B1 |
| Success | Bright Green | #4CAF50 |
| Warning | Orange | #FF9800 |
| Error | Soft Red | #EF5350 |

### 3.3 Typography

- **Font Family:** "Comic Neue" (Google Fonts) or "Nunito" - rounded, friendly
- **Headings:** 24-32px, bold
- **Body:** 18-20px, medium
- **Buttons:** 20-24px, bold
- **Minimum touch target:** 48x48px (child-friendly)

### 3.4 Component Styling

All UI elements:
- `rounded-2xl` or `rounded-3xl`
- Soft drop shadows: `shadow-lg`
- Large text/buttons
- Playful hover animations (scale 1.05)

---

## 4. Component Specifications

### 4.1 ChessBoard (Left Column - 60%)

**Component:** react-chessboard

**Props:**
- `boardWidth`: fills container (responsive)
- `customArrows`: array of arrows for hints [from, to, color]
- `customSquareStyles`: highlight last move

**Square Colors:**
- Light: `#FFF8DC` (cream)
- Dark: `#C5E1A5` (light green)

**Features:**
- Show last move with highlight
- Hint arrow: thick, colorful (e.g., #FF6B6B red), appears when "Show me!" clicked
- Responsive: fills available height

### 4.2 Setup Card - "Choose Your Adventure"

**Title:** 🏰 Choose Your Adventure!

**Elements:**

1. **Opening Selector:**
   - Dropdown or large toggle buttons
   - Options: Ruy Lopez, Italian Game, Fried Liver Attack
   - Kid-friendly descriptions with emojis

2. **Side Selection:**
   - Two massive buttons side-by-side:
     - "♔ I am WHITE" (white button, black text)
     - "♚ I am BLACK" (black button, white text)
   - Selected side gets highlight border

3. **Start Button:**
   - Big, bouncy "🎮 Start Playing!" button
   - Only enabled when opening + side selected
   - On click: initialize game, hide setup, show board

**State:**
```typescript
interface SetupState {
  selectedOpening: 'ruy_lopez' | 'italian' | 'fried_liver' | null;
  playerSide: 'white' | 'black' | null;
  gameStarted: boolean;
}
```

### 4.3 New Game Button - "Play Again!"

**Title:** 🔄 Play Again!

**Behavior:**
- Always visible after game starts
- Big, prominent button below Control Panel cards
- On click: reset entire game state (see Section 4.8)


### 4.3 Game Logic & Bot Behavior

**Phase 1: Book Moves**
- Hardcoded opening dictionary (see Section 7)
- Bot responds instantly with correct move from book
- Track position in opening sequence

**Phase 2: Stockfish**
- Trigger when:
  - Opening sequence exhausted, OR
  - Player makes non-book move
- Use stockfish.js (WASM) at depth 5
- Display "🤖 Bot is thinking..." with animation

**Engine Integration:**
```typescript
interface GameState {
  phase: 'setup' | 'book' | 'stockfish';
  bookIndex: number; // position in opening sequence
  fen: string; // current position
  moves: string[]; // move history
}
```

#### BLACK-Side Logic (Player is BLACK)
When player chooses BLACK:
1. Bot (WHITE) plays first with book move
2. Player (BLACK) responds with book move
3. Continue until book exhausted or player deviates
4. Then switch to Stockfish

#### Book Move Detection
- **Book exhaustion detection**: When player makes a move that is NOT in the expected book sequence for the current opening, transition to Stockfish phase
- Check: Does player's move match the expected move at current `bookIndex`?
- If NO: Set `phase = 'stockfish'`, continue game with Stockfish

#### Phase Transitions
**Phase 1: Book Moves**
- Hardcoded opening dictionary (see Section 7)
- Bot responds instantly with correct move from book
- Track position in opening sequence
- Move to Stockfish when: (1) book sequence ends, OR (2) player makes non-book move

**Phase 2: Stockfish**
- Trigger when book exhausted (as defined above)
- Use stockfish.js (WASM) at **depth 5** (reduced from 8 for faster iPad response)
- Display "🤖 Bot is thinking..." with animation

#### Evaluation Timing
- **Evaluate after each player move**: 
  1. Get Stockfish evaluation BEFORE player's move (capture FEN)
  2. Process player's move
  3. Get Stockfish evaluation AFTER player's move
  4. Calculate centipawn difference → display as badge in Analysis Panel

### 4.4 Hint Panel - "Friendly Helper"

**Title:** 🦉 Need a Hint?

**Layout:** Collapsible accordion

**When Expanded:**

1. **Hint Text:**
   - Opening-specific encouraging message
   - Examples:
     - Ruy Lopez: "Slide your Knight to the center to protect your pieces! 🐴"
     - Italian: "Bring your Knight out - it's ready to jump! 🦘"

2. **Show Me Button:**
   - Big "✨ Show me!" button
   - On click: set customArrows on chessboard to show correct move

**State:**
```typescript
interface HintState {
  isOpen: boolean;
  hintText: string;
  showArrow: boolean;
  arrowFrom: string | null;
  arrowTo: string | null;
}
```

### 4.5 Analysis Panel - "My Score!"

**Title:** 📊 My Score!

**Layout:** Collapsible accordion

**Evaluation Logic:**
1. Get Stockfish evaluation before player's move
2. Get evaluation after player's move
3. Calculate centipawn difference

**Kid-Friendly Badges:**

| Eval Drop | Badge |
|-----------|-------|
| < 0.5 | 🌟 **AWESOME MOVE!** (green) |
| 0.5 - 1.5 | 🤔 **OKAY MOVE** (yellow) |
| > 1.5 | 🔴 **OOPS! MISTAKE** (red) |

**Display:**
- Large emoji + text (NO raw numbers)
- Brief encouraging message
- Color-coded background

---

## 5. State Management

### 5.1 Global State (React Context)

```typescript
interface AppState {
  // Setup
  selectedOpening: Opening | null;
  playerSide: 'white' | 'black' | null;
  gameStarted: boolean;

  // Game
  game: Chess; // chess.js instance
  phase: 'setup' | 'book' | 'stockfish';
  bookIndex: number;
  isBotThinking: boolean;

  // Hints
  hintOpen: boolean;
  currentHint: string;
  showArrow: boolean;
  arrowFrom: string | null;
  arrowTo: string | null;

  // Analysis
  analysisOpen: boolean;
  lastMoveScore: 'awesome' | 'okay' | 'mistake' | null;

  // UI
  resetKey: number; // for hard reset

### 4.6 Edge Case Handling

#### Illegal Move Feedback
- When player drops piece on invalid square:
  - Trigger **shake animation** on chessboard (CSS keyframes: translateX ±10px, 3 cycles)
  - Show **toast message**: "Oops! That move isn't allowed. Try again! 🤔"
  - Piece returns to original position
  - No state change

#### Draw Handling
- **Stalemate detection**: Display toast "It's a draw! The king has no moves left. 🤝"
- **50-move rule**: If 50 moves without pawn move or capture, display "Draw by 50-move rule! 🤝"
- After draw: Show "Play Again?" prompt with New Game button

#### Stockfish Load Failure
- If Stockfish fails to initialize:
  - Display **fallback message** in Analysis Panel: "🤖 Bot is taking a nap. Let's keep playing!"
  - Continue with book moves only (if available)
  - Log error to console for debugging

}
```

### 5.2 Reset Logic

"New Game" button should reset ALL state:
- New chess.js instance
- Clear move history
- Reset to setup phase
- Clear hints and analysis
- Clear arrows

---

## 6. Opening Dictionary

### 6.1 Ruy Lopez

```json
{
  "name": "Ruy Lopez",
  "description": "The classic Spanish Opening! ♟️",
  "moves": [
    { "white": "e4", "black": "e5", "hint": "Black attacks the center! 🏰" },
    { "white": "Nf3", "black": "Nc6", "hint": "Knights come out to the center! 🐴" },
    { "white": "Bb5", "black": "a6", "hint": "The Bishop eyes the center! 🎯" }
  ]
}
```

### 6.2 Italian Game

```json
{
  "name": "Italian Game",
  "description": "The quick and friendly opening! ⚡",
  "moves": [
    { "white": "e4", "black": "e5", "hint": "Open the center! 🚀" },
    { "white": "Nf3", "black": "Nc6", "hint": "Knights ready to hop! 🐴" },
    { "white": "Bc4", "black": "Bc5", "hint": "Bishops point at the enemy! 🎯" }
  ]
}
```

### 6.3 Fried Liver Attack

```json
{
  "name": "Fried Liver Attack",
  "description": "A spicy aggressive opening! 🌶️",
  "moves": [
    { "white": "e4", "black": "e5", "hint": "Control the center! ⭐" },
    { "white": "Nf3", "black": "Nc6", "hint": "Knight to the center! 🐴" },
    { "white": "Bc4", "black": "Nf6", "hint": "Bishop aims at f7! 🎯" },
    { "white": "Ng5", "black": "d5", "hint": "The Knight jumps in! 🌟" }
  ]
}
```

---

## 7. Technical Requirements
### 7.2 Error Boundary Wrapper
```typescript
// Wrap main App in error boundary
class ErrorBoundary extends React.Component {
  state = { hasError: false };
  
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  
  render() {
    if (this.state.hasError) {
      return <div className="p-8 text-center">Something went wrong. Please refresh! 🔄</div>;
    }
    return this.props.children;
  }
}
```

### 7.3 Stockfish Cleanup (Critical)
```typescript
// Clean up on component unmount
useEffect(() => {
  return () => {
    stockfish?.terminate(); // Kill worker
    stockfish = null;
  };
}, []);
```


### 7.1 Dependencies

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "chess.js": "^0.12.0"",
    "react-chessboard": "^4.4.0"",
    "stockfish.js": "^16.0.0"
  },
  "devDependencies": {
    "tailwindcss": "^3.4.0",
    "vite": "^5.0.0",
    "@types/react": "^18.2.0",
    "typescript": "^5.3.0"
  }
}
```

### 7.2 Stockfish Integration

- Use WebAssembly version for performance
- Initialize on app load (lazy load)
- Depth 8 for fast, child-friendly response time
- Kill previous search before starting new one

### 7.3 Responsive Design

- Container: max-width 1400px, centered
- Chessboard: aspect-ratio 1/1, fills left column
- Control Panel: flex column, gap 4 between cards
- No scroll: use flexbox with overflow hidden

### 7.4 Performance Targets

- First paint: < 1s
- Bot move response: < 500ms (depth 5)
- Hint arrow render: < 100ms
- Game reset: < 200ms

---

## 8. File Structure

```
chess-trainer/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
├── SPEC.md
├── public/
│   └── stockfish.js/
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── index.css
    ├── components/
    │   ├── ChessBoard.tsx
    │   ├── ControlPanel.tsx
    │   ├── SetupCard.tsx
    │   ├── HintPanel.tsx
    │   └── AnalysisPanel.tsx
    ├── hooks/
    │   ├── useGame.ts
    │   ├── useStockfish.ts
    │   └── useHint.ts
    ├── data/
    │   └── openings.ts
    ├── types/
    │   └── index.ts
    └── utils/
        └── chessHelpers.ts
```

---

## 9. Acceptance Criteria

### Must Have (MVP)
- [ ] 2-column layout renders correctly on iPad landscape
- [ ] Chessboard displays with cream/green squares
- [ ] Can select opening and side
- [ ] Book moves work for all 3 openings
- [ ] Stockfish kicks in after book exhausted
- [ ] Hint panel shows text and arrow
- [ ] Analysis panel shows kid-friendly badges
- [ ] Reset clears all state properly
- [ ] Touch-friendly (48px+ targets)

### Nice to Have
- [ ] Sound effects for moves
- [ ] Confetti on awesome moves
- [ ] More openings
- [ ] Move history display

---

## 10. Design Mockup (ASCII)

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│   ┌──────────────────────────────┐  ┌──────────────────────┐ │
│   │                              │  │ 🏰 Choose Your       │ │
│   │                              │  │    Adventure!        │ │
│   │     ♜ ♞ ♝ ♚ ♝ ♞ ♜          │  │                      │ │
│   │     ♟ ♟ ♟ ♟ ♟ ♟ ♟          │  │  Opening: [Italian ▼] │ │
│   │                              │  │                      │ │
│   │     · · · · · · · ·        │  │  ♔ I am WHITE        │ │
│   │     · · · · · · · ·        │  │  ♚ I am BLACK        │ │
│   │                              │  │                      │ │
│   │     ♙ ♙ ♙ ♙ ♙ ♙ ♙          │  │  🎮 Start Playing!   │ │
│   │     ♖ ♘ ♗ ♔ ♗ ♘ ♖          │  │                      │ │
│   │                              │  └──────────────────────┘ │
│   │                              │  ┌──────────────────────┐ │
│   │                              │  │ 🦉 Need a Hint?  [▼] │ │
│   │                              │  │                      │ │
│   │                              │  │  Bring your Knight   │ │
│   └──────────────────────────────┘  │  out to protect!     │ │
│                                     │                      │ │
│                                     │  ✨ Show me!          │ │
│                                     └──────────────────────┘ │
│                                     ┌──────────────────────┐ │
│                                     │ 📊 My Score!     [▼] │ │
│                                     │                      │ │
│                                     │  🌟 AWESOME MOVE!    │ │
│                                     │                      │ │
│                                     └──────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

---

*Design Version: 1.0*
*Created by: PM*
*Date: 2024*

# MINDFORGE — AI Agent Framework for Knowledge Transformation

## Project Overview

MINDFORGE is a web framework that transforms a user's vague idea into an interactive experience through a 4-chapter pipeline powered by AI agents. Each chapter is wrapped in a graphic novel storytelling style with a central metamorphosis object (an egg that transforms through stages).

### Core Concept
- **User**: Non-technical people who describe a problem in words
- **Pipeline**: Interview → Research → Quiz → Simulator
- **Visual metaphor**: Chaos cloud → Egg → Knowledge Egg → Glowing/Cracking Egg → Hatched creature
- **Theme (MVP)**: Cognitive biases and decision-making
- **Style**: Graphic novel, parchment/sepia tones, hand-drawn feel

### Architecture
- Sequential Pipeline pattern (from swarm intelligence research)
- Each agent produces a .md file passed to the next stage
- Storytelling is a cross-cutting concern (not a separate stage)
- Anthropic API calls happen client-side via `/v1/messages`

## Tech Stack

- **Vite** + **React 18** (JavaScript, not TypeScript)
- **CSS Modules** or inline styles (no Tailwind — graphic novel aesthetic needs custom styling)
- **Anthropic API** — Claude Sonnet 4 (`claude-sonnet-4-20250514`)
- No backend — pure SPA, API calls from browser

## Project Structure

```
mindforge/
├── CLAUDE.md              # This file
├── package.json
├── vite.config.js
├── index.html
├── public/
└── src/
    ├── main.jsx           # Entry point
    ├── App.jsx            # Root component with reducer + routing
    ├── styles.css         # Global styles, CSS variables, animations
    ├── api.js             # Anthropic API helper functions
    ├── reducer.js         # useReducer state management
    ├── prompts.js         # All AI agent system prompts
    ├── constants.js       # Colors, chapter metadata, narrator texts
    ├── components/
    │   ├── MetamorphosisObject.jsx  # Central SVG egg animation (5 stages)
    │   ├── Narrator.jsx             # Storytelling narrator box
    │   ├── SpeechBubble.jsx         # Chat bubble for interview
    │   ├── FileTransition.jsx       # Animated .md file transfer overlay
    │   ├── InsightCard.jsx          # Knowledge card for research stage
    │   ├── ChapterNav.jsx           # Top navigation between chapters
    │   ├── Button.jsx               # Styled button component
    │   └── LoadingQuill.jsx         # Loading animation (writing quill)
    └── chapters/
        ├── Intro.jsx      # Welcome screen (stage 0)
        ├── Chapter1.jsx   # "Fog of Choice" — Interview (Goldratt method)
        ├── Chapter2.jsx   # "Library of Minds" — Research
        ├── Chapter3.jsx   # "Mirror of Mind" — Quiz
        └── Chapter4.jsx   # "Arena of Decisions" — Simulator
```

## Commands

```bash
npm install          # Install dependencies
npm run dev          # Start dev server (Vite, port 5173)
npm run build        # Production build to dist/
npm run preview      # Preview production build
```

## Key Design Decisions

1. **Egg metamorphosis is the visual anchor** — it appears on every chapter screen and transforms based on progress. The SVG is self-contained with CSS/SMIL animations.

2. **State flows through .md files** — each chapter generates a markdown-like string that becomes input for the next chapter's AI agent. State is managed via `useReducer`.

3. **No localStorage** — all state lives in React state. Session resets on refresh.

4. **API calls are direct** — no proxy server. The Anthropic API is called from the browser. The artifact environment handles auth automatically.

5. **Prompts produce JSON** — all AI agents except the interviewer return structured JSON for UI rendering. The interviewer returns natural language with a `КОРЕНЬ:` marker for completion detection.

## AI Agents (4 agents in sequential pipeline)

| Agent | Role | Input | Output | Model |
|-------|------|-------|--------|-------|
| Interviewer | Goldratt method, finds root constraint | User's answers | `todo.md` (problem definition) | Sonnet 4 |
| Researcher | Finds 5 cognitive biases | `todo.md` | `research.md` (JSON with insights) | Sonnet 4 |
| Quiz Master | Creates 5 scenario-tests | `research.md` + `todo.md` | `quiz.md` (bias profile) | Sonnet 4 |
| Arena Master | Creates 3 decision scenarios | `quiz.md` + `todo.md` + `research.md` | Game data + creature name | Sonnet 4 |

## Visual Style Guide

- **Palette**: Parchment `#f4e4c1`, Ink `#2a1810`, Accent Red `#c4533a`, Green `#3a6b4f`, Gold `#b8860b`, Blue `#4a8ebb`
- **Font**: Georgia / Palatino (serif, book-like)
- **Borders**: 2-3px solid ink-colored, offset box shadows for "drawn" effect
- **Animations**: Fade-in with translateY, SVG SMIL for egg, CSS keyframes for loading
- **Tone**: Warm, sepia, parchment gradients, hand-crafted feel

## Patterns from Research Applied

- Sequential Pipeline (pattern #1 from Google's 21 agent patterns)
- File system as memory (Manus principle — .md files between agents)
- todo.md as attention mechanism (Manus)
- Human-in-the-loop (pattern #13 — user participates at every stage)
- Reflection (pattern #4 — quiz reflects on research)
- Plan-and-Execute economy (Sonnet for all, not Opus)
- Context Engineering > Model Selection (specialized prompts per agent)

## Future Roadmap

- [ ] Universal topic support (not just cognitive biases)
- [ ] Persistent storage for completed journeys
- [ ] Multiple creature types based on topic
- [ ] Sound effects and ambient audio
- [ ] Export final creature + wisdom as shareable card
- [ ] Backend with user accounts
- [ ] A2A protocol for inter-agent communication

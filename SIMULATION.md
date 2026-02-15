# Simulation Framework: Rules & Metrics

## Overview

The simulation is an experimental environment where generated games are instantiated, run with automated agents, and evaluated against quality metrics. It answers the question: "Is this generated game interesting?"

---

## 1. Simulation Model

### Core Loop

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   GENERATE   │────▶│   SIMULATE   │────▶│   EVALUATE   │
│              │     │              │     │              │
│ Compose game │     │ Run agents   │     │ Measure KPIs │
│ from grammar │     │ in game      │     │              │
│ + constraints│     │ instance     │     │ Score fitness │
└──────┬───────┘     └──────────────┘     └──────┬───────┘
       │                                         │
       │         ┌──────────────┐                │
       └─────────│   SELECT &   │◀───────────────┘
                 │   MUTATE     │
                 │              │
                 │ Keep best,   │
                 │ evolve rest  │
                 └──────────────┘
```

### Game State Representation

A generated game instance consists of:

```typescript
interface GameState {
  entities: Entity[];           // All game objects
  rules: Rule[];                // Active rule set
  goals: Goal[];                // Win/loss/scoring conditions
  resources: ResourcePool[];    // Tracked resources
  feedbackLoops: FeedbackLoop[]; // Identified feedback structures
  tick: number;                 // Current simulation step
  phase: GamePhase;             // Current game phase
}
```

### Agent Model

Automated agents play the generated games:

```typescript
interface Agent {
  id: string;
  role: Role;                   // Agent's role in the game
  strategy: Strategy;           // Decision-making approach
  state: AgentState;            // Current agent state
  history: Action[];            // Actions taken so far
}

type Strategy =
  | 'random'                    // Random valid actions
  | 'greedy'                    // Maximize immediate reward
  | 'exploratory'               // Try diverse actions
  | 'adversarial';              // Minimize opponent's score
```

---

## 2. Simulation Rules

### Rule Categories

#### 2.1 Structural Rules (define the game's shape)
- **Entity spawning**: When and how entities enter the game
- **Phase transitions**: How the game moves between phases
- **Boundary conditions**: Spatial, temporal, and resource limits

#### 2.2 Interaction Rules (define entity relationships)
- **Collision/contact**: What happens when entities meet
- **Transformation**: How entities change state
- **Resource exchange**: How resources flow between entities

#### 2.3 Progression Rules (define advancement)
- **Scoring**: What actions yield points
- **Leveling**: How entities grow/evolve
- **Unlocking**: What gates access to new content

#### 2.4 Termination Rules (define endings)
- **Win conditions**: How a player/team wins
- **Loss conditions**: How a player/team loses
- **Draw conditions**: When no winner is determined
- **Time limits**: Maximum duration

### Rule Encoding

Rules are expressed as typed functions:

```typescript
interface Rule {
  id: string;
  name: string;
  trigger: Trigger;             // When does this rule fire?
  condition: Condition;         // Under what circumstances?
  effect: Effect;               // What happens?
  priority: number;             // Resolution order
}

type Trigger =
  | { type: 'on_tick' }                           // Every game step
  | { type: 'on_event', event: string }           // When event fires
  | { type: 'on_state', predicate: Predicate }    // When state matches
  | { type: 'on_interaction', entities: [string, string] }; // When entities meet

type Effect =
  | { type: 'modify', target: string, property: string, delta: number }
  | { type: 'spawn', entity: EntityTemplate }
  | { type: 'destroy', target: string }
  | { type: 'transform', target: string, into: EntityTemplate }
  | { type: 'transfer', from: string, to: string, resource: string, amount: number }
  | { type: 'emit_event', event: string }
  | { type: 'sequence', effects: Effect[] }
  | { type: 'conditional', condition: Condition, then: Effect, else?: Effect };
```

---

## 3. Evaluation Metrics (KPIs)

### 3.1 Playability Metrics

| Metric | Definition | Target Range | Weight |
|--------|-----------|-------------|--------|
| **Completion Rate** | % of simulations that reach a terminal state | 80-100% | 0.15 |
| **Average Duration** | Mean ticks to completion | 50-500 ticks | 0.10 |
| **Decision Count** | Mean meaningful decisions per agent per game | 10-100 | 0.10 |
| **Deadlock Rate** | % of simulations stuck in non-terminal loops | 0-5% | 0.15 |

### 3.2 Balance Metrics

| Metric | Definition | Target Range | Weight |
|--------|-----------|-------------|--------|
| **Win Rate Variance** | Variance of win rates across agent strategies | < 0.1 (σ²) | 0.10 |
| **First-Mover Advantage** | Win rate delta between first and last player | < 10% | 0.05 |
| **Strategy Dominance** | Whether one strategy always wins | No dominant strategy | 0.10 |
| **Comeback Potential** | % of games where trailing player wins | 10-40% | 0.05 |

### 3.3 Emergence Metrics

| Metric | Definition | Target Range | Weight |
|--------|-----------|-------------|--------|
| **State Space Entropy** | Shannon entropy of visited game states | High (diverse states) | 0.05 |
| **Action Diversity** | Unique action sequences / total sequences | > 0.5 | 0.05 |
| **Feedback Loop Count** | Number of detected positive/negative loops | 2-10 | 0.05 |
| **Surprise Index** | Frequency of low-probability state transitions | > 0 | 0.05 |

### 3.4 Aesthetic Alignment (MDA)

Each generated game targets a subset of MDA aesthetics:

| Aesthetic | Proxy Metric |
|-----------|-------------|
| **Challenge** | Decision difficulty variance, loss rate |
| **Discovery** | New states visited over time (exploration curve) |
| **Expression** | Number of viable strategies |
| **Fellowship** | Cooperative action frequency |
| **Narrative** | State sequence coherence (arc detection) |
| **Sensation** | Visual/audio event frequency and variety |
| **Submission** | Flow state duration (uninterrupted play) |

### Composite Fitness Function

```
Fitness(game) = Σ(weight_i × normalize(metric_i))
```

Where `normalize` maps each metric to [0, 1] based on its target range (values within range → 1.0, values outside → decay toward 0).

---

## 4. Simulation Phases

### Phase 1: Initialization
- Generate game specification from grammar
- Instantiate entities, rules, goals
- Spawn agents with assigned roles and strategies

### Phase 2: Execution
- Run game loop (tick-based)
- Agents observe state, select actions, execute
- Rules fire based on triggers and conditions
- State transitions are recorded

### Phase 3: Analysis
- Compute all metrics
- Detect feedback loops via resource flow analysis
- Identify dominant strategies
- Calculate composite fitness score

### Phase 4: Selection
- Rank generated games by fitness
- Select top N for next generation
- Apply mutations (add/remove/modify rules, change parameters)
- Apply crossover (combine mechanics from two games)
- Generate new candidates

---

## 5. Experiment Protocol

### Initial Experiment: "Can the system generate a playable game?"

**Setup:**
- Component vocabulary: 10 basic components (Position, Health, Score, Inventory, Timer, Team, Damage, Healing, Collection, Movement)
- System vocabulary: 5 basic systems (MovementSystem, CollisionSystem, HealthSystem, ScoreSystem, TimerSystem)
- Grammar: simple 3-rule grammar generating entity configurations
- Agents: 2-4 agents with random/greedy strategies
- Generations: 100
- Population: 50 games per generation

**Success criteria:**
- At least 1 game achieves Fitness > 0.6
- That game is completable (has reachable win condition)
- That game has no deadlocks
- At least 2 different strategies can win

**What we learn:**
- Whether the primitive vocabulary is sufficient
- Whether the grammar rules produce valid compositions
- Whether the fitness function guides toward interesting games
- What minimal complexity threshold produces "playable" output

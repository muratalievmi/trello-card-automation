/**
 * Core type definitions for the Meta-Game Framework.
 *
 * The system is built on four primitives:
 *   Entity   — a unique identity that holds components
 *   Component — typed data attached to an entity
 *   System   — behavior that operates on entities with specific components
 *   Rule     — a trigger-condition-effect triple that governs state transitions
 */

// ---------------------------------------------------------------------------
// Entity & Component layer (ECS)
// ---------------------------------------------------------------------------

export type EntityId = string;

export interface Entity {
  id: EntityId;
  components: Map<ComponentType, Component>;
  tags: Set<string>;
}

export type ComponentType =
  | 'position'
  | 'health'
  | 'score'
  | 'inventory'
  | 'timer'
  | 'team'
  | 'damage'
  | 'healing'
  | 'collection'
  | 'movement'
  | 'appearance'
  | 'ai';

export interface Component {
  type: ComponentType;
  data: Record<string, unknown>;
}

// Concrete component data shapes
export interface PositionData {
  x: number;
  y: number;
}

export interface HealthData {
  current: number;
  max: number;
}

export interface ScoreData {
  value: number;
}

export interface InventoryData {
  items: string[];
  capacity: number;
}

export interface TimerData {
  remaining: number;
  total: number;
  active: boolean;
}

export interface TeamData {
  teamId: string;
}

export interface DamageData {
  amount: number;
  type: string;
}

export interface HealingData {
  amount: number;
}

export interface CollectionData {
  collectibleType: string;
  radius: number;
}

export interface MovementData {
  speed: number;
  direction: { dx: number; dy: number };
}

export interface AppearanceData {
  shape: 'circle' | 'square' | 'triangle' | 'star';
  color: string;
  size: number;
}

export interface AIData {
  strategy: Strategy;
  aggressiveness: number; // 0..1
}

// ---------------------------------------------------------------------------
// Rule layer
// ---------------------------------------------------------------------------

export interface Rule {
  id: string;
  name: string;
  trigger: Trigger;
  condition: Condition;
  effect: Effect;
  priority: number;
}

export type Trigger =
  | { type: 'on_tick' }
  | { type: 'on_event'; event: string }
  | { type: 'on_state'; predicate: Predicate }
  | { type: 'on_interaction'; entityTags: [string, string] };

export type Condition =
  | { type: 'always' }
  | { type: 'component_check'; entityTag: string; component: ComponentType; property: string; op: CompareOp; value: number }
  | { type: 'and'; conditions: Condition[] }
  | { type: 'or'; conditions: Condition[] }
  | { type: 'not'; condition: Condition };

export type CompareOp = 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte';

export type Effect =
  | { type: 'modify'; targetTag: string; component: ComponentType; property: string; delta: number }
  | { type: 'set'; targetTag: string; component: ComponentType; property: string; value: unknown }
  | { type: 'spawn'; template: EntityTemplate }
  | { type: 'destroy'; targetTag: string }
  | { type: 'transfer'; fromTag: string; toTag: string; resource: string; amount: number }
  | { type: 'emit_event'; event: string }
  | { type: 'sequence'; effects: Effect[] }
  | { type: 'conditional'; condition: Condition; then: Effect; else?: Effect };

export type Predicate = (state: GameState) => boolean;

// ---------------------------------------------------------------------------
// Goal layer
// ---------------------------------------------------------------------------

export interface Goal {
  id: string;
  name: string;
  description: string;
  condition: Condition;
  type: 'win' | 'lose' | 'score';
  targetRole?: string;
}

// ---------------------------------------------------------------------------
// Role layer
// ---------------------------------------------------------------------------

export interface Role {
  id: string;
  name: string;
  description: string;
  allowedActions: string[];
  initialComponents: ComponentType[];
}

// ---------------------------------------------------------------------------
// Game definition
// ---------------------------------------------------------------------------

export interface EntityTemplate {
  tags: string[];
  components: Component[];
}

export interface GameDefinition {
  id: string;
  name: string;
  description: string;
  roles: Role[];
  entityTemplates: EntityTemplate[];
  rules: Rule[];
  goals: Goal[];
  config: GameConfig;
}

export interface GameConfig {
  maxTicks: number;
  boardWidth: number;
  boardHeight: number;
  minPlayers: number;
  maxPlayers: number;
}

// ---------------------------------------------------------------------------
// Runtime state
// ---------------------------------------------------------------------------

export interface GameState {
  definition: GameDefinition;
  entities: Map<EntityId, Entity>;
  tick: number;
  phase: GamePhase;
  events: GameEvent[];
  scores: Map<string, number>; // role/team → score
  terminated: boolean;
  result: GameResult | null;
}

export type GamePhase = 'setup' | 'playing' | 'ended';

export interface GameEvent {
  tick: number;
  type: string;
  data: Record<string, unknown>;
}

export interface GameResult {
  winner: string | null; // role id or null for draw
  scores: Record<string, number>;
  duration: number;
  reason: string;
}

// ---------------------------------------------------------------------------
// Agent / Strategy
// ---------------------------------------------------------------------------

export type Strategy = 'random' | 'greedy' | 'exploratory' | 'adversarial';

export interface Agent {
  id: string;
  role: Role;
  strategy: Strategy;
  entityId: EntityId;
}

export interface AgentAction {
  agentId: string;
  type: string;
  params: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Metrics
// ---------------------------------------------------------------------------

export interface SimulationMetrics {
  completionRate: number;
  averageDuration: number;
  decisionCount: number;
  deadlockRate: number;
  winRateVariance: number;
  firstMoverAdvantage: number;
  strategyDominance: boolean;
  comebackPotential: number;
  stateSpaceEntropy: number;
  actionDiversity: number;
  feedbackLoopCount: number;
  surpriseIndex: number;
  fitness: number;
}

import {
  GameDefinition,
  GameState,
  GamePhase,
  Entity,
  EntityId,
  Rule,
  Condition,
  Effect,
  CompareOp,
  GameEvent,
  GameResult,
  Agent,
  AgentAction,
} from '../core/types.js';
import { createEntity, getComponent, hasTag } from '../core/entity.js';

/**
 * The game engine instantiates a GameDefinition into a running GameState,
 * processes rules each tick, and evaluates goals.
 */
export class GameEngine {
  private state: GameState;
  private agents: Agent[] = [];

  constructor(definition: GameDefinition) {
    this.state = {
      definition,
      entities: new Map(),
      tick: 0,
      phase: 'setup',
      events: [],
      scores: new Map(),
      terminated: false,
      result: null,
    };
  }

  getState(): Readonly<GameState> {
    return this.state;
  }

  /** Initialize the game: spawn initial entities, register agents. */
  setup(agents: Agent[]): void {
    this.agents = agents;

    // Spawn initial entities from templates
    for (const template of this.state.definition.entityTemplates) {
      const entity = createEntity(template);
      this.state.entities.set(entity.id, entity);
    }

    // Assign agent entities
    for (const agent of this.agents) {
      this.state.entities.set(agent.entityId, this.state.entities.get(agent.entityId)!);
    }

    // Initialize scores
    for (const role of this.state.definition.roles) {
      this.state.scores.set(role.id, 0);
    }

    this.state.phase = 'playing';
  }

  /** Run one tick of the game loop. */
  tick(): void {
    if (this.state.terminated) return;

    this.state.tick++;

    // 1. Process rules in priority order
    const sortedRules = [...this.state.definition.rules].sort(
      (a, b) => b.priority - a.priority
    );

    for (const rule of sortedRules) {
      if (this.shouldTrigger(rule)) {
        if (this.evaluateCondition(rule.condition)) {
          this.applyEffect(rule.effect);
        }
      }
    }

    // 2. Check goals
    this.checkGoals();

    // 3. Check timeout
    if (this.state.tick >= this.state.definition.config.maxTicks) {
      this.terminate('timeout');
    }

    // 4. Clear tick events
    this.state.events = this.state.events.filter(
      (e) => e.tick === this.state.tick
    );
  }

  /** Run the game to completion. */
  run(maxTicks?: number): GameResult {
    const limit = maxTicks ?? this.state.definition.config.maxTicks;

    while (!this.state.terminated && this.state.tick < limit) {
      this.tick();
    }

    if (!this.state.result) {
      this.terminate('timeout');
    }

    return this.state.result!;
  }

  /** Emit a game event. */
  emitEvent(type: string, data: Record<string, unknown> = {}): void {
    this.state.events.push({ tick: this.state.tick, type, data });
  }

  /** Execute an agent action. */
  executeAction(action: AgentAction): void {
    this.emitEvent(action.type, { agentId: action.agentId, ...action.params });
  }

  // -----------------------------------------------------------------------
  // Rule evaluation
  // -----------------------------------------------------------------------

  private shouldTrigger(rule: Rule): boolean {
    const trigger = rule.trigger;

    switch (trigger.type) {
      case 'on_tick':
        return true;

      case 'on_event':
        return this.state.events.some((e) => e.type === trigger.event);

      case 'on_state':
        return trigger.predicate(this.state);

      case 'on_interaction': {
        const [tagA, tagB] = trigger.entityTags;
        const entitiesA = this.getEntitiesByTag(tagA);
        const entitiesB = this.getEntitiesByTag(tagB);
        // Check proximity-based interaction
        for (const a of entitiesA) {
          for (const b of entitiesB) {
            if (a.id !== b.id && this.areInteracting(a, b)) {
              return true;
            }
          }
        }
        return false;
      }

      default:
        return false;
    }
  }

  evaluateCondition(condition: Condition): boolean {
    switch (condition.type) {
      case 'always':
        return true;

      case 'component_check': {
        const entities = this.getEntitiesByTag(condition.entityTag);
        return entities.some((entity) => {
          const data = getComponent(entity, condition.component);
          if (!data) return false;
          const val = (data as Record<string, unknown>)[condition.property];
          if (typeof val !== 'number') return false;
          return this.compare(val, condition.op, condition.value);
        });
      }

      case 'and':
        return condition.conditions.every((c) => this.evaluateCondition(c));

      case 'or':
        return condition.conditions.some((c) => this.evaluateCondition(c));

      case 'not':
        return !this.evaluateCondition(condition.condition);

      default:
        return false;
    }
  }

  private applyEffect(effect: Effect): void {
    switch (effect.type) {
      case 'modify': {
        const entities = this.getEntitiesByTag(effect.targetTag);
        for (const entity of entities) {
          const comp = entity.components.get(effect.component);
          if (comp && typeof (comp.data as Record<string, number>)[effect.property] === 'number') {
            (comp.data as Record<string, number>)[effect.property] += effect.delta;
          }
        }
        break;
      }

      case 'set': {
        const entities = this.getEntitiesByTag(effect.targetTag);
        for (const entity of entities) {
          const comp = entity.components.get(effect.component);
          if (comp) {
            (comp.data as Record<string, unknown>)[effect.property] = effect.value;
          }
        }
        break;
      }

      case 'spawn': {
        const entity = createEntity(effect.template);
        this.state.entities.set(entity.id, entity);
        break;
      }

      case 'destroy': {
        const toRemove: EntityId[] = [];
        for (const [id, entity] of this.state.entities) {
          if (hasTag(entity, effect.targetTag)) {
            toRemove.push(id);
          }
        }
        for (const id of toRemove) {
          this.state.entities.delete(id);
        }
        break;
      }

      case 'transfer': {
        // Simple resource transfer between tagged entities
        const from = this.getEntitiesByTag(effect.fromTag);
        const to = this.getEntitiesByTag(effect.toTag);
        if (from.length > 0 && to.length > 0) {
          const scoreFrom = this.state.scores.get(effect.fromTag) ?? 0;
          const scoreTo = this.state.scores.get(effect.toTag) ?? 0;
          const transferAmount = Math.min(effect.amount, scoreFrom);
          this.state.scores.set(effect.fromTag, scoreFrom - transferAmount);
          this.state.scores.set(effect.toTag, scoreTo + transferAmount);
        }
        break;
      }

      case 'emit_event':
        this.emitEvent(effect.event);
        break;

      case 'sequence':
        for (const subEffect of effect.effects) {
          this.applyEffect(subEffect);
        }
        break;

      case 'conditional':
        if (this.evaluateCondition(effect.condition)) {
          this.applyEffect(effect.then);
        } else if (effect.else) {
          this.applyEffect(effect.else);
        }
        break;
    }
  }

  // -----------------------------------------------------------------------
  // Goal checking
  // -----------------------------------------------------------------------

  private checkGoals(): void {
    for (const goal of this.state.definition.goals) {
      if (this.evaluateCondition(goal.condition)) {
        if (goal.type === 'win') {
          this.terminate('goal_reached', goal.targetRole ?? null, goal.name);
        } else if (goal.type === 'lose') {
          // The targeted role loses — find another winner
          const otherRoles = this.state.definition.roles.filter(
            (r) => r.id !== goal.targetRole
          );
          const winner = otherRoles.length === 1 ? otherRoles[0].id : null;
          this.terminate('goal_reached', winner, goal.name);
        }
      }
    }
  }

  private terminate(
    reason: string,
    winner: string | null = null,
    goalName?: string
  ): void {
    this.state.terminated = true;
    this.state.phase = 'ended';
    this.state.result = {
      winner,
      scores: Object.fromEntries(this.state.scores),
      duration: this.state.tick,
      reason: goalName ? `${reason}: ${goalName}` : reason,
    };
  }

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  private getEntitiesByTag(tag: string): Entity[] {
    const result: Entity[] = [];
    for (const entity of this.state.entities.values()) {
      if (hasTag(entity, tag)) {
        result.push(entity);
      }
    }
    return result;
  }

  private areInteracting(a: Entity, b: Entity): boolean {
    const posA = getComponent<{ x: number; y: number }>(a, 'position');
    const posB = getComponent<{ x: number; y: number }>(b, 'position');
    if (!posA || !posB) return false;

    const dx = posA.x - posB.x;
    const dy = posA.y - posB.y;
    const dist = Math.sqrt(dx * dx + dy * dy);

    return dist < 1.5; // interaction radius
  }

  private compare(a: number, op: CompareOp, b: number): boolean {
    switch (op) {
      case 'eq': return a === b;
      case 'neq': return a !== b;
      case 'gt': return a > b;
      case 'gte': return a >= b;
      case 'lt': return a < b;
      case 'lte': return a <= b;
    }
  }
}

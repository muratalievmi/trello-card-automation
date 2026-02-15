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
 *
 * Key design: on_interaction rules are processed per interacting pair, so
 * effects like "destroy collectible" only affect the specific entity in that
 * interaction, not all entities with that tag.
 */
export class GameEngine {
  private state: GameState;
  private agents: Agent[] = [];
  private rngState: number = 12345;

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

  private nextRandom(): number {
    this.rngState = (this.rngState * 1664525 + 1013904223) & 0xffffffff;
    return (this.rngState >>> 0) / 0xffffffff;
  }

  setup(agents: Agent[]): void {
    this.agents = agents;

    for (const template of this.state.definition.entityTemplates) {
      const entity = createEntity(template);
      this.state.entities.set(entity.id, entity);
    }

    for (const agent of this.agents) {
      this.state.entities.set(agent.entityId, this.state.entities.get(agent.entityId)!);
    }

    for (const role of this.state.definition.roles) {
      this.state.scores.set(role.id, 0);
    }

    this.state.phase = 'playing';
  }

  tick(): void {
    if (this.state.terminated) return;

    this.state.tick++;

    // 1. Agent decisions
    this.processAgentActions();

    // 2. Movement
    this.processMovement();

    // 3. Process rules
    const sortedRules = [...this.state.definition.rules].sort(
      (a, b) => b.priority - a.priority
    );

    for (const rule of sortedRules) {
      if (this.state.terminated) break;

      if (rule.trigger.type === 'on_interaction') {
        // Interaction rules are processed per-pair with scoped effects
        this.processInteractionRule(rule);
      } else {
        if (this.shouldTrigger(rule) && this.evaluateCondition(rule.condition)) {
          this.applyEffect(rule.effect);
        }
      }
    }

    // 4. Check goals
    if (!this.state.terminated) {
      this.checkGoals();
    }

    // 5. Check timeout
    if (!this.state.terminated && this.state.tick >= this.state.definition.config.maxTicks) {
      this.terminate('timeout');
    }

    // 6. Clear tick events
    this.state.events = this.state.events.filter(
      (e) => e.tick === this.state.tick
    );
  }

  // -----------------------------------------------------------------------
  // Agent action system
  // -----------------------------------------------------------------------

  private processAgentActions(): void {
    for (const agent of this.agents) {
      const entity = this.state.entities.get(agent.entityId);
      if (!entity) continue;

      const pos = getComponent<{ x: number; y: number }>(entity, 'position');
      const mov = getComponent<{ speed: number; direction: { dx: number; dy: number } }>(entity, 'movement');
      if (!pos || !mov) continue;

      const dir = this.chooseDirection(agent, entity, pos);
      mov.direction.dx = dir.dx;
      mov.direction.dy = dir.dy;
    }
  }

  private chooseDirection(
    agent: Agent,
    entity: Entity,
    pos: { x: number; y: number }
  ): { dx: number; dy: number } {
    switch (agent.strategy) {
      case 'greedy':
        return this.greedyDirection(entity, pos);
      case 'adversarial':
        return this.adversarialDirection(entity, pos);
      case 'exploratory':
        return this.nextRandom() < 0.5
          ? this.greedyDirection(entity, pos)
          : this.randomDirection();
      case 'random':
      default:
        return this.randomDirection();
    }
  }

  private randomDirection(): { dx: number; dy: number } {
    const directions = [
      { dx: 1, dy: 0 }, { dx: -1, dy: 0 },
      { dx: 0, dy: 1 }, { dx: 0, dy: -1 },
      { dx: 1, dy: 1 }, { dx: -1, dy: -1 },
      { dx: 1, dy: -1 }, { dx: -1, dy: 1 },
    ];
    return directions[Math.floor(this.nextRandom() * directions.length)];
  }

  private greedyDirection(
    entity: Entity,
    pos: { x: number; y: number }
  ): { dx: number; dy: number } {
    let bestTarget: { x: number; y: number } | null = null;
    let bestDist = Infinity;

    // First priority: collectibles and finish lines
    for (const other of this.state.entities.values()) {
      if (other.id === entity.id) continue;
      if (!hasTag(other, 'collectible') && !hasTag(other, 'finish_line')) continue;

      const otherPos = getComponent<{ x: number; y: number }>(other, 'position');
      if (!otherPos) continue;

      const dist = Math.abs(otherPos.x - pos.x) + Math.abs(otherPos.y - pos.y);
      if (dist < bestDist) {
        bestDist = dist;
        bestTarget = otherPos;
      }
    }

    // Fallback: target enemy players (for combat scenarios)
    if (!bestTarget) {
      for (const other of this.state.entities.values()) {
        if (other.id === entity.id) continue;
        if (!hasTag(other, 'player')) continue;

        const otherPos = getComponent<{ x: number; y: number }>(other, 'position');
        if (!otherPos) continue;

        const dist = Math.abs(otherPos.x - pos.x) + Math.abs(otherPos.y - pos.y);
        if (dist < bestDist) {
          bestDist = dist;
          bestTarget = otherPos;
        }
      }
    }

    if (!bestTarget) return this.randomDirection();

    const dx = Math.sign(bestTarget.x - pos.x);
    const dy = Math.sign(bestTarget.y - pos.y);
    if (dx === 0 && dy === 0) return this.randomDirection();
    return { dx, dy };
  }

  private adversarialDirection(
    entity: Entity,
    pos: { x: number; y: number }
  ): { dx: number; dy: number } {
    let bestTarget: { x: number; y: number } | null = null;
    let bestDist = Infinity;

    for (const other of this.state.entities.values()) {
      if (other.id === entity.id) continue;
      if (!hasTag(other, 'player')) continue;

      const otherPos = getComponent<{ x: number; y: number }>(other, 'position');
      if (!otherPos) continue;

      const dist = Math.abs(otherPos.x - pos.x) + Math.abs(otherPos.y - pos.y);
      if (dist < bestDist) {
        bestDist = dist;
        bestTarget = otherPos;
      }
    }

    if (!bestTarget) return this.randomDirection();

    return {
      dx: Math.sign(bestTarget.x - pos.x),
      dy: Math.sign(bestTarget.y - pos.y),
    };
  }

  // -----------------------------------------------------------------------
  // Movement processing
  // -----------------------------------------------------------------------

  private processMovement(): void {
    const { boardWidth, boardHeight } = this.state.definition.config;

    for (const entity of this.state.entities.values()) {
      const pos = getComponent<{ x: number; y: number }>(entity, 'position');
      const mov = getComponent<{ speed: number; direction: { dx: number; dy: number } }>(entity, 'movement');
      if (!pos || !mov) continue;
      if (mov.direction.dx === 0 && mov.direction.dy === 0) continue;

      pos.x = Math.max(0, Math.min(boardWidth - 1, pos.x + mov.direction.dx * mov.speed));
      pos.y = Math.max(0, Math.min(boardHeight - 1, pos.y + mov.direction.dy * mov.speed));
    }
  }

  // -----------------------------------------------------------------------
  // Interaction rule processing (pair-scoped)
  // -----------------------------------------------------------------------

  /**
   * Process an on_interaction rule for every interacting pair.
   * Effects are scoped: tagA targets entity A, tagB targets entity B.
   */
  private processInteractionRule(rule: Rule): void {
    if (rule.trigger.type !== 'on_interaction') return;

    const [tagA, tagB] = rule.trigger.entityTags;
    const entitiesA = this.getEntitiesByTag(tagA);
    const entitiesB = this.getEntitiesByTag(tagB);

    for (const a of entitiesA) {
      for (const b of entitiesB) {
        if (this.state.terminated) return;
        if (a.id === b.id) continue;
        if (!this.state.entities.has(a.id) || !this.state.entities.has(b.id)) continue;
        if (!this.areInteracting(a, b)) continue;

        if (this.evaluateCondition(rule.condition)) {
          this.applyScopedEffect(rule.effect, tagA, a, tagB, b);
        }
      }
    }
  }

  /**
   * Apply effect scoped to a specific interacting pair.
   * When targetTag matches tagA → affect only entityA.
   * When targetTag matches tagB → affect only entityB.
   */
  private applyScopedEffect(
    effect: Effect,
    tagA: string,
    entityA: Entity,
    tagB: string,
    entityB: Entity
  ): void {
    switch (effect.type) {
      case 'modify': {
        const target = this.resolveInteractionTarget(effect.targetTag, tagA, entityA, tagB, entityB);
        if (target) {
          const comp = target.components.get(effect.component);
          if (comp && typeof (comp.data as Record<string, number>)[effect.property] === 'number') {
            (comp.data as Record<string, number>)[effect.property] += effect.delta;
          }
        }
        break;
      }

      case 'set': {
        const target = this.resolveInteractionTarget(effect.targetTag, tagA, entityA, tagB, entityB);
        if (target) {
          const comp = target.components.get(effect.component);
          if (comp) {
            (comp.data as Record<string, unknown>)[effect.property] = effect.value;
          }
        }
        break;
      }

      case 'destroy': {
        const target = this.resolveInteractionTarget(effect.targetTag, tagA, entityA, tagB, entityB);
        if (target) {
          this.state.entities.delete(target.id);
        }
        break;
      }

      case 'sequence':
        for (const sub of effect.effects) {
          this.applyScopedEffect(sub, tagA, entityA, tagB, entityB);
        }
        break;

      case 'conditional':
        if (this.evaluateCondition(effect.condition)) {
          this.applyScopedEffect(effect.then, tagA, entityA, tagB, entityB);
        } else if (effect.else) {
          this.applyScopedEffect(effect.else, tagA, entityA, tagB, entityB);
        }
        break;

      default:
        // For other effect types, fall back to global apply
        this.applyEffect(effect);
        break;
    }
  }

  /** Map a targetTag to the specific entity in an interaction pair. */
  private resolveInteractionTarget(
    targetTag: string,
    tagA: string,
    entityA: Entity,
    tagB: string,
    entityB: Entity
  ): Entity | null {
    if (targetTag === tagA || hasTag(entityA, targetTag)) return entityA;
    if (targetTag === tagB || hasTag(entityB, targetTag)) return entityB;
    return null;
  }

  // -----------------------------------------------------------------------
  // Main loop
  // -----------------------------------------------------------------------

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

  emitEvent(type: string, data: Record<string, unknown> = {}): void {
    this.state.events.push({ tick: this.state.tick, type, data });
  }

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

      case 'on_interaction':
        // Handled separately in processInteractionRule
        return false;

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
      if (this.state.terminated) break;
      if (this.evaluateCondition(goal.condition)) {
        if (goal.type === 'win') {
          this.terminate('goal_reached', goal.targetRole ?? null, goal.name);
        } else if (goal.type === 'lose') {
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
    if (this.state.terminated) return;
    this.state.terminated = true;
    this.state.phase = 'ended';

    // Sync entity component scores to state scores
    for (const agent of this.agents) {
      const entity = this.state.entities.get(agent.entityId);
      if (!entity) continue;
      const scoreData = getComponent<{ value: number }>(entity, 'score');
      if (scoreData) {
        this.state.scores.set(agent.role.id, scoreData.value);
      }
    }

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

    return dist < 1.5;
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

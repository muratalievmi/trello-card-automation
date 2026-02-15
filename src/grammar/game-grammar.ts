import {
  GameDefinition,
  EntityTemplate,
  Rule,
  Goal,
  Role,
  Component,
  ComponentType,
  GameConfig,
} from '../core/types.js';

/**
 * Game grammar: generates GameDefinitions by composing primitives.
 *
 * The grammar operates in two modes:
 *   1. Template-based: combine predefined mechanic modules
 *   2. Generative: use production rules to expand a seed into a full game
 *
 * This module implements the Template-based approach as the initial strategy.
 */

// ---------------------------------------------------------------------------
// Mechanic Modules — reusable building blocks
// ---------------------------------------------------------------------------

export interface MechanicModule {
  name: string;
  description: string;
  requiredComponents: ComponentType[];
  entityTemplates: EntityTemplate[];
  rules: Rule[];
  goals: Goal[];
}

/** Collection mechanic: entities collect items to score points. */
export const CollectionMechanic: MechanicModule = {
  name: 'collection',
  description: 'Entities collect items scattered on the board',
  requiredComponents: ['position', 'score', 'collection'],
  entityTemplates: [
    {
      tags: ['collectible', 'item'],
      components: [
        { type: 'position', data: { x: 0, y: 0 } },
        { type: 'appearance', data: { shape: 'star', color: '#FFD700', size: 0.5 } },
      ],
    },
  ],
  rules: [
    {
      id: 'collect_item',
      name: 'Collect Item',
      trigger: { type: 'on_interaction', entityTags: ['player', 'collectible'] },
      condition: { type: 'always' },
      effect: {
        type: 'sequence',
        effects: [
          { type: 'modify', targetTag: 'player', component: 'score', property: 'value', delta: 1 },
          { type: 'destroy', targetTag: 'collectible' },
        ],
      },
      priority: 10,
    },
  ],
  goals: [
    {
      id: 'collect_all',
      name: 'Collect All Items',
      description: 'First player to collect all items wins',
      condition: {
        type: 'component_check',
        entityTag: 'player',
        component: 'score',
        property: 'value',
        op: 'gte',
        value: 10,
      },
      type: 'win',
    },
  ],
};

/** Combat mechanic: entities deal damage to each other. */
export const CombatMechanic: MechanicModule = {
  name: 'combat',
  description: 'Entities can damage each other through proximity',
  requiredComponents: ['position', 'health', 'damage'],
  entityTemplates: [],
  rules: [
    {
      id: 'deal_damage',
      name: 'Deal Damage on Contact',
      trigger: { type: 'on_interaction', entityTags: ['attacker', 'defender'] },
      condition: { type: 'always' },
      effect: {
        type: 'modify',
        targetTag: 'defender',
        component: 'health',
        property: 'current',
        delta: -1,
      },
      priority: 5,
    },
    {
      id: 'death_check',
      name: 'Remove Dead Entities',
      trigger: { type: 'on_tick' },
      condition: {
        type: 'component_check',
        entityTag: 'defender',
        component: 'health',
        property: 'current',
        op: 'lte',
        value: 0,
      },
      effect: { type: 'destroy', targetTag: 'defender' },
      priority: 1,
    },
  ],
  goals: [
    {
      id: 'last_standing',
      name: 'Last Entity Standing',
      description: 'The last surviving entity wins',
      condition: {
        type: 'component_check',
        entityTag: 'defender',
        component: 'health',
        property: 'current',
        op: 'lte',
        value: 0,
      },
      type: 'lose',
      targetRole: 'defender',
    },
  ],
};

/** Survival mechanic: a timer ticks down; survive to win. */
export const SurvivalMechanic: MechanicModule = {
  name: 'survival',
  description: 'Survive for a given number of ticks to win',
  requiredComponents: ['health', 'timer'],
  entityTemplates: [],
  rules: [
    {
      id: 'tick_timer',
      name: 'Countdown Timer',
      trigger: { type: 'on_tick' },
      condition: { type: 'always' },
      effect: {
        type: 'modify',
        targetTag: 'player',
        component: 'timer',
        property: 'remaining',
        delta: -1,
      },
      priority: 0,
    },
  ],
  goals: [
    {
      id: 'survive_timer',
      name: 'Survive Until Timer Ends',
      description: 'Survive until the timer reaches zero',
      condition: {
        type: 'component_check',
        entityTag: 'player',
        component: 'timer',
        property: 'remaining',
        op: 'lte',
        value: 0,
      },
      type: 'win',
    },
  ],
};

/** Race mechanic: first to reach a target position wins. */
export const RaceMechanic: MechanicModule = {
  name: 'race',
  description: 'First entity to reach the goal position wins',
  requiredComponents: ['position', 'movement'],
  entityTemplates: [
    {
      tags: ['finish_line'],
      components: [
        { type: 'position', data: { x: 9, y: 9 } },
        { type: 'appearance', data: { shape: 'square', color: '#00FF00', size: 1 } },
      ],
    },
  ],
  rules: [],
  goals: [
    {
      id: 'reach_finish',
      name: 'Reach the Finish Line',
      description: 'First player to reach the finish line wins',
      condition: {
        type: 'component_check',
        entityTag: 'player',
        component: 'position',
        property: 'x',
        op: 'gte',
        value: 9,
      },
      type: 'win',
    },
  ],
};

// ---------------------------------------------------------------------------
// Module Registry
// ---------------------------------------------------------------------------

export const MECHANIC_MODULES: Record<string, MechanicModule> = {
  collection: CollectionMechanic,
  combat: CombatMechanic,
  survival: SurvivalMechanic,
  race: RaceMechanic,
};

// ---------------------------------------------------------------------------
// Game Generator
// ---------------------------------------------------------------------------

export interface GenerationParams {
  mechanics: string[];        // which mechanic modules to include
  playerCount: number;
  boardSize: number;
  maxTicks: number;
  seed?: number;
}

/** Simple seeded pseudo-random number generator. */
class SeededRandom {
  private state: number;

  constructor(seed: number) {
    this.state = seed;
  }

  next(): number {
    this.state = (this.state * 1664525 + 1013904223) & 0xffffffff;
    return (this.state >>> 0) / 0xffffffff;
  }

  nextInt(min: number, max: number): number {
    return Math.floor(this.next() * (max - min + 1)) + min;
  }

  pick<T>(arr: T[]): T {
    return arr[this.nextInt(0, arr.length - 1)];
  }
}

/**
 * Generate a GameDefinition by composing mechanic modules.
 */
export function generateGame(params: GenerationParams): GameDefinition {
  const rng = new SeededRandom(params.seed ?? Date.now());
  const id = `game_${rng.nextInt(1000, 9999)}`;

  // Gather modules
  const modules = params.mechanics
    .map((name) => MECHANIC_MODULES[name])
    .filter(Boolean);

  if (modules.length === 0) {
    throw new Error('At least one valid mechanic module is required');
  }

  // Merge entity templates
  const entityTemplates: EntityTemplate[] = [];

  // Create player templates
  const playerColors = ['#FF4444', '#4444FF', '#44FF44', '#FFFF44'];
  for (let i = 0; i < params.playerCount; i++) {
    const components: Component[] = [
      { type: 'position', data: { x: rng.nextInt(0, params.boardSize - 1), y: rng.nextInt(0, params.boardSize - 1) } },
      { type: 'appearance', data: { shape: 'circle', color: playerColors[i % playerColors.length], size: 1 } },
      { type: 'movement', data: { speed: 1, direction: { dx: 0, dy: 0 } } },
    ];

    // Add components required by selected mechanics
    const neededComponents = new Set<ComponentType>();
    for (const mod of modules) {
      for (const comp of mod.requiredComponents) {
        neededComponents.add(comp);
      }
    }

    // Add missing required components with defaults
    if (neededComponents.has('health') && !components.some((c) => c.type === 'health')) {
      components.push({ type: 'health', data: { current: 10, max: 10 } });
    }
    if (neededComponents.has('score') && !components.some((c) => c.type === 'score')) {
      components.push({ type: 'score', data: { value: 0 } });
    }
    if (neededComponents.has('timer') && !components.some((c) => c.type === 'timer')) {
      components.push({ type: 'timer', data: { remaining: params.maxTicks, total: params.maxTicks, active: true } });
    }
    if (neededComponents.has('damage') && !components.some((c) => c.type === 'damage')) {
      components.push({ type: 'damage', data: { amount: 1, type: 'melee' } });
    }
    if (neededComponents.has('collection') && !components.some((c) => c.type === 'collection')) {
      components.push({ type: 'collection', data: { collectibleType: 'item', radius: 1.5 } });
    }
    if (neededComponents.has('inventory') && !components.some((c) => c.type === 'inventory')) {
      components.push({ type: 'inventory', data: { items: [], capacity: 10 } });
    }

    const tags = ['player', `player_${i}`];
    if (neededComponents.has('damage')) tags.push('attacker');
    if (neededComponents.has('health')) tags.push('defender');

    entityTemplates.push({ tags, components });
  }

  // Add module-specific entities (e.g., collectibles)
  for (const mod of modules) {
    for (const template of mod.entityTemplates) {
      // Spawn multiple instances with random positions
      const count = rng.nextInt(3, 10);
      for (let i = 0; i < count; i++) {
        const cloned = structuredClone(template);
        const posComp = cloned.components.find((c) => c.type === 'position');
        if (posComp) {
          posComp.data = { x: rng.nextInt(0, params.boardSize - 1), y: rng.nextInt(0, params.boardSize - 1) };
        }
        entityTemplates.push(cloned);
      }
    }
  }

  // Merge rules
  const rules: Rule[] = [];
  for (const mod of modules) {
    rules.push(...structuredClone(mod.rules));
  }

  // Merge goals
  const goals: Goal[] = [];
  for (const mod of modules) {
    goals.push(...structuredClone(mod.goals));
  }

  // Create roles
  const roles: Role[] = [];
  for (let i = 0; i < params.playerCount; i++) {
    roles.push({
      id: `player_${i}`,
      name: `Player ${i + 1}`,
      description: `Player ${i + 1}`,
      allowedActions: ['move', 'interact'],
      initialComponents: ['position', 'movement', 'appearance'],
    });
  }

  const config: GameConfig = {
    maxTicks: params.maxTicks,
    boardWidth: params.boardSize,
    boardHeight: params.boardSize,
    minPlayers: params.playerCount,
    maxPlayers: params.playerCount,
  };

  return {
    id,
    name: `Generated Game: ${modules.map((m) => m.name).join(' + ')}`,
    description: `A game combining: ${modules.map((m) => m.description).join('; ')}`,
    roles,
    entityTemplates,
    rules,
    goals,
    config,
  };
}

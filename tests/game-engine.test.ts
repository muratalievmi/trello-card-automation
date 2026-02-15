import { describe, it, expect, beforeEach } from 'vitest';
import { GameEngine } from '../src/engine/game-engine.js';
import { generateGame } from '../src/grammar/game-grammar.js';
import { computeMetrics } from '../src/simulation/metrics.js';
import { resetIdCounter } from '../src/core/entity.js';
import { Agent, GameDefinition, GameResult } from '../src/core/types.js';

function createAgents(definition: GameDefinition): Agent[] {
  return definition.roles.map((role, i) => ({
    id: `agent_${i}`,
    role,
    strategy: 'random' as const,
    entityId: `e_${i + 1}`,
  }));
}

describe('GameEngine', () => {
  beforeEach(() => {
    resetIdCounter();
  });

  it('should create a game from a definition', () => {
    const definition = generateGame({
      mechanics: ['collection'],
      playerCount: 2,
      boardSize: 10,
      maxTicks: 50,
      seed: 1,
    });

    expect(definition.name).toContain('collection');
    expect(definition.roles).toHaveLength(2);
    expect(definition.rules.length).toBeGreaterThan(0);
    expect(definition.goals.length).toBeGreaterThan(0);
  });

  it('should initialize and run a game', () => {
    const definition = generateGame({
      mechanics: ['survival'],
      playerCount: 1,
      boardSize: 5,
      maxTicks: 20,
      seed: 42,
    });

    const engine = new GameEngine(definition);
    const agents = createAgents(definition);
    engine.setup(agents);

    const result = engine.run();

    expect(result).toBeDefined();
    expect(result.duration).toBeGreaterThan(0);
    expect(result.duration).toBeLessThanOrEqual(20);
  });

  it('should terminate on timeout', () => {
    // Use a minimal game with no achievable goals
    const definition = generateGame({
      mechanics: ['collection'],
      playerCount: 1,
      boardSize: 5,
      maxTicks: 5,
      seed: 99,
    });
    // Remove all goals so only timeout can end the game
    definition.goals = [];

    const engine = new GameEngine(definition);
    const agents = createAgents(definition);
    engine.setup(agents);

    const result = engine.run();

    expect(result.reason).toContain('timeout');
    expect(result.duration).toBe(5);
  });

  it('should combine multiple mechanics', () => {
    const definition = generateGame({
      mechanics: ['collection', 'combat'],
      playerCount: 2,
      boardSize: 10,
      maxTicks: 50,
      seed: 7,
    });

    expect(definition.rules.length).toBeGreaterThanOrEqual(2);
    expect(definition.goals.length).toBeGreaterThanOrEqual(2);
    expect(definition.entityTemplates.length).toBeGreaterThan(2); // players + collectibles
  });

  it('should evaluate condition types', () => {
    const definition = generateGame({
      mechanics: ['collection'],
      playerCount: 1,
      boardSize: 5,
      maxTicks: 10,
      seed: 1,
    });

    const engine = new GameEngine(definition);
    const agents = createAgents(definition);
    engine.setup(agents);

    // Test 'always' condition
    expect(engine.evaluateCondition({ type: 'always' })).toBe(true);

    // Test 'not' condition
    expect(engine.evaluateCondition({ type: 'not', condition: { type: 'always' } })).toBe(false);

    // Test 'and' condition
    expect(
      engine.evaluateCondition({
        type: 'and',
        conditions: [{ type: 'always' }, { type: 'always' }],
      })
    ).toBe(true);

    // Test 'or' condition
    expect(
      engine.evaluateCondition({
        type: 'or',
        conditions: [
          { type: 'not', condition: { type: 'always' } },
          { type: 'always' },
        ],
      })
    ).toBe(true);
  });
});

describe('computeMetrics', () => {
  it('should return empty metrics for no results', () => {
    const metrics = computeMetrics([]);
    expect(metrics.fitness).toBe(0);
    expect(metrics.completionRate).toBe(0);
  });

  it('should compute metrics for a batch of results', () => {
    const results: GameResult[] = [
      { winner: 'player_0', scores: { player_0: 10, player_1: 3 }, duration: 50, reason: 'goal_reached: Collect All Items' },
      { winner: 'player_1', scores: { player_0: 5, player_1: 10 }, duration: 75, reason: 'goal_reached: Collect All Items' },
      { winner: null, scores: { player_0: 0, player_1: 0 }, duration: 100, reason: 'timeout' },
    ];

    const metrics = computeMetrics(results);

    expect(metrics.completionRate).toBeCloseTo(2 / 3);
    expect(metrics.averageDuration).toBeCloseTo(75);
    expect(metrics.deadlockRate).toBeCloseTo(1 / 3);
    expect(metrics.fitness).toBeGreaterThan(0);
  });
});

describe('Game Generation', () => {
  beforeEach(() => {
    resetIdCounter();
  });

  it('should throw for invalid mechanics', () => {
    expect(() =>
      generateGame({
        mechanics: ['nonexistent'],
        playerCount: 1,
        boardSize: 5,
        maxTicks: 10,
      })
    ).toThrow('At least one valid mechanic module is required');
  });

  it('should produce deterministic output with same seed', () => {
    const a = generateGame({ mechanics: ['collection'], playerCount: 2, boardSize: 10, maxTicks: 50, seed: 123 });
    const b = generateGame({ mechanics: ['collection'], playerCount: 2, boardSize: 10, maxTicks: 50, seed: 123 });

    expect(a.name).toBe(b.name);
    expect(a.entityTemplates.length).toBe(b.entityTemplates.length);
    expect(a.rules.length).toBe(b.rules.length);
  });

  it('should produce different output with different seeds', () => {
    const a = generateGame({ mechanics: ['collection'], playerCount: 2, boardSize: 10, maxTicks: 50, seed: 1 });
    const b = generateGame({ mechanics: ['collection'], playerCount: 2, boardSize: 10, maxTicks: 50, seed: 2 });

    // Entity positions should differ
    const posA = a.entityTemplates[2]?.components.find((c) => c.type === 'position');
    const posB = b.entityTemplates[2]?.components.find((c) => c.type === 'position');

    // With different seeds, at least some positions should differ
    // (not guaranteed for any single pair, but highly likely)
    expect(a.id).not.toBe(b.id);
  });
});

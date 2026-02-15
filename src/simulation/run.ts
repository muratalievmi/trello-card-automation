import { generateGame, GenerationParams, MECHANIC_MODULES } from '../grammar/game-grammar.js';
import { GameEngine } from '../engine/game-engine.js';
import { computeMetrics } from './metrics.js';
import { resetIdCounter } from '../core/entity.js';
import { Agent, GameResult, Strategy } from '../core/types.js';

/**
 * Run a batch simulation: generate games, run them, evaluate metrics.
 */

const STRATEGIES: Strategy[] = ['random', 'greedy', 'exploratory', 'adversarial'];

function runSingleGame(params: GenerationParams, seed: number): GameResult {
  resetIdCounter();

  const definition = generateGame({ ...params, seed });
  const engine = new GameEngine(definition);

  // Vary agent strategies across runs for better balance measurement
  const strategyOffset = seed % STRATEGIES.length;
  const agents: Agent[] = definition.roles.map((role, i) => ({
    id: `agent_${i}`,
    role,
    strategy: STRATEGIES[(i + strategyOffset) % STRATEGIES.length],
    entityId: `e_${i + 1}`,
  }));

  engine.setup(agents);
  return engine.run();
}

function runBatch(params: GenerationParams, batchSize: number): GameResult[] {
  const results: GameResult[] = [];
  for (let i = 0; i < batchSize; i++) {
    const result = runSingleGame(params, (params.seed ?? 0) + i);
    results.push(result);
  }
  return results;
}

// Main execution
const availableMechanics = Object.keys(MECHANIC_MODULES);

console.log('=== Meta-Game Framework: Simulation Runner ===\n');
console.log(`Available mechanics: ${availableMechanics.join(', ')}\n`);

// Run experiments with different mechanic combinations
const combinations = [
  ['collection'],
  ['combat'],
  ['survival'],
  ['race'],
  ['collection', 'combat'],
  ['collection', 'survival'],
  ['combat', 'survival'],
  ['collection', 'combat', 'survival'],
];

for (const mechanics of combinations) {
  const params: GenerationParams = {
    mechanics,
    playerCount: 2,
    boardSize: 10,
    maxTicks: 100,
    seed: 42,
  };

  console.log(`\n--- Mechanics: ${mechanics.join(' + ')} ---`);

  const results = runBatch(params, 20);
  const metrics = computeMetrics(results);

  console.log(`  Fitness:          ${metrics.fitness.toFixed(3)}`);
  console.log(`  Completion Rate:  ${(metrics.completionRate * 100).toFixed(1)}%`);
  console.log(`  Avg Duration:     ${metrics.averageDuration.toFixed(1)} ticks`);
  console.log(`  Deadlock Rate:    ${(metrics.deadlockRate * 100).toFixed(1)}%`);
  console.log(`  Win Rate Var:     ${metrics.winRateVariance.toFixed(4)}`);
  console.log(`  Strategy Dom:     ${metrics.strategyDominance ? 'YES' : 'no'}`);
  console.log(`  State Entropy:    ${metrics.stateSpaceEntropy.toFixed(3)}`);
}

console.log('\n=== Simulation Complete ===');

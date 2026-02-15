import { GameResult, SimulationMetrics } from '../core/types.js';

/**
 * Compute simulation metrics from a batch of game results.
 */
export function computeMetrics(results: GameResult[]): SimulationMetrics {
  if (results.length === 0) {
    return emptyMetrics();
  }

  const total = results.length;

  // Completion rate: games that ended with a result (not timeout)
  const completed = results.filter((r) => r.reason !== 'timeout');
  const completionRate = completed.length / total;

  // Average duration
  const averageDuration =
    results.reduce((sum, r) => sum + r.duration, 0) / total;

  // Decision count (placeholder — would need action logs)
  const decisionCount = averageDuration * 0.5; // rough proxy

  // Deadlock rate: games that timed out with no score changes
  const deadlocked = results.filter(
    (r) => r.reason === 'timeout' && Object.values(r.scores).every((s) => s === 0)
  );
  const deadlockRate = deadlocked.length / total;

  // Win rate variance
  const winCounts: Record<string, number> = {};
  for (const r of results) {
    if (r.winner) {
      winCounts[r.winner] = (winCounts[r.winner] ?? 0) + 1;
    }
  }
  const winRates = Object.values(winCounts).map((c) => c / total);
  const winRateVariance = variance(winRates);

  // First-mover advantage
  const player0Wins = winCounts['player_0'] ?? 0;
  const lastPlayerId = Object.keys(winCounts).sort().pop();
  const lastPlayerWins = lastPlayerId ? (winCounts[lastPlayerId] ?? 0) : 0;
  const firstMoverAdvantage =
    total > 0 ? Math.abs(player0Wins - lastPlayerWins) / total : 0;

  // Strategy dominance (simplified: check if one role wins >70%)
  const maxWinRate = Math.max(...winRates, 0);
  const strategyDominance = maxWinRate > 0.7;

  // Comeback potential (placeholder)
  const comebackPotential = completionRate > 0 ? 0.2 : 0;

  // State space entropy (proxy: score distribution entropy)
  const allScores = results.flatMap((r) => Object.values(r.scores));
  const stateSpaceEntropy = entropy(allScores);

  // Action diversity (proxy: unique winner count / total)
  const uniqueWinners = new Set(results.map((r) => r.winner).filter(Boolean));
  const actionDiversity = uniqueWinners.size / Math.max(1, Object.keys(winCounts).length);

  // Feedback loop count (would require flow analysis; placeholder)
  const feedbackLoopCount = results.length > 0 ? 2 : 0;

  // Surprise index (proxy: how often the lower-scored player wins)
  const surpriseIndex = comebackPotential * 0.5;

  // Composite fitness
  const weights = {
    completionRate: 0.15,
    averageDuration: 0.10,
    decisionCount: 0.10,
    deadlockRate: 0.15,
    winRateVariance: 0.10,
    firstMoverAdvantage: 0.05,
    strategyDominance: 0.10,
    comebackPotential: 0.05,
    stateSpaceEntropy: 0.05,
    actionDiversity: 0.05,
    feedbackLoopCount: 0.05,
    surpriseIndex: 0.05,
  };

  const fitness =
    weights.completionRate * completionRate +
    weights.averageDuration * normalize(averageDuration, 50, 500) +
    weights.decisionCount * normalize(decisionCount, 10, 100) +
    weights.deadlockRate * (1 - deadlockRate) +
    weights.winRateVariance * (1 - Math.min(winRateVariance * 10, 1)) +
    weights.firstMoverAdvantage * (1 - firstMoverAdvantage) +
    weights.strategyDominance * (strategyDominance ? 0 : 1) +
    weights.comebackPotential * normalize(comebackPotential, 0.1, 0.4) +
    weights.stateSpaceEntropy * normalize(stateSpaceEntropy, 0, 3) +
    weights.actionDiversity * actionDiversity +
    weights.feedbackLoopCount * normalize(feedbackLoopCount, 2, 10) +
    weights.surpriseIndex * surpriseIndex;

  return {
    completionRate,
    averageDuration,
    decisionCount,
    deadlockRate,
    winRateVariance,
    firstMoverAdvantage,
    strategyDominance,
    comebackPotential,
    stateSpaceEntropy,
    actionDiversity,
    feedbackLoopCount,
    surpriseIndex,
    fitness,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function emptyMetrics(): SimulationMetrics {
  return {
    completionRate: 0,
    averageDuration: 0,
    decisionCount: 0,
    deadlockRate: 1,
    winRateVariance: 0,
    firstMoverAdvantage: 0,
    strategyDominance: false,
    comebackPotential: 0,
    stateSpaceEntropy: 0,
    actionDiversity: 0,
    feedbackLoopCount: 0,
    surpriseIndex: 0,
    fitness: 0,
  };
}

function variance(values: number[]): number {
  if (values.length === 0) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  return values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / values.length;
}

function entropy(values: number[]): number {
  if (values.length === 0) return 0;

  const counts: Record<number, number> = {};
  for (const v of values) {
    counts[v] = (counts[v] ?? 0) + 1;
  }

  const total = values.length;
  let h = 0;
  for (const count of Object.values(counts)) {
    const p = count / total;
    if (p > 0) {
      h -= p * Math.log2(p);
    }
  }

  return h;
}

function normalize(value: number, min: number, max: number): number {
  if (max === min) return 1;
  const clamped = Math.max(min, Math.min(max, value));
  return (clamped - min) / (max - min);
}

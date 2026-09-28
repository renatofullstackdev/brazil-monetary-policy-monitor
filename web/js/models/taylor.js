export const CANONICAL_INFLATION_COEFFICIENT = 0.5;
export const CANONICAL_OUTPUT_GAP_COEFFICIENT = 0.5;

function finite(name, value) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new TypeError(`${name} deve ser um número finito.`);
  return number;
}

function nonNegative(name, value) {
  const number = finite(name, value);
  if (number < 0) throw new RangeError(`${name} não pode ser negativo.`);
  return number;
}

export function taylorRule({
  inflation,
  inflationTarget,
  neutralRealRate,
  outputGap,
  inflationCoefficient = CANONICAL_INFLATION_COEFFICIENT,
  outputGapCoefficient = CANONICAL_OUTPUT_GAP_COEFFICIENT,
}) {
  const priceChange = finite("Inflação", inflation);
  const target = finite("Meta de inflação", inflationTarget);
  const neutral = finite("Taxa real neutra", neutralRealRate);
  const gap = finite("Hiato do produto", outputGap);
  const alpha = nonNegative("Coeficiente da inflação", inflationCoefficient);
  const beta = nonNegative("Coeficiente do hiato", outputGapCoefficient);
  const inflationGapResponse = alpha * (priceChange - target);
  const outputGapResponse = beta * gap;
  const nominalRate = neutral + priceChange + inflationGapResponse + outputGapResponse;
  return {
    nominalRate,
    inflationCoefficient: alpha,
    outputGapCoefficient: beta,
    decomposition: {
      neutralRealRate: neutral,
      inflation: priceChange,
      inflationGapResponse,
      outputGapResponse,
    },
  };
}

export function prospectiveTaylor({
  expectedInflation,
  inflationTarget,
  neutralRealRate,
  outputGap,
  inflationCoefficient = CANONICAL_INFLATION_COEFFICIENT,
  outputGapCoefficient = CANONICAL_OUTPUT_GAP_COEFFICIENT,
}) {
  return taylorRule({
    inflation: expectedInflation,
    inflationTarget,
    neutralRealRate,
    outputGap,
    inflationCoefficient,
    outputGapCoefficient,
  });
}

export function inertialTaylor({ previousPolicyRate, taylorRate, smoothing }) {
  const previous = finite("Taxa de política de referência", previousPolicyRate);
  const target = finite("Taylor subjacente", taylorRate);
  const rho = finite("Coeficiente de inércia", smoothing);
  if (rho < 0 || rho > 1) throw new RangeError("Coeficiente de inércia deve ficar entre 0 e 1.");
  return {
    nominalRate: rho * previous + (1 - rho) * target,
    previousPolicyComponent: rho * previous,
    taylorComponent: (1 - rho) * target,
    smoothing: rho,
    underlyingTaylorRate: target,
  };
}

export const CANONICAL_INFLATION_COEFFICIENT = 0.5;
export const CANONICAL_OUTPUT_GAP_COEFFICIENT = 0.5;

function finite(name, value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new TypeError(`${name} deve ser um número finito.`);
  }
  return number;
}

export function prospectiveTaylor({
  expectedInflation,
  inflationTarget,
  neutralRealRate,
  outputGap,
}) {
  const inflation = finite("Inflação esperada", expectedInflation);
  const target = finite("Meta de inflação", inflationTarget);
  const neutral = finite("Taxa real neutra", neutralRealRate);
  const gap = finite("Hiato do produto", outputGap);

  const inflationGapResponse = CANONICAL_INFLATION_COEFFICIENT * (inflation - target);
  const outputGapResponse = CANONICAL_OUTPUT_GAP_COEFFICIENT * gap;
  const nominalRate = neutral + inflation + inflationGapResponse + outputGapResponse;

  return {
    nominalRate,
    decomposition: {
      neutralRealRate: neutral,
      inflation,
      inflationGapResponse,
      outputGapResponse,
    },
  };
}

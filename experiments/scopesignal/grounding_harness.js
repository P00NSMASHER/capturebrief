/* ScopeSignal validation harness.
 *
 * Independently implements the narrow deterministic grounding rule we are
 * validating from cneuralnetwork/ScopeSignal at pinned revision
 * d470659a009e9944fd6c4a7969a903dfc28c443e (MIT).
 *
 * This is validation-only: it does not analyze contracts or send messages.
 */

function normalizeText(value) {
  return value.replace(/\s+/g, " ").trim().toLowerCase();
}

function enforceGrounding(finding, contractText) {
  const verifiedEvidence = finding.contractEvidence.filter((evidence) =>
    normalizeText(contractText).includes(normalizeText(evidence.quote)),
  );

  if (finding.status === "out_of_scope" && verifiedEvidence.length === 0) {
    return {
      ...finding,
      status: "review",
      confidence: Math.min(finding.confidence, 0.55),
      contractEvidence: [],
    };
  }
  return { ...finding, contractEvidence: verifiedEvidence };
}

const cases = [
  {
    name: "clear extra page remains grounded",
    contract:
      "Scope includes one landing page. Additional pages require written change authorization.",
    finding: {
      status: "out_of_scope",
      confidence: 0.92,
      contractEvidence: [
        { quote: "Additional pages require written change authorization." },
      ],
    },
    expect: "out_of_scope",
  },
  {
    name: "included first revision stays in scope",
    contract: "The fee includes two revision rounds.",
    finding: {
      status: "in_scope",
      confidence: 0.9,
      contractEvidence: [{ quote: "includes two revision rounds" }],
    },
    expect: "in_scope",
  },
  {
    name: "ambiguous rush request remains review",
    contract: "The fee includes reasonable revisions.",
    finding: { status: "review", confidence: 0.6, contractEvidence: [] },
    expect: "review",
  },
  {
    name: "fabricated clause is rejected",
    contract: "Scope includes one landing page.",
    finding: {
      status: "out_of_scope",
      confidence: 0.99,
      contractEvidence: [{ quote: "Weekend work requires a 50% rush fee." }],
    },
    expect: "review",
    maxConfidence: 0.55,
    expectEvidenceCount: 0,
  },
];

let failures = 0;
for (const testCase of cases) {
  const result = enforceGrounding(testCase.finding, testCase.contract);
  const ok =
    result.status === testCase.expect &&
    (testCase.maxConfidence === undefined ||
      result.confidence <= testCase.maxConfidence) &&
    (testCase.expectEvidenceCount === undefined ||
      result.contractEvidence.length === testCase.expectEvidenceCount);

  console.log(
    `${ok ? "PASS" : "FAIL"} ${testCase.name} -> status=${result.status} confidence=${result.confidence} evidence=${result.contractEvidence.length}`,
  );
  if (!ok) failures += 1;
}

if (failures) process.exit(1);

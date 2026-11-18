import { formatProbability, probabilityTone } from "./format";

describe("formatProbability", () => {
  it("renders one decimal percent", () => {
    expect(formatProbability(0.8345)).toBe("83.5%");
  });
});

describe("probabilityTone", () => {
  it("bands probabilities", () => {
    expect(probabilityTone(0.8)).toBe("high");
    expect(probabilityTone(0.5)).toBe("medium");
    expect(probabilityTone(0.1)).toBe("low");
  });
});

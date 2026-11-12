import { buildAlertQuery } from "../api";
import { formatMoney, formatScore, scoreTone } from "../format";

describe("formatScore", () => {
  it("renders one decimal percent", () => {
    expect(formatScore(0.8345)).toBe("83.5%");
  });

  it("handles zero", () => {
    expect(formatScore(0)).toBe("0.0%");
  });
});

describe("formatMoney", () => {
  it("renders currency", () => {
    expect(formatMoney(1234.5)).toBe("$1,234.50");
  });
});

describe("scoreTone", () => {
  it("bands scores", () => {
    expect(scoreTone(0.9)).toBe("high");
    expect(scoreTone(0.6)).toBe("medium");
    expect(scoreTone(0.1)).toBe("low");
  });
});

describe("buildAlertQuery", () => {
  it("serializes filters", () => {
    expect(buildAlertQuery({ status: "open", minScore: 0.5, limit: 25 })).toBe(
      "?status=open&min_score=0.5&limit=25",
    );
  });

  it("returns empty string with no filters", () => {
    expect(buildAlertQuery({})).toBe("");
  });
});

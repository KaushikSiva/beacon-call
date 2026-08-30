import { describe, expect, it } from "vitest";
import { confidenceLabel, statusLabel } from "./format";

describe("display formatting", () => {
  it("formats confidence as a whole percent", () => {
    expect(confidenceLabel(0.876)).toBe("88%");
  });

  it("formats machine statuses for the operator", () => {
    expect(statusLabel("awaiting_inbound_call")).toBe("AWAITING INBOUND CALL");
  });
});

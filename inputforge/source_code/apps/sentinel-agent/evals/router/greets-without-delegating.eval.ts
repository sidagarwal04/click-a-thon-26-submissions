import { defineEval } from "eve/evals";

export default defineEval({
  description:
    "A plain greeting should get a direct reply, not a delegation to the " +
    "investigator subagent.",
  async test(t) {
    await t.send("hey, are you there?");
    t.succeeded();
    t.calledSubagent("investigator", { count: 0 });
  },
});

import { defineEval } from "eve/evals";

export default defineEval({
  description:
    "A question that requires looking at observability data should be " +
    "delegated to the investigator subagent, and the router should relay " +
    "its findings rather than answering from its own guess.",
  async test(t) {
    await t.send(
      "The error rate on checkout-service spiked to 40% around 14:32 UTC " +
        "today. Can you find out what happened?",
    );
    t.succeeded();
    t.calledSubagent("investigator", { status: "completed" });
    t.judge.autoevals
      .closedQA("States a likely cause or explicitly says the cause is unclear, and gives a severity.")
      .atLeast(0.7);
  },
});

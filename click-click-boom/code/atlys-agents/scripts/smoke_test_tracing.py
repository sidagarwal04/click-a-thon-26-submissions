"""Run once Langfuse Cloud keys are in .env — proves traced_run actually reaches
Langfuse and prints a real trace URL to click and eyeball."""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from tracing import traced_run


def main():
    with traced_run(agent="pipeline", spec="smoke_test") as run:
        run.log(step="ping", input={"hello": "world"}, output={"ok": True}, reasoning="smoke test")
        with run.span("nested_example", revision=1):
            run.log(step="nested_ping", input="a", output="b")
        print("trace url:", run.url)
    time.sleep(1)  # give the flush a beat before the process exits
    print("done — open the URL above and confirm you see: pipeline:smoke_test, "
          "with a 'ping' span and a nested 'nested_example' > 'nested_ping' span.")


if __name__ == "__main__":
    main()

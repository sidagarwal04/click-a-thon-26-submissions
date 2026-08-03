import { timingSafeEqual } from "node:crypto";
import { defineChannel, POST } from "eve/channels";
import { z } from "zod";
import slack from "./slack";

const AnomalyPayload = z.object({
  title: z.string(),
  severity: z.enum(["low", "medium", "high", "critical"]),
  source: z.string(),
  detectedAt: z.string(),
  details: z.record(z.string(), z.unknown()).default({}),
});

function isAuthorized(req: Request): boolean {
  const expected = process.env.ANOMALY_WEBHOOK_SECRET;
  if (!expected) return false;

  const provided = req.headers.get("authorization")?.replace(/^Bearer\s+/i, "");
  if (!provided) return false;

  const a = Buffer.from(provided);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

export default defineChannel({
  routes: [
    POST("/webhook", async (req, args) => {
      if (!isAuthorized(req)) {
        return new Response("Unauthorized", { status: 401 });
      }

      const parsed = AnomalyPayload.safeParse(await req.json());
      if (!parsed.success) {
        return Response.json({ error: parsed.error.flatten() }, { status: 400 });
      }
      const alert = parsed.data;

      const channelId = process.env.SLACK_ALERTS_CHANNEL_ID;
      if (!channelId) {
        return Response.json(
          { error: "SLACK_ALERTS_CHANNEL_ID is not configured" },
          { status: 500 },
        );
      }

      args.waitUntil(
        args.receive(slack, {
          message:
            `Anomaly detected (${alert.severity}) from ${alert.source} ` +
            `at ${alert.detectedAt}: ${alert.title}\n\n` +
            "Details:\n```" +
            JSON.stringify(alert.details, null, 2) +
            "```",
          target: { channelId },
          auth: {
            authenticator: "anomaly-detector",
            principalType: "service",
            principalId: alert.source,
            attributes: { severity: alert.severity },
          },
        }),
      );

      return new Response("ok", { status: 202 });
    }),
  ],
});

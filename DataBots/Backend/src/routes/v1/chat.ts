import { FastifyInstance } from "fastify";
import { createRcaLlamaIndexAgent } from "../../services/agentService.js";

export default async function chatRoutes(fastify: FastifyInstance) {
  // Chat completions endpoint powered by LlamaIndex OpenAIAgent & ClickHouse tools
  fastify.post("/v1/chat/completions", async (request, reply) => {
    const { messages, stream, model } = (request.body as any) || {};

    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      reply.status(400);
      return { error: "Invalid request body: 'messages' array is required." };
    }

    // Extract the latest user message
    const userMessages = messages.filter((m: any) => m.role === "user");
    let queryText = "";
    const lastUserContent = userMessages[userMessages.length - 1]?.content;

    if (typeof lastUserContent === "string") {
      queryText = lastUserContent;
    } else if (Array.isArray(lastUserContent)) {
      const textPart = lastUserContent.find((p: any) => p.type === "text" || p.text);
      queryText = textPart?.text || "";
    }

    if (!queryText) {
      reply.status(400);
      return { error: "No user query found in messages history." };
    }

    try {
      console.log(`[LlamaIndex Agent Turn] Query: "${queryText}"`);
      const agent = createRcaLlamaIndexAgent();

      const result = await agent.chat({
        message: queryText,
      });

      const responseText = result.response;

      if (stream) {
        reply.raw.writeHead(200, {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
          "Access-Control-Allow-Origin": "*",
        });

        const chunkId = `chatcmpl-${Date.now()}`;
        reply.raw.write(
          `data: ${JSON.stringify({
            id: chunkId,
            object: "chat.completion.chunk",
            created: Math.floor(Date.now() / 1000),
            model: model || "deepseek-chat",
            choices: [{ index: 0, delta: { content: responseText }, finish_reason: null }],
          })}\n\n`
        );
        reply.raw.write(
          `data: ${JSON.stringify({
            id: chunkId,
            object: "chat.completion.chunk",
            created: Math.floor(Date.now() / 1000),
            model: model || "deepseek-chat",
            choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
          })}\n\n`
        );
        reply.raw.write("data: [DONE]\n\n");
        reply.raw.end();
        return;
      } else {
        return reply.send({
          id: `chatcmpl-${Date.now()}`,
          object: "chat.completion",
          created: Math.floor(Date.now() / 1000),
          model: model || "deepseek-chat",
          choices: [
            { index: 0, message: { role: "assistant", content: responseText }, finish_reason: "stop" },
          ],
        });
      }
    } catch (err: any) {
      console.error("LlamaIndex Agent execution failed:", err);
      reply.status(500);
      return { error: `Error executing LlamaIndex Agent: ${err?.message || err}` };
    }
  });
}

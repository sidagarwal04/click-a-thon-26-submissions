const express = require('express');
const { createAnalyticsHandlers } = require('@librechat/api');
const { logger } = require('@librechat/data-schemas');
const { analyticsPersistRequestSchema } = require('librechat-data-provider');
const { requireJwtAuth, configMiddleware } = require('~/server/middleware');
const db = require('~/models');

const router = express.Router();
const handlers = createAnalyticsHandlers();

router.post('/query', requireJwtAuth, handlers.query);
router.post('/data', requireJwtAuth, handlers.data);
router.post('/dimensions', requireJwtAuth, handlers.dimensions);

/**
 * Persist analytics chat turns.
 * Native POST /api/messages/:conversationId returns 404 until the conversation
 * already exists (validateMessageReq). Agent chat creates convos via saveConvo
 * in the controller; analytics uses this route for the same upsert path.
 */
router.post('/persist', requireJwtAuth, configMiddleware, async (req, res) => {
  try {
    const parsed = analyticsPersistRequestSchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({
        error: 'Invalid analytics persist payload',
        details: parsed.error.flatten(),
      });
    }

    const { conversationId, title, endpoint, model, messages } = parsed.data;
    const userId = req.user.id;
    const reqCtx = {
      userId,
      isTemporary: req?.body?.isTemporary,
      interfaceConfig: req?.config?.interfaceConfig,
    };

    for (const message of messages) {
      const saved = await db.saveMessage(
        reqCtx,
        {
          ...message,
          conversationId,
          user: userId,
          unfinished: false,
        },
        { context: 'POST /api/analytics/persist' },
      );
      if (!saved) {
        return res.status(400).json({ error: 'Message not saved', messageId: message.messageId });
      }
    }

    await db.saveConvo(
      reqCtx,
      {
        conversationId,
        title,
        endpoint: endpoint ?? null,
        model: model ?? null,
      },
      { context: 'POST /api/analytics/persist' },
    );

    return res.status(201).json({ conversationId, title });
  } catch (error) {
    logger.error('[analytics] Persist failed', error);
    return res.status(500).json({ error: 'Failed to persist analytics conversation' });
  }
});

module.exports = router;

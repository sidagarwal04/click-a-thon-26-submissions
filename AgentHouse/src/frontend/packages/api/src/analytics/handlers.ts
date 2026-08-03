import { logger } from '@librechat/data-schemas';
import type { Request, Response } from 'express';
import { ZodError } from 'zod';
import {
  parseAnalyticsDataBody,
  parseAnalyticsDimensionsBody,
  parseAnalyticsQueryBody,
  resolveAnalyticsData,
  resolveAnalyticsDimensions,
  resolveAnalyticsQuery,
} from './service';

interface AuthenticatedRequest extends Request {
  user?: {
    id?: string;
  };
}

export function createAnalyticsHandlers(): {
  query: (req: AuthenticatedRequest, res: Response) => Promise<Response | undefined>;
  data: (req: AuthenticatedRequest, res: Response) => Promise<Response | undefined>;
  dimensions: (req: AuthenticatedRequest, res: Response) => Promise<Response | undefined>;
} {
  async function query(
    req: AuthenticatedRequest,
    res: Response,
  ): Promise<Response | undefined> {
    try {
      const request = parseAnalyticsQueryBody(req.body);
      const result = await resolveAnalyticsQuery(request);
      return res.status(200).json(result);
    } catch (error) {
      if (error instanceof ZodError) {
        return res.status(400).json({
          error: 'Invalid analytics query',
          details: error.flatten(),
        });
      }

      logger.error('[analytics] Query failed', error);
      const message = error instanceof Error ? error.message : 'Analytics query failed';
      return res.status(502).json({ error: message });
    }
  }

  async function data(
    req: AuthenticatedRequest,
    res: Response,
  ): Promise<Response | undefined> {
    try {
      const request = parseAnalyticsDataBody(req.body);
      const result = await resolveAnalyticsData(request);
      return res.status(200).json(result);
    } catch (error) {
      if (error instanceof ZodError) {
        return res.status(400).json({
          error: 'Invalid analytics data request',
          details: error.flatten(),
        });
      }

      logger.error('[analytics] Data failed', error);
      const message = error instanceof Error ? error.message : 'Analytics data failed';
      return res.status(502).json({ error: message });
    }
  }

  async function dimensions(
    req: AuthenticatedRequest,
    res: Response,
  ): Promise<Response | undefined> {
    try {
      const request = parseAnalyticsDimensionsBody(req.body);
      const result = await resolveAnalyticsDimensions(request);
      return res.status(200).json(result);
    } catch (error) {
      if (error instanceof ZodError) {
        return res.status(400).json({
          error: 'Invalid analytics dimensions request',
          details: error.flatten(),
        });
      }

      logger.error('[analytics] Dimensions failed', error);
      const message = error instanceof Error ? error.message : 'Analytics dimensions failed';
      return res.status(502).json({ error: message });
    }
  }

  return { query, data, dimensions };
}

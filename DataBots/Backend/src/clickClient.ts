import fp from 'fastify-plugin'
import type { FastifyPluginAsync } from 'fastify'
import { getClickHouseService, ClickHouseService } from './services/clickhouse.js'

// Extend Fastify's types so TypeScript knows about 'ch' and 'clickhouseService'
declare module 'fastify' {
  interface FastifyInstance {
    ch: ReturnType<ClickHouseService['getRawClient']>
    clickhouseService: ClickHouseService
  }
}

const clickhousePlugin: FastifyPluginAsync = async (fastify) => {
  const service = getClickHouseService()
  const ch = service.getRawClient()

  // Expose client globally via fastify.ch and fastify.clickhouseService
  fastify.decorate('ch', ch)
  fastify.decorate('clickhouseService', service)

  // Gracefully sever connections on server teardown
  fastify.addHook('onClose', async () => {
    await service.close()
  })
}

export default fp(clickhousePlugin)

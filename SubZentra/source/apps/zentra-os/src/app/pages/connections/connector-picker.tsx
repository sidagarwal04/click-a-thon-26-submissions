import { Badge, Button } from '@open-zentra/foundation-design-system';
import { Icon } from '@open-zentra/foundation-icons';
import { Link, useNavigate } from 'react-router-dom';

import { CONNECTOR_CATEGORIES, CONNECTORS } from './constants';
import { ConnectorLogo } from './connector-logos';
import type { Connector } from './types';

interface ConnectorTileProps {
  readonly connector: Connector;
  readonly onSelect: (connector: Connector) => void;
}

const ConnectorTile = ({ connector, onSelect }: ConnectorTileProps) => (
  <button
    type="button"
    onClick={() => onSelect(connector)}
    className="group flex w-full items-center gap-3 rounded-lg border border-border bg-card px-4 py-4 text-left transition-colors hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
  >
    <ConnectorLogo name={connector.logo} className="h-7 w-7 shrink-0" />
    <span className="min-w-0 flex-1">
      <span className="block truncate text-sm font-medium">{connector.name}</span>
      {connector.available ? (
        <span className="mt-0.5 block font-mono text-[10px] uppercase tracking-[0.14em] text-primary">
          Connects
        </span>
      ) : (
        <span className="mt-0.5 block font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
          Not built
        </span>
      )}
    </span>
  </button>
);

/**
 * Choosing what to connect to.
 *
 * The unbuilt connectors are shown rather than hidden, and say so on their own
 * tile. A picker that lists one option tells an operator nothing about where
 * the product is going; a picker that lists twelve and silently breaks eleven
 * is worse. Both are avoided by labelling.
 */
export const ConnectorPicker = () => {
  const navigate = useNavigate();

  return (
    <section className="px-8 py-10">
      <Button component={Link} to="/connections" intent="ghost" size="sm" className="-ml-2">
        <Icon name="arrow_left" size="sm" /> Connections
      </Button>

      <h1 className="mt-4 font-serif text-[clamp(1.75rem,3.2vw,2.5rem)] font-normal tracking-[-0.035em]">
        Select a source connector
      </h1>
      <p className="mt-3 max-w-2xl text-sm text-foreground-muted">
        ZentraOS reads from the source in place. Nothing is copied out of it until a harvest
        is started, and credentials are sealed the moment they are accepted.
      </p>

      {CONNECTOR_CATEGORIES.map((category) => {
        const connectors = CONNECTORS.filter((entry) => entry.category === category);
        if (connectors.length === 0) return null;

        return (
          <div className="mt-10" key={category}>
            <div className="flex items-center gap-3">
              <h2 className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-foreground-muted">
                {category}
              </h2>
              <span className="h-px flex-1 bg-border" aria-hidden="true" />
            </div>
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {connectors.map((connector) => (
                <ConnectorTile
                  key={connector.id}
                  connector={connector}
                  onSelect={(selected) => navigate(`/connections/new/${selected.id}`)}
                />
              ))}
            </div>
          </div>
        );
      })}

      <p className="mt-12 flex items-center gap-3 border-t border-border pt-5 text-sm text-foreground-muted">
        <Badge intent="primary" size="sm">
          ClickHouse
        </Badge>
        is the only connector wired to the Connector API. The rest open a configuration page
        that describes what they will need and saves nothing.
      </p>
    </section>
  );
};

import { Alert, Button, Card, EmptyState } from '@open-zentra/foundation-design-system';
import { Icon } from '@open-zentra/foundation-icons';
import { Link } from 'react-router-dom';

import { ConnectorLogo } from './connector-logos';
import type { Connector } from './types';

interface PlaceholderConfigProps {
  readonly connector: Connector;
}

/**
 * The configuration page for a connector that does not exist yet.
 *
 * Deliberately fieldless. A disabled form would still be a form: it would
 * suggest the shape of the credentials is settled and the only thing missing
 * is a click, when in fact the Connector API has one credential model and no
 * notion of a connector kind. Saying that is more use than a mock.
 */
export const PlaceholderConfig = ({ connector }: PlaceholderConfigProps) => (
  <section className="px-8 py-10">
    <Button component={Link} to="/connections/new" intent="ghost" size="sm" className="-ml-2">
      <Icon name="arrow_left" size="sm" /> Connectors
    </Button>

    <div className="mt-4 flex items-center gap-3">
      <ConnectorLogo name={connector.logo} className="h-8 w-8" />
      <h1 className="font-serif text-[clamp(1.75rem,3.2vw,2.5rem)] font-normal tracking-[-0.035em]">
        Connect {connector.name}
      </h1>
    </div>
    <p className="mt-3 max-w-2xl text-sm text-foreground-muted">{connector.blurb}</p>

    <Card padding="lg" className="mt-8 max-w-2xl">
      <EmptyState size="lg" icon={<Icon name={connector.icon} size="xl" />}>
        <EmptyState.Title>The {connector.name} connector is not built</EmptyState.Title>
        <EmptyState.Description>
          The Connector API accepts one credential shape — host, port, database, username and
          password — and holds no notion of which kind of source it is talking to. Supporting
          {' '}
          {connector.name} means a credential model of its own and a driver behind it, not a
          form on this page.
        </EmptyState.Description>
        <EmptyState.Actions>
          <Button component={Link} to="/connections/new/clickhouse">
            Connect ClickHouse instead
          </Button>
          <Button component={Link} to="/connections" intent="secondary">
            Back to connections
          </Button>
        </EmptyState.Actions>
      </EmptyState>
    </Card>

    <Alert intent="info" className="mt-5 max-w-2xl" title="Nothing here is saved">
      This page has no fields on purpose. Credentials typed into a form that posts nowhere are
      still credentials that were typed.
    </Alert>
  </section>
);

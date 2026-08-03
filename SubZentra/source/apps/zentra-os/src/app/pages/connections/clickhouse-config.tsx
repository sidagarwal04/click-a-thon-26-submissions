import { useState, type FormEvent } from 'react';

import {
  Alert,
  Button,
  Card,
  Input,
  Label,
  Switch,
} from '@open-zentra/foundation-design-system';
import { Icon } from '@open-zentra/foundation-icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';

import { ApiError, type TokenSource } from '../../api';

import { registerSource } from './api';
import {
  CLICKHOUSE_PLAIN_PORT,
  CLICKHOUSE_SECURE_PORT,
  CONNECTION_FAILURE_HELP,
} from './constants';
import { ConnectorLogo } from './connector-logos';
import type { SourceResponse } from './types';

interface ClickHouseConfigProps {
  readonly getToken: TokenSource;
  readonly canWrite: boolean;
}

interface FormState {
  readonly name: string;
  readonly host: string;
  readonly port: string;
  readonly database: string;
  readonly username: string;
  readonly password: string;
  readonly secure: boolean;
  readonly storeSampleValues: boolean;
}

const INITIAL_FORM: FormState = {
  name: '',
  host: '',
  port: String(CLICKHOUSE_SECURE_PORT),
  database: 'default',
  username: 'default',
  password: '',
  secure: true,
  storeSampleValues: false,
};

interface FieldProps {
  readonly id: string;
  readonly label: string;
  readonly hint?: string;
  readonly children: React.ReactNode;
}

const Field = ({ id, label, hint, children }: FieldProps) => (
  <div className="flex flex-col gap-1.5">
    <Label htmlFor={id}>{label}</Label>
    {children}
    {hint ? (
      <p className="text-xs text-foreground-muted" id={`${id}-hint`}>
        {hint}
      </p>
    ) : null}
  </div>
);

/**
 * Registering a ClickHouse service.
 *
 * There is no separate "Test connection" button because there is no separate
 * test: `POST /v1/connector/sources` opens the connection before it persists
 * anything and refuses to store a source it could not reach. One button that
 * both proves and saves is honest about that; two would imply a source can
 * exist unverified, which through this path it cannot.
 */
export const ClickHouseConfig = ({ getToken, canWrite }: ClickHouseConfigProps) => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [revealPassword, setRevealPassword] = useState(false);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  const mutation = useMutation({
    mutationFn: (state: FormState) =>
      registerSource(getToken, {
        name: state.name.trim(),
        credentials: {
          host: state.host.trim(),
          port: Number(state.port),
          database: state.database.trim(),
          username: state.username.trim(),
          password: state.password,
          secure: state.secure,
        },
        store_sample_values: state.storeSampleValues,
      }),
    onSuccess: async (source: SourceResponse) => {
      await queryClient.invalidateQueries({ queryKey: ['connector-sources'] });
      navigate('/connections', { state: { registered: source.data_source_id } });
    },
  });

  const portNumber = Number(form.port);
  const portIsValid =
    form.port.trim() !== '' &&
    Number.isInteger(portNumber) &&
    portNumber >= 1 &&
    portNumber <= 65535;
  const isComplete =
    form.name.trim() !== '' &&
    form.host.trim() !== '' &&
    form.database.trim() !== '' &&
    form.username.trim() !== '' &&
    form.password !== '' &&
    portIsValid;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!isComplete || !canWrite) return;
    mutation.mutate(form);
  };

  // A 502 carries the coarse failure code the domain allows out; anything else
  // is a transport or authorisation problem and reads better as its own message.
  const failureCode =
    mutation.error instanceof ApiError && mutation.error.status === 502
      ? mutation.error.message
      : undefined;
  const failureHelp = failureCode ? CONNECTION_FAILURE_HELP[failureCode] : undefined;

  return (
    <section className="px-8 py-10">
      <Button component={Link} to="/connections/new" intent="ghost" size="sm" className="-ml-2">
        <Icon name="arrow_left" size="sm" /> Connectors
      </Button>

      <div className="mt-4 flex items-center gap-3">
        <ConnectorLogo name="clickhouse" className="h-8 w-8" />
        <h1 className="font-serif text-[clamp(1.75rem,3.2vw,2.5rem)] font-normal tracking-[-0.035em]">
          Connect ClickHouse
        </h1>
      </div>
      <p className="mt-3 max-w-2xl text-sm text-foreground-muted">
        ZentraOS opens the connection before it stores anything. If these credentials do not
        reach the service, nothing is saved and the reason is shown below.
      </p>

      <form className="mt-8 max-w-2xl" onSubmit={submit}>
        <Card padding="lg">
          <Card.Header icon={<Icon name="tag" size="sm" />}>
            <Card.Title>Source</Card.Title>
          </Card.Header>
          <div className="mt-5 flex flex-col gap-5">
            <Field
              id="ch-name"
              label="Connection name"
              hint="How this source is named everywhere else in ZentraOS."
            >
              <Input
                id="ch-name"
                value={form.name}
                onChange={(event) => set('name', event.target.value)}
                placeholder="Atlys production events"
                autoComplete="off"
                required
              />
            </Field>
          </div>
        </Card>

        <Card padding="lg" className="mt-5">
          <Card.Header icon={<Icon name="database" size="sm" />}>
            <Card.Title>Service</Card.Title>
          </Card.Header>
          <div className="mt-5 flex flex-col gap-5">
            <Field
              id="ch-host"
              label="Host"
              hint="The hostname alone — no scheme and no port. For ClickHouse Cloud this ends in clickhouse.cloud."
            >
              <Input
                id="ch-host"
                value={form.host}
                onChange={(event) => set('host', event.target.value)}
                placeholder="abc123xyz.ap-south-1.aws.clickhouse.cloud"
                autoComplete="off"
                required
              />
            </Field>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <Field id="ch-port" label="Port">
                <Input
                  id="ch-port"
                  type="number"
                  min={1}
                  max={65535}
                  value={form.port}
                  invalid={form.port.trim() !== '' && !portIsValid}
                  onChange={(event) => set('port', event.target.value)}
                  required
                />
              </Field>

              <Field id="ch-database" label="Database">
                <Input
                  id="ch-database"
                  value={form.database}
                  onChange={(event) => set('database', event.target.value)}
                  placeholder="default"
                  autoComplete="off"
                  required
                />
              </Field>
            </div>

            <div className="flex items-start gap-3 rounded-md border border-border p-4">
              <Switch
                id="ch-secure"
                checked={form.secure}
                onCheckedChange={(checked) => {
                  set('secure', checked);
                  // The port almost always moves with the protocol, and an
                  // operator who toggles TLS and leaves 8443 behind gets
                  // "unreachable" with no hint that the port is the reason.
                  // Only rewritten when it still holds the other default.
                  setForm((current) =>
                    current.port === String(checked ? CLICKHOUSE_PLAIN_PORT : CLICKHOUSE_SECURE_PORT)
                      ? {
                          ...current,
                          secure: checked,
                          port: String(checked ? CLICKHOUSE_SECURE_PORT : CLICKHOUSE_PLAIN_PORT),
                        }
                      : { ...current, secure: checked },
                  );
                }}
              />
              <div>
                <Label htmlFor="ch-secure">Connect over TLS</Label>
                <p className="mt-1 text-xs text-foreground-muted">
                  Required by ClickHouse Cloud, which listens on {CLICKHOUSE_SECURE_PORT}. A
                  self-managed cluster without TLS is usually on {CLICKHOUSE_PLAIN_PORT}.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card padding="lg" className="mt-5">
          <Card.Header icon={<Icon name="key" size="sm" />}>
            <Card.Title>Credentials</Card.Title>
          </Card.Header>
          <div className="mt-5 flex flex-col gap-5">
            <Field
              id="ch-username"
              label="Username"
              hint="A read-only user is enough. ZentraOS never writes to a connected source."
            >
              <Input
                id="ch-username"
                value={form.username}
                onChange={(event) => set('username', event.target.value)}
                placeholder="default"
                autoComplete="off"
                required
              />
            </Field>

            <Field id="ch-password" label="Password">
              <Input
                id="ch-password"
                type={revealPassword ? 'text' : 'password'}
                value={form.password}
                onChange={(event) => set('password', event.target.value)}
                autoComplete="new-password"
                required
                end={
                  <button
                    type="button"
                    onClick={() => setRevealPassword((shown) => !shown)}
                    aria-label={revealPassword ? 'Hide password' : 'Show password'}
                    className="text-foreground-muted transition-colors hover:text-foreground"
                  >
                    <Icon name={revealPassword ? 'eye_off' : 'eye'} size="sm" />
                  </button>
                }
              />
            </Field>

            <div className="flex items-start gap-3 rounded-md border border-border p-4">
              <Switch
                id="ch-samples"
                checked={form.storeSampleValues}
                onCheckedChange={(checked) => set('storeSampleValues', checked)}
              />
              <div>
                <Label htmlFor="ch-samples">Store sample values</Label>
                <p className="mt-1 text-xs text-foreground-muted">
                  Off by default. Enabling it copies raw column values into ZentraOS during a
                  harvest, which is a materially different data posture to statistics alone.
                </p>
              </div>
            </div>
          </div>
        </Card>

        {mutation.error ? (
          <Alert
            intent="error"
            className="mt-5"
            role="alert"
            title={
              failureCode ? 'That service could not be reached' : 'The source was not registered'
            }
          >
            {failureHelp ?? mutation.error.message} Nothing was saved.
          </Alert>
        ) : null}

        {!canWrite ? (
          <Alert intent="info" className="mt-5">
            Viewer access is read only. Registering a source needs an analyst or admin role.
          </Alert>
        ) : null}

        <div className="mt-6 flex items-center gap-3">
          <Button type="submit" size="lg" loading={mutation.isPending} disabled={!isComplete || !canWrite}>
            Test and save connection
          </Button>
          <Button component={Link} to="/connections" intent="secondary" size="lg">
            Cancel
          </Button>
        </div>
      </form>
    </section>
  );
};

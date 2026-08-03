/**
 * Vendor marks for the connector picker.
 *
 * Inline rather than imported: `foundation-icons` wraps lucide, which carries
 * no vendor logos, and a picker where every source shows the same database
 * glyph is a picker you have to read rather than recognise. These are drawn
 * simply and at one size — enough to tell apart, not passed off as the
 * vendors' own artwork.
 *
 * ClickHouse draws its bars in `currentColor` so the one connector that
 * actually connects stays legible in both themes; the rest carry brand colour.
 */

export type ConnectorLogoName =
  | 'clickhouse'
  | 'snowflake'
  | 'bigquery'
  | 'databricks'
  | 'postgresql'
  | 'mysql'
  | 'mssql'
  | 'oracle'
  | 's3'
  | 'azure-blob'
  | 'gcs'
  | 'sftp';

interface LogoProps {
  readonly className?: string;
}

const svgProps = {
  viewBox: '0 0 24 24',
  xmlns: 'http://www.w3.org/2000/svg',
  'aria-hidden': true as const,
};

const ClickHouseLogo = ({ className }: LogoProps) => (
  <svg {...svgProps} className={className} fill="none">
    {[2, 6.5, 11, 15.5].map((x) => (
      <rect key={x} x={x} y={2} width={3} height={20} fill="currentColor" />
    ))}
    <rect x={20} y={10} width={3} height={4} fill="#FAFF69" />
  </svg>
);

const SnowflakeLogo = ({ className }: LogoProps) => (
  <svg
    {...svgProps}
    className={className}
    fill="none"
    stroke="#29B5E8"
    strokeWidth={2}
    strokeLinecap="round"
  >
    <path d="M12 3v18M4.2 7.5l15.6 9M19.8 7.5l-15.6 9" />
  </svg>
);

const BigQueryLogo = ({ className }: LogoProps) => (
  <svg {...svgProps} className={className} fill="none">
    <path
      d="M12 2 20.7 7v10L12 22 3.3 17V7z"
      stroke="#4285F4"
      strokeWidth={1.8}
      strokeLinejoin="round"
    />
    <circle cx={11} cy={11} r={3.2} stroke="#4285F4" strokeWidth={1.8} />
    <path d="m13.4 13.4 3 3" stroke="#4285F4" strokeWidth={1.8} strokeLinecap="round" />
  </svg>
);

const DatabricksLogo = ({ className }: LogoProps) => (
  <svg {...svgProps} className={className} fill="none" stroke="#FF3621" strokeWidth={1.8}>
    <path d="m3 8 9-4.5L21 8l-9 4.5z" strokeLinejoin="round" />
    <path d="m3 12.5 9 4.5 9-4.5" strokeLinejoin="round" />
    <path d="m3 17 9 4.5 9-4.5" strokeLinejoin="round" />
  </svg>
);

const PostgresLogo = ({ className }: LogoProps) => (
  <svg {...svgProps} className={className} fill="none" stroke="#336791" strokeWidth={1.8}>
    <ellipse cx={12} cy={6} rx={7.5} ry={3.2} />
    <path d="M4.5 6v12c0 1.8 3.4 3.2 7.5 3.2s7.5-1.4 7.5-3.2V6" strokeLinecap="round" />
    <path d="M4.5 12c0 1.8 3.4 3.2 7.5 3.2s7.5-1.4 7.5-3.2" strokeLinecap="round" />
  </svg>
);

const MySqlLogo = ({ className }: LogoProps) => (
  <svg
    {...svgProps}
    className={className}
    fill="none"
    stroke="#00758F"
    strokeWidth={1.8}
    strokeLinecap="round"
  >
    <path d="M3 18c5.5 0 9-3 10.5-7C15 7 17.5 5 21 5" strokeLinejoin="round" />
    <path d="M21 5c0 4-1.2 7.5-3.5 10" />
    <circle cx={17.8} cy={8.4} r={1.1} fill="#00758F" stroke="none" />
  </svg>
);

const MsSqlLogo = ({ className }: LogoProps) => (
  <svg {...svgProps} className={className} fill="none" stroke="#A4373A" strokeWidth={1.8}>
    <rect x={3} y={3.5} width={18} height={5.5} rx={1.4} />
    <rect x={3} y={15} width={18} height={5.5} rx={1.4} />
    <path d="M6.5 6.25h.01M6.5 17.75h.01" strokeLinecap="round" strokeWidth={2.4} />
    <path d="M12 9v6" strokeLinecap="round" />
  </svg>
);

const OracleLogo = ({ className }: LogoProps) => (
  <svg {...svgProps} className={className} fill="none">
    <rect
      x={2}
      y={7}
      width={20}
      height={10}
      rx={5}
      stroke="#C74634"
      strokeWidth={2.6}
    />
  </svg>
);

const S3Logo = ({ className }: LogoProps) => (
  <svg {...svgProps} className={className} fill="none" stroke="#E25444" strokeWidth={1.8}>
    <path d="M4 5h16l-1.8 15.2a1.4 1.4 0 0 1-1.4 1.3H7.2a1.4 1.4 0 0 1-1.4-1.3z" strokeLinejoin="round" />
    <path d="M4 5c0-1.1 3.6-2 8-2s8 .9 8 2" strokeLinecap="round" />
    <path d="M6.2 11.5h11.6" strokeLinecap="round" />
  </svg>
);

const AzureBlobLogo = ({ className }: LogoProps) => (
  <svg {...svgProps} className={className} fill="none" stroke="#0089D6" strokeWidth={1.8}>
    <path d="M9.5 3 3 18h5.2L14.5 3z" strokeLinejoin="round" />
    <path d="M12.8 8 21 21H8.4l3-4.6" strokeLinejoin="round" />
  </svg>
);

const GcsLogo = ({ className }: LogoProps) => (
  <svg {...svgProps} className={className} fill="none" stroke="#1A73E8" strokeWidth={1.8}>
    <path
      d="M17.5 19H7a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18 10.5a4.25 4.25 0 0 1-.5 8.5z"
      strokeLinejoin="round"
    />
    <path d="M9.5 14.5h5" strokeLinecap="round" />
  </svg>
);

const SftpLogo = ({ className }: LogoProps) => (
  <svg
    {...svgProps}
    className={className}
    fill="none"
    stroke="#5B6BD6"
    strokeWidth={1.8}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M13.5 2.5H6.5A1.5 1.5 0 0 0 5 4v16a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 20V8z" />
    <path d="M13.5 2.5V8H19" />
    <path d="M9 13.5h6M12.5 11l2.5 2.5-2.5 2.5" />
  </svg>
);

const LOGOS: Record<ConnectorLogoName, (props: LogoProps) => React.ReactElement> = {
  clickhouse: ClickHouseLogo,
  snowflake: SnowflakeLogo,
  bigquery: BigQueryLogo,
  databricks: DatabricksLogo,
  postgresql: PostgresLogo,
  mysql: MySqlLogo,
  mssql: MsSqlLogo,
  oracle: OracleLogo,
  s3: S3Logo,
  'azure-blob': AzureBlobLogo,
  gcs: GcsLogo,
  sftp: SftpLogo,
};

interface ConnectorLogoProps {
  readonly name: ConnectorLogoName;
  readonly className?: string;
}

export const ConnectorLogo = ({ name, className = 'h-6 w-6' }: ConnectorLogoProps) => {
  const Logo = LOGOS[name];
  return <Logo className={className} />;
};

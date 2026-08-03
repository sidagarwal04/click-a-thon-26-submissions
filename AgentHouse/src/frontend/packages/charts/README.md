# da Insight SDK 🚀

A powerful React component library for creating data-driven insights and visualizations. Unlike traditional chart libraries, da Insight SDK focuses on delivering meaningful insights through various visualization types, making it easier to understand and communicate data patterns and trends.

## Features ✨

- **Multiple Insight Types**:

  - Trend Insights: Track changes and patterns over time
  - Contributor Insights: Break down metrics by dimensions
  - Ranking Insights: Compare and rank different entities
  - Summary Insights: Quick overview of key metrics
  - Comparison Insights: Compare metric with reference lines (Min, Max, Avg, Median and Moving Average)

- **Rich Visualization Support**:

  - Big Number: Simple metric display
  - Big Number with Trend: Metric with trend indicator
  - Line Charts: Time-series trends
  - Area Charts: Cumulative trends
  - Bar Charts: Categorical comparisons
  - Mixed Charts: Combination of bars, lines, and areas
  - Ranking Charts: Ordered comparisons

- **Interactive Features**:
  - Time grain selection
  - Customizable filters
  - Dimension filtering
  - Data comparison capabilities
  - Responsive design

## Installation 📦

```bash
npm install da-insight-sdk
# or
yarn add da-insight-sdk
```

## Quick Start 🚀

Here's a simple example of creating a trend insight with a bar chart:

```tsx
import { Insight, ChartTypes } from "da-insight-sdk";

const TrendInsight = () => {
  const metrics = [
    {
      metricKey: "revenue",
      metricLabel: "Revenue",
    },
  ];

  const dataResolver = async ({ payload, insight_type }) => {
    return {
      data: [
        { date: "2024-01", revenue: 1000 },
        { date: "2024-02", revenue: 1200 },
        { date: "2024-03", revenue: 1500 },
      ],
    };
  };

  return (
    <Insight
      type={ChartTypes.BAR}
      title="Revenue Trend"
      description="Monthly revenue trends"
      metrics={metrics}
      timeGrain="MONTHLY"
      timeRange={90}
      dataResolver={dataResolver}
    />
  );
};
```

## Insight Types and Visualizations 📊

> **Note**: Chart type is specified at the Insight component level using the `type` prop. The only exception is for Mixed charts, where each metric can specify its own chart type.

### 1. Trend Insights

Track changes and patterns over time.

<div style="display: flex; gap: 12px; align-items: flex-end;">
  <img src="https://res.cloudinary.com/dqjrfzbxx/image/upload/v1748522767/Trend_Bar_fnqucw.png" alt="Sample Trend Insight - Bar Chart" width="30%"/>
  <img src="https://res.cloudinary.com/dqjrfzbxx/image/upload/v1748522767/Trend_Line_upszrc.png" alt="Sample Trend Insight - Line Chart" width="30%"/>
  <img src="https://res.cloudinary.com/dqjrfzbxx/image/upload/v1748522767/Trend_Area_ywdnou.png" alt="Sample Trend Insight - Area Chart" width="30%"/>
</div>
<br>
<em>Sample outputs: Trend Insight (Bar, Line, and Area Charts)</em>

```tsx
import { ChartTypes, Insight } from "da-insight-sdk";

// Example: Revenue trend with line chart
const TrendInsight = () => {
  const dataResolver = async ({ payload, insight_type }) => {
    // Example response structure
    return {
      data: [
        { fromtime: "2024-01-01", totime: "2024-01-31", revenue: 1000 },
        { fromtime: "2024-02-01", totime: "2024-02-29", revenue: 1200 },
        { fromtime: "2024-03-01", totime: "2024-03-31", revenue: 1500 },
      ],
      interpretation: ["Revenue has shown a consistent upward trend over the last 3 months"],
    };
  };

  return (
    <div className="h-72">
      <Insight
        title="Revenue Trend"
        type={ChartTypes.LINE}
        metrics={[
          {
            metricKey: "revenue",
            metricLabel: "Revenue",
          },
        ]}
        dataResolver={dataResolver}
        options={{ className: "h-full" }}
      />
    </div>
  );
};
```

### 2. Contributor Insights

Break down metrics by dimensions.

<img src="https://res.cloudinary.com/dqjrfzbxx/image/upload/v1748522766/Contributor_eskcnk.png" alt="Sample Contributor Insight - CSAT by Agent Team" width="350"/>
<br>
<em>Sample output: CSAT by Agent Team (Contributor Insight)</em>

```tsx
import { ChartTypes, Insight } from "da-insight-sdk";

// Example: CSAT by Agent Team
const ContributorInsight = () => {
  const dataResolver = async ({ payload, insight_type }) => {
    // Example response structure
    return {
      data: [
        { fromtime: "2024-01-01", totime: "2024-01-31", "Team A": 85, "Team B": 92, "Team C": 78 },
        { fromtime: "2024-02-01", totime: "2024-02-28", "Team A": 75, "Team B": 67, "Team C": 58 },
        { fromtime: "2024-03-01", totime: "2024-03-31", "Team A": 27, "Team B": 22, "Team C": 48 },
      ],
      interpretation: ["Team B has the highest CSAT score of 92"],
    };
  };

  const dimensionValuesResolver = async (dimension) => {
    // Example response structure
    return ["Team A", "Team B", "Team C"];
  };

  return (
    <div className="h-72">
      <Insight
        title="CSAT by Agent Team"
        type={ChartTypes.MIXED}
        metrics={[
          {
            metricKey: "csat",
            metricLabel: "CSAT",
            chartType: ChartTypes.BAR,
          },
        ]}
        filters={{
          csat: {
            showDimensionContributionIn: "agent_team",
          },
        }}
        dataResolver={dataResolver}
        dimensionValuesResolver={dimensionValuesResolver}
        options={{ className: "h-full" }}
      />
    </div>
  );
};
```

### 3. Ranking Insights

Compare and rank different entities.

<img src="https://res.cloudinary.com/dqjrfzbxx/image/upload/v1748522766/Ranking_kahp7o.png" alt="Sample Ranking Insight" width="70%"/>
<br>
<em>Sample output: Ranking Insight</em>

```tsx
import { ChartTypes, Insight } from "da-insight-sdk";

// Example: CSAT Ranking by Agent Team
const RankingInsight = () => {
  const dataResolver = async ({ payload, insight_type }) => {
    // Example response structure
    return {
      data: [{ fromtime: "2024-01-01", totime: "2024-03-31", "Team A": 85, "Team B": 92, "Team C": 78 }],
      interpretation: ["Team B leads with the highest CSAT score of 92"],
    };
  };

  return (
    <div className="h-72">
      <Insight
        title="CSAT by Agent Team"
        type={ChartTypes.RANKING}
        metrics={[
          {
            metricKey: "csat",
            metricLabel: "CSAT",
          },
        ]}
        filters={{
          csat: {
            showDimensionContributionIn: "agent_team",
          },
        }}
        dataResolver={dataResolver}
        options={{ className: "h-full" }}
      />
    </div>
  );
};
```

### 4. Summary Insights

Quick overview of key metrics.

<div style="display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap;">
  <img src="https://res.cloudinary.com/dqjrfzbxx/image/upload/v1748522766/Summary_BigNumber_rah9c4.png" alt="Sample Summary Insight - Big Number" width="48%"/>
  <img src="https://res.cloudinary.com/dqjrfzbxx/image/upload/v1748522766/Summary_BigNumberWithTrend_nvvzpb.png" alt="Sample Summary Insight - Big Number with Trend" width="50%"/>
  <img src="https://res.cloudinary.com/dqjrfzbxx/image/upload/v1748522766/Summary_Expanded_qxn1c0.png" alt="Sample Summary Insight - Big Number Expanded" width="100%"/>
</div>
<br>
<em>Sample outputs: Summary Insight (Big Number, Big Number with Trend and Big Number Expanded)</em>

```tsx
import { ChartTypes, Insight } from "da-insight-sdk";

// Example: Positive Conversations Summary
const SummaryInsight = () => {
  const dataResolver = async ({ payload, insight_type }) => {
    // Example response structure
    return {
      data: [
        {
          fromtime: "2024-02-01",
          totime: "2024-02-28",
          positive_conversations: 1500,
        },
        {
          fromtime: "2024-03-01",
          totime: "2024-03-31",
          positive_conversations: 1800,
        },
      ],
      interpretation: ["Positive conversations increased by 15% compared to previous period"],
    };
  };

  return (
    <div className="h-48">
      <Insight
        title="Positive Conversations"
        type={ChartTypes.BIGNUMBERWITHTREND}
        metrics={[
          {
            metricKey: "positive_conversations",
            metricLabel: "Positive Conversations",
          },
        ]}
        dataResolver={dataResolver}
        options={{ className: "h-full" }}
      />
    </div>
  );
};
```

### 5. Comparison Insights

Compare metric with reference lines (Min, Max, Avg, Median and Moving Average).

<img src="https://res.cloudinary.com/dqjrfzbxx/image/upload/v1748522766/Comparison_pr14j0.png" alt="Sample Comparison Insight" width="75%"/>
<br>
<em>Sample output: Comparison Insight</em>

```tsx
import { ChartTypes, Insight } from "da-insight-sdk";

// Example: Positive Conversations with Reference Lines
const ComparisonInsight = () => {
  const dataResolver = async ({ payload, insight_type }) => {
    // Example response structure
    return {
      data: [
        {
          fromtime: "2024-01-01",
          totime: "2024-01-31",
          positive_conversations: 1000,
          min: 800,
          max: 1200,
          avg: 1000,
          median: 950,
          moving_avg: 980,
        },
        {
          fromtime: "2024-02-01",
          totime: "2024-02-29",
          positive_conversations: 1200,
          min: 800,
          max: 1200,
          avg: 1000,
          median: 950,
          moving_avg: 1050,
        },
        {
          fromtime: "2024-03-01",
          totime: "2024-03-31",
          positive_conversations: 1500,
          min: 800,
          max: 1200,
          avg: 1000,
          median: 950,
          moving_avg: 1150,
        },
      ],
      interpretation: ["Positive conversations are consistently above average"],
    };
  };

  return (
    <div className="h-72">
      <Insight
        title="Positive Conversations Comparison"
        type={ChartTypes.BAR}
        metrics={[
          {
            metricKey: "positive_conversations",
            metricLabel: "Positive Conversations",
          },
        ]}
        filters={{
          positive_conversations: {
            compareWith: ["min", "max", "median", "moving_avg", "avg"],
          },
        }}
        dataResolver={dataResolver}
        options={{ className: "h-full" }}
      />
    </div>
  );
};
```

### 6. Mixed Chart Example

Combine multiple chart types in a single visualization.

<img src="https://res.cloudinary.com/dqjrfzbxx/image/upload/v1748522766/Mixed_naaf7t.png" alt="Sample Mixed Chart Insight" width="80%"/>
<br>
<em>Sample output: Mixed Chart Insight</em>

## Props 📝

### Insight Component

| Prop                    | Type                     | Description                                     | Required | Default |
| ----------------------- | ------------------------ | ----------------------------------------------- | -------- | ------- |
| type                    | ChartTypes               | Type of chart to display                        | Yes      | -       |
| title                   | string                   | Title of the insight                            | No       | -       |
| description             | string                   | Description of the insight                      | No       | -       |
| metrics                 | IMetric[]                | Array of metrics to display                     | Yes      | -       |
| timeGrain               | TimeGrain                | Time granularity (DAILY, WEEKLY, MONTHLY, etc.) | No       | MONTHLY |
| timeRange               | number                   | Number of time units to display                 | No       | 180     |
| filters                 | IFilters                 | Custom filters for the data                     | No       | -       |
| options                 | IOptions                 | Display options (`hideTitle`, `compact`, `micro`, `expanded`, `hideCard`, `className`, `showExplanation`, `periodLabel`, `vsLabel`, `currentWindowLabel`, `align`) | No       | -       |
| actions                 | MenuItem[]               | Custom actions for the insight                  | No       | -       |
| dataResolver            | IDataResolver            | Data resolver                                   | Yes      | -       |
| dimensionValuesResolver | IDimensionValuesResolver | Dimension values resolver                       | No\*     | -       |

\*Required only for Contributor insights

> **Note**: If `timeGrain` and `timeRange` are not provided, the component will default to monthly granularity and a 180-day time range.

## Data Resolvers 🔄

### Data Resolver

The `dataResolver` is a required function that fetches and processes data for your insights. It receives a payload object and insight type, and returns a promise with the processed data.

```tsx
interface IDataResolverResponse {
  data: IEntry[]; // Array of data entries
  query?: string; // Optional: The database query that was executed to fetch this data
  interpretation?: string[]; // Optional array of data interpretations that will be displayed under the chart
}

interface IEntry {
  date?: string;
  fromtime?: string;
  totime?: string;
  [key: string]: string | number;
}

// Example implementation
const dataResolver: IDataResolver = async ({ payload, insight_type }) => {
  // Fetch data from your API or data source
  const response = await fetchData(payload);

  return {
    data: response.data,
    query: response.query, // Optional: The actual query executed on the database
    interpretation: response.insights, // Optional: Will be displayed under the chart if provided
  };
};
```

> **Note**:
>
> - The `interpretation` field is optional. When provided, it will be displayed as a list of insights below the chart, helping users understand key patterns and trends in the data.
> - The `query` field is optional. When provided, it should contain the actual database query that was executed to fetch the data. This is useful for debugging and understanding the data source.

### Dimension Values Resolver

The `dimensionValuesResolver` is required only for Contributor insights. It fetches possible values for dimensions used in filtering and plotting.

```tsx
// Example implementation
const dimensionValuesResolver: IDimensionValuesResolver = async (dimension) => {
  // Example response for region dimension
  return ["North", "South", "East", "West"];
};
```

## Contributing 🤝

Contributions are welcome! Please feel free to submit a Pull Request.

## License 📄

ISC License

## Author 👨‍💻

Created by Thushar

---

Built with ❤️ using React, TypeScript, and Recharts

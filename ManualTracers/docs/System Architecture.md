# **Click-a-thon 2026: Automated Root-Cause Analyst Architecture**

This document details the end-to-end architecture for the Automated Root-Cause Analyst system, built primarily on ClickHouse and HyperDX, with an external Investigation Worker and an LLM for narrative synthesis.

## **Architecture Diagram**

The following Mermaid diagram visualizes the data flow, component interactions, and the step-by-step investigation process.

graph TD  
    %% Define Styles  
    classDef clickhouse fill:\#ffe733,stroke:\#333,stroke-width:2px,color:\#000;  
    classDef hyperdx fill:\#00d4ff,stroke:\#333,stroke-width:2px,color:\#000;  
    classDef python fill:\#4b8bbe,stroke:\#333,stroke-width:2px,color:\#fff;  
    classDef llm fill:\#7c3aed,stroke:\#333,stroke-width:2px,color:\#fff;  
    classDef user fill:\#e0e0e0,stroke:\#333,stroke-width:1px;

    %% Components  
    subgraph Data Sources  
        Events\[Raw Ad Events Stream\]  
    end

    subgraph ClickHouse \[ClickHouse: Data & Semantic Engine\]  
        direction TB  
        RawTables\[(Fact & Dimension Tables)\]  
        MV\[(Hourly Aggregated MV)\]  
        SemanticTable\[(Metric Definitions Table\<br/\>- Formulas\<br/\>- Dependencies\<br/\>- Z-Score Baselines)\]  
          
        Events \--\>|Insert| RawTables  
        RawTables \--\>|Real-time Rollup| MV  
    end

    subgraph HyperDX \[HyperDX / ClickStack: Observability\]  
        direction TB  
        AlertQuery\[Z-Score Calculation Query\<br/\>(Current vs Mean/SD)\]  
        Threshold\[Z-Score Threshold Trigger\]  
        Webhook\[Webhook Dispatcher\]

        MV \--\>|Query (Every 5-15m)| AlertQuery  
        SemanticTable \-.-\>|Threshold Config| AlertQuery  
        AlertQuery \--\> Threshold  
        Threshold \--\>|Breach Detected| Webhook  
    end

    subgraph InvestigationWorker \[Automated Investigation Engine\]  
        direction TB  
        WebhookReceiver\[Webhook Receiver API\]  
        SemanticLookup\[Semantic Mapper\]  
        FactorAnalyzer\[Factor Drill-down Logic\]  
        DimensionSlicer\[Dimension Isolation Logic\]  
        JSONBuilder\[Structured Output Builder\]

        WebhookReceiver \--\> SemanticLookup  
        SemanticLookup \--\>|Fetch Config| SemanticTable  
        SemanticLookup \--\> FactorAnalyzer  
        FactorAnalyzer \--\>|Query Factors| MV  
        FactorAnalyzer \--\> DimensionSlicer  
        DimensionSlicer \--\>|Query Segments| MV  
        DimensionSlicer \--\> JSONBuilder  
    end

    subgraph LLM \[Narrative Synthesis\]  
        PromptEngine\[Prompt Generator\]  
        Model\[LLM API\]  
          
        JSONBuilder \--\> PromptEngine  
        PromptEngine \--\> Model  
    end

    Output\[Final Plain-Language Diagnosis\]

    %% Main Flow  
    Webhook \--\>|JSON Payload:\<br/\>Metric, Time, Z-Score| WebhookReceiver  
    Model \--\> Output

    %% Assign Styles  
    class ClickHouse clickhouse;  
    class HyperDX hyperdx;  
    class InvestigationWorker python;  
    class LLM llm;  
    class Events,Output user;

## **Step-by-Step Execution Flow**

### **1\. Data Ingestion & Pre-Aggregation (ClickHouse)**

* The raw synthetic ad events flow into the base tables (ad\_events, apps, etc.).  
* To ensure lightning-fast alert evaluation and drill-downs, a **Materialized View (MV)** continuously denormalizes and aggregates this data into hourly buckets per dimension combination (e.g., timestamp, geo\_device\_id, ad\_format, requests, revenue).  
* Alongside the data, ClickHouse holds a **Metric Definitions Table**. This is the core semantic layer. It stores the SQL formula for every metric, its threshold (baseline z-score), its dependent factors (e.g., Revenue depends on Requests, Fill Rate, and eCPM), and the dimensions to check.

### **2\. Monitoring & Alerting (HyperDX)**

* HyperDX executes scheduled queries (e.g., every 5-15 minutes) against the aggregated MV in ClickHouse.  
* **The Z-Score Query:** Using a highly optimized ClickHouse query, HyperDX calculates the trailing mean and standard deviation for the metric over the last few weeks, then computes the current Z-score: (current\_value \- trailing\_mean) / std\_dev.  
* If the calculated Z-score exceeds the threshold defined in the Semantic Table (e.g., Z \< \-2.0), HyperDX triggers an alert.  
* HyperDX packages the anomaly context (the broken metric name, the timestamp, and the calculated Z-score) into a JSON payload and dispatches it via Webhook.

### **3\. Automated Drill-Down (Investigation Engine)**

* A standalone microservice (the Investigation Worker) receives the webhook.  
* **Semantic Lookup:** It queries the ClickHouse Metric Definitions Table to understand the alerted metric.  
* **Factor Analysis (Walking the Tree):** If the alert is for a composite metric like "Revenue," the engine does *not* immediately slice by dimension. Instead, it looks up the dependencies (requests, fill\_rate, ecpm) and queries ClickHouse to calculate their Z-scores. It identifies the true mathematical culprit (e.g., total requests dropped).  
* **Dimension Isolation:** Once the root metric is isolated, the engine queries the ClickHouse MV to calculate the Z-scores for that specific metric across all mapped dimensions (e.g., device\_model, region). It finds the exact segment driving the anomaly.  
* The engine formats all findings—the triggering alert, the true culprit segment, and the ruled-out factors—into a structured JSON object.

### **4\. Narrative Synthesis (LLM)**

* The structured JSON is passed into a strict prompt. The LLM has zero access to the database; it only sees the computed numbers and segments provided by the Investigation Engine.  
* The LLM generates a localized, plain-language diagnosis based *only* on the deterministic data provided, outputting a final, trustworthy root-cause explanation.
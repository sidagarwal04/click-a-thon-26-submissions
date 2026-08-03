**concurrency**  

> Use the *concurrency_deltas* table (minute bucket + delta).  
> Compute a running sum of deltas for each `(platform, country, content, …)` group over the requested minute range – that value is the exact active user count at every minute.  
> The peak is simply the maximum of those sums; the average is either an arithmetic mean or the total sum divided by elapsed minutes.  
> Because ClickHouse can prune partitions and read only the relevant columns, this runs in a fraction of a second and never scans raw session history.  

If you need sub‑second dashboards, materialize that running‑sum column into another table; otherwise run the windowed sum on demand.
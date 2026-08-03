-- Load the source files (Data/) into the tables defined in schema.sql.
-- Run with: clickhouse-client --queries-file load.sql
-- (paths are relative to the clickhouse-client process's working directory;
-- adjust to absolute paths, or use the ClickHouse Cloud console's file
-- upload / s3() table function, if INFILE isn't available on a hosted instance)

INSERT INTO apps        FROM INFILE '../Data/apps.txt'        FORMAT CSVWithNames;
INSERT INTO advertisers FROM INFILE '../Data/advertisers.txt' FORMAT CSVWithNames;
INSERT INTO geo_device  FROM INFILE '../Data/geo_device.txt'  FORMAT CSVWithNames;
INSERT INTO ad_events   FROM INFILE '../Data/ad_events.parquet' FORMAT Parquet;
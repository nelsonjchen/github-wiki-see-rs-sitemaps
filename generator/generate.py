payload_query = '''
#standardSQL
CREATE TEMPORARY FUNCTION
  parsePayload(payload STRING)
  RETURNS ARRAY<STRING>
  LANGUAGE js AS """ try { return JSON.parse(payload).pages.reduce((a,
      s) => {a.push(s.html_url); return a},
    []); } catch (e) { return []; } """;
WITH
  parsed_payloads AS (
  SELECT
    parsePayload(payload) AS html_urls
  FROM
    `github-wiki-see.scratch.multi_page`)
SELECT
  DISTINCT html_url
FROM
  parsed_payloads
CROSS JOIN
  UNNEST(parsed_payloads.html_urls) AS html_url
'''

from google.cloud import bigquery

client = bigquery.Client()

# Perform a query.
query_job = client.query(payload_query)  # API request
rows = query_job.result()  # Waits for query to finish

for row in rows:
    print(row.html_url)
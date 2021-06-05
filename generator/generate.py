# noinspection PyPackageRequirements
from google.cloud import bigquery


def generate():
    table = 'github-wiki-see.scratch.multi_page'
    payload_query_template = '''
#standardSQL
CREATE TEMPORARY FUNCTION
  parsePayload(payload STRING)
  RETURNS ARRAY<STRING>
  LANGUAGE js AS """ try { return JSON.parse(payload).pages.reduce((a,
      s) => {a.push(s.html_url); return a},
    []); } catch (e) { return []; } """;
SELECT
  *
FROM (
  WITH
    parsed_payloads AS (
    SELECT
      parsePayload(payload) AS html_urls,
      created_at
    FROM
      `github-wiki-see.scratch.multi_page` )
  SELECT
    DISTINCT html_url,
    created_at,
    ROW_NUMBER() OVER(PARTITION BY html_url ORDER BY created_at DESC) AS rn
  FROM
    parsed_payloads
  CROSS JOIN
    UNNEST(parsed_payloads.html_urls) AS html_url)
WHERE
  rn = 1
'''
    payload_query = payload_query_template.replace('github-wiki-see.scratch.multi_page', table)

    client = bigquery.Client()

    # Perform a query.
    query_job = client.query(payload_query)  # API request
    rows = query_job.result()  # Waits for query to finish

    for row in rows:
        print(row.html_url)


if __name__ == "__main__":
    generate()

query = '''
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
  DISTINCT html_urls
FROM
  parsed_payloads
CROSS JOIN
  UNNEST(parsed_payloads.html_urls) AS html_urls
'''

print("Hello")
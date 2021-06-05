# noinspection PyPackageRequirements
from google.cloud import bigquery


def generate():
    table = 'github-wiki-see.scratch.multi_page'
    payload_query = ('\n'
                     ' #standardSQL\n'
                     'CREATE TEMPORARY FUNCTION\n'
                     '  parsePayload(payload STRING)\n'
                     '  RETURNS ARRAY<STRING>\n'
                     '  LANGUAGE js AS """ try { return JSON.parse(payload).pages.reduce((a,\n'
                     '      s) => {a.push(s.html_url); return a},\n'
                     '    []); } catch (e) { return []; } """;\n'
                     'WITH\n'
                     '  parsed_payloads AS (\n'
                     '  SELECT\n'
                     '    parsePayload(payload) AS html_urls\n'
                     '  FROM\n'
                     f'    `{table}` )\n'
                     'SELECT\n'
                     '  DISTINCT html_url\n'
                     'FROM\n'
                     '  parsed_payloads\n'
                     'CROSS JOIN\n'
                     '  UNNEST(parsed_payloads.html_urls) AS html_url\n'
                     )

    client = bigquery.Client()

    # Perform a query.
    query_job = client.query(payload_query)  # API request
    rows = query_job.result()  # Waits for query to finish

    for row in rows:
        print(row.html_url)


if __name__ == "__main__":
    generate()

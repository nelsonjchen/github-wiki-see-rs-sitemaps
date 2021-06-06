import argparse
from datetime import date, timedelta
from xml.dom import minidom
import pathlib
import shutil

# noinspection PyPackageRequirements
from google.cloud import bigquery


def generate(bigquery_table=None):
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
      `github-wiki-see.scratch.multi_page`
    WHERE
      type = 'GollumEvent')
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
  AND html_url NOT LIKE "%/wiki/Home"
  AND html_url NOT LIKE "%/wiki/_Sidebar"
  AND html_url NOT LIKE "%/wiki/_Footer"
  AND html_url NOT LIKE "%/wiki/_Header"
'''
    payload_query = payload_query_template.replace('github-wiki-see.scratch.multi_page', bigquery_table)

    client = bigquery.Client()

    # Perform a query.
    query_job = client.query(payload_query)  # API request
    rows = query_job.result()  # Waits for query to finish

    root = minidom.Document()

    sitemap_urlset = root.createElement('urlset')
    sitemap_urlset.setAttribute('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
    sitemap_urlset.setAttribute('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    sitemap_urlset.setAttribute('xsi:schemaLocation',
                                'https://www.sitemaps.org/schemas/sitemap/0.9 '
                                'https://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd/XMLSchema-instance')

    root.appendChild(sitemap_urlset)

    # Generate XML File from query
    for row in rows:
        urlChild = root.createElement('url')
        sitemap_urlset.appendChild(urlChild)
        locChild = root.createElement('loc')
        urlChild.appendChild(locChild)
        locTextChild = root.createTextNode(row.html_url.replace(
            'https://github.com/', 'https://github-wiki-see.page/m/'
        ))
        locChild.appendChild(locTextChild)
        lastmodChild = root.createElement('lastmod')
        urlChild.appendChild(lastmodChild)
        lastmodTextChild = root.createTextNode(row.created_at.isoformat())
        lastmodChild.appendChild(lastmodTextChild)

    xml_str = root.toprettyxml(indent="\t")

    save_path_file = "../dist/generated_sitemap.xml"

    with open(save_path_file, "w") as f:
        f.write(xml_str)


def copy_manual_sitemaps():
    dist_dir = pathlib.Path('../dist')

    base_file = pathlib.Path('../base_sitemap.xml')
    shutil.copy(base_file, dist_dir)
    index_file = pathlib.Path('../base/sitemap_index.xml')
    shutil.copy(index_file, dist_dir)

    # Copy manual seed sitemaps
    shutil.copytree(pathlib.Path('../seed_sitemaps'), dist_dir / 'seed_sitemaps', dirs_exist_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate some sitemaps.')
    parser.add_argument('--realbq', dest='realbq', action='store_true')
    parser.set_defaults(realbq=False)

    args = parser.parse_args()

    pathlib.Path('../dist').mkdir(exist_ok=True)
    copy_manual_sitemaps()

    if args.realbq:
        yesterday = date.today() - timedelta(days=1)
        target_bigquery_table = f'githubarchive.day.{yesterday.strftime("%Y%m%d")}'
    else:
        target_bigquery_table = 'github-wiki-see.scratch.multi_page'

    print(f'Pulling from BQ table: {target_bigquery_table}')
    generate(bigquery_table=target_bigquery_table)

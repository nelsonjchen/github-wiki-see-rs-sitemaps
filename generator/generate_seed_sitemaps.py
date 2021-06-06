import argparse
from datetime import date, timedelta
from xml.dom import minidom
import pathlib
import shutil

# noinspection PyPackageRequirements
from google.cloud import bigquery

"""
Manually edited file to generate seed sitemaps from past months
"""



def generate(bigquery_table=None):
    payload_query_template = '''
    SELECT * FROM `github-wiki-see.scratch.multi_page`
'''
    payload_query = payload_query_template.replace('github-wiki-see.scratch.multi_page', bigquery_table)

    client = bigquery.Client()

    # Perform a query.
    query_job = client.query(payload_query)  # API request
    pages = query_job.result(page_size=45000).pages  # Waits for query to finish

    for count, page in enumerate(pages):
        root = minidom.Document()

        sitemap_urlset = root.createElement('urlset')
        sitemap_urlset.setAttribute('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
        sitemap_urlset.setAttribute('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        sitemap_urlset.setAttribute('xsi:schemaLocation',
                                    'https://www.sitemaps.org/schemas/sitemap/0.9 '
                                    'https://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd/XMLSchema-instance')

        root.appendChild(sitemap_urlset)

        # Generate XML File from query
        for row in page:
            urlChild = root.createElement('url')
            sitemap_urlset.appendChild(urlChild)
            locChild = root.createElement('loc')
            urlChild.appendChild(locChild)
            locTextChild = root.createTextNode(row.html_url.replace(
                'https://github.com/', 'https://github-wiki-see.page/m/'
            ))
            locChild.appendChild(locTextChild)

        xml_str = root.toprettyxml(indent="\t")

        save_path_file = f"../seed_sitemaps/{bigquery_table}_{count}.xml"

        with open(save_path_file, "w") as f:
            f.write(xml_str)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate seed sitemaps from table with html_url')
    parser.add_argument('--table', dest='table', action='store', required=True)

    args = parser.parse_args()

    pathlib.Path('../seed_sitemaps').mkdir(exist_ok=True)

    print(f'Pulling from BQ table: {args.table}')
    generate(bigquery_table=args.table)

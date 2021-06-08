import argparse
import json
import pathlib

# noinspection PyPackageRequirements
from google.cloud import bigquery, pubsub
from tqdm import tqdm

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
    pages = query_job.result(page_size=1000).pages  # Waits for query to finish

    publisher = pubsub.PublisherClient(
        batch_settings=pubsub.types.BatchSettings(
            max_messages=1000,
            max_latency=10
        )
    )

    future = None
    for count, page in enumerate(tqdm(pages, desc="pages")):
        print(f"Processing page {count}")
        for row in tqdm(page, desc="rows"):
            message_object_bytes = json.dumps({
                "url": row.html_url,
                "created_at": row.created_at.isoformat(),
            }).encode('utf8')

            topic_path = publisher.topic_path("github-wiki-see", "head_checker_input")
            future = publisher.publish(topic_path, message_object_bytes)

        future.result()
        print(f"Processed page {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate seed sitemaps from table with html_url')
    parser.add_argument('--table', dest='table', action='store', required=True)

    args = parser.parse_args()

    pathlib.Path('../seed_sitemaps').mkdir(exist_ok=True)

    print(f'Pulling from BQ table: {args.table}')
    generate(bigquery_table=args.table)

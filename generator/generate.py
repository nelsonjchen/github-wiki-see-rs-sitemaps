import argparse
import json
from datetime import date, timedelta
from xml.dom import minidom
import pathlib
import shutil
import datetime
from smart_open import smart_open


def generate_last_week_from_gha(hours_back=2):
    """
    Use cheaper S3 Archives from Github Archives
    :return:
    """
    print(f"Processing {hours_back=}")

    def file_names_for_hours_back():
        now = datetime.datetime.utcnow() - timedelta(hours=1)
        while True:
            yield now - timedelta(hours=1)
            now = now - timedelta(hours=1)

    urls_to_last_mod = {}

    for hour_back, archive_datetime in zip(range(hours_back), file_names_for_hours_back()):
        print(f"{hour_back + 1} hour(s) back")
        try:
            url = f"https://data.gharchive.org/{archive_datetime.year}-{archive_datetime.month:02d}-{archive_datetime.day:02d}-{archive_datetime.hour}.json.gz"
            with smart_open(url, 'r', encoding='utf-8') as f:
                print(f'Opening {url}')
                for line in f:
                    event = json.loads(line)
                    if event['type'] != 'GollumEvent':
                        continue
                    event_created_at = datetime.datetime.fromisoformat(event['created_at'][:-1])
                    for page in event['payload']['pages']:
                        if page['html_url'].endswith('wiki/Home') or page['html_url'].endswith('wiki/_Sidebar') or \
                                page['html_url'].endswith('wiki/_Footer') or page['html_url'].endswith('wiki/_Header'):
                            continue

                        if page['html_url'] in urls_to_last_mod:
                            if urls_to_last_mod[page['html_url']] < event_created_at:
                                urls_to_last_mod[page['html_url']] = event_created_at
                        else:
                            urls_to_last_mod[page['html_url']] = event_created_at
        except Exception as e:
            print(e)

        print(f'Entries in {len(urls_to_last_mod)=}')

    root = minidom.Document()

    sitemap_urlset = root.createElement('urlset')
    sitemap_urlset.setAttribute('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
    sitemap_urlset.setAttribute('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    sitemap_urlset.setAttribute('xsi:schemaLocation',
                                'https://www.sitemaps.org/schemas/sitemap/0.9 '
                                'https://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd/XMLSchema-instance')

    root.appendChild(sitemap_urlset)
    root.appendChild(root.createComment("Content based on www.gharchive.org used under the CC-BY-4.0 license."))

    # Generate XML File from query
    for url, last_mod in urls_to_last_mod.items():
        urlChild = root.createElement('url')
        sitemap_urlset.appendChild(urlChild)
        locChild = root.createElement('loc')
        urlChild.appendChild(locChild)
        locTextChild = root.createTextNode(url.replace(
            'https://github.com/', 'https://github-wiki-see.page/m/'
        ))
        locChild.appendChild(locTextChild)
        lastmodChild = root.createElement('lastmod')
        urlChild.appendChild(lastmodChild)
        lastmodTextChild = root.createTextNode(last_mod.isoformat() + "+00:00")
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
    # parser.add_argument('--realbq', dest='realbq', action='store_true')
    parser.add_argument('--real_week', dest='real_week', action='store_true')

    parser.set_defaults(realbq=False)

    args = parser.parse_args()

    pathlib.Path('../dist').mkdir(exist_ok=True)
    copy_manual_sitemaps()

    # if args.realbq:
    #     yesterday = date.today() - timedelta(days=1)
    #     target_bigquery_table = f'githubarchive.day.{yesterday.strftime("%Y%m%d")}'
    # else:
    #     target_bigquery_table = 'github-wiki-see.scratch.multi_page'

    # print(f'Pulling from BQ table: {target_bigquery_table}')
    # generate(bigquery_table=target_bigquery_table)

    if args.real_week:
        hours_back = 24 * 7
    else:
        hours_back = 2

    # Use S3 Archives
    generate_last_week_from_gha(hours_back)

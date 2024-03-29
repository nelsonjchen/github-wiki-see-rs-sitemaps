import argparse
import dataclasses
import datetime
import json
import pathlib
import shutil
from datetime import timedelta
from multiprocessing import Pool
from xml.dom import minidom

from diskcache import Cache
from smart_open import smart_open

current_dir = pathlib.Path(__file__).parent
cache = Cache(f'{current_dir}/cache')


@dataclasses.dataclass
class HourBackDate:
    year: int
    month: int
    day: int
    hour: int


def generate_last_week_from_gha(hours_back=2):
    """
    Use Archives from Github Archives
    :return:
    """
    print(f"Processing {hours_back=}")

    def file_names_for_hours_back():
        now = datetime.datetime.utcnow() - timedelta(hours=1)
        while True:
            yield_date = now - timedelta(hours=1)
            yield HourBackDate(
                yield_date.year,
                yield_date.month,
                yield_date.day,
                yield_date.hour
            )
            now = now - timedelta(hours=1)

    urls_to_last_mod = {}

    pool = Pool(processes=8)
    for url_date_dict in pool.imap_unordered(
            process_hour_back_archive_time,
            zip(
                range(hours_back),
                file_names_for_hours_back()
            )
    ):
        for url, page_date in url_date_dict.items():
            if url in urls_to_last_mod:
                if urls_to_last_mod[url] < page_date:
                    urls_to_last_mod[url] = page_date
            else:
                urls_to_last_mod[url] = page_date
        print(f"Current entries so far in {len(urls_to_last_mod)=}")

    print(f"Processed {hours_back + 1}, Entries in {len(urls_to_last_mod)=}")

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


def process_hour_back_archive_time(f_args):
    print(f"_Processing with possible cache {f_args=} ")
    hour_back, archive_datetime = f_args
    print(f'_Processing {hour_back + 1} hour(s) back')
    res = _process_archive_time(archive_datetime)
    print(f'_Processed {hour_back + 1} hour(s) back with {len(res)} entries')
    print(f"_Processed with possible cache {f_args=}")
    return res


# Cache it for a month
@cache.memoize(expire=60 * 60 * 24 * 7 * 4)
def _process_archive_time(archive_datetime):
    urls_to_last_mod_chunk = {}
    url = f"https://data.gharchive.org/{archive_datetime.year}-{archive_datetime.month:02d}-{archive_datetime.day:02d}-{archive_datetime.hour}.json.gz"
    try:
        with smart_open(url, 'r', encoding='utf-8') as f:
            for line in f:
                event = json.loads(line)
                if event['type'] != 'GollumEvent':
                    continue
                event_created_at = datetime.datetime.fromisoformat(event['created_at'][:-1])
                for page in event['payload']['pages']:
                    if page['html_url'].endswith('wiki/Home') or page['html_url'].endswith('wiki/_Sidebar') or \
                            page['html_url'].endswith('wiki/_Footer') or page['html_url'].endswith('wiki/_Header'):
                        continue

                    if page['html_url'] in urls_to_last_mod_chunk:
                        if urls_to_last_mod_chunk[page['html_url']] < event_created_at:
                            urls_to_last_mod_chunk[page['html_url']] = event_created_at
                    else:
                        urls_to_last_mod_chunk[page['html_url']] = event_created_at
    except Exception as e:
        print(e, f'Error for {url}')
        return {}
    print(f'Processed {url}, Entries in {len(urls_to_last_mod_chunk)=}')
    return urls_to_last_mod_chunk


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
    parser.add_argument('--hours_back', dest='hours_back', type=int, default=2)

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

    hours_back = 2
    if args.hours_back:
        hours_back = args.hours_back

    # Use Archives
    generate_last_week_from_gha(hours_back)

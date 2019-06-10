import argparse
from datetime import datetime
import os

from notion.client import NotionClient
import yaml


default_option = {
    'title': True,
    'content': False,
    'props': [],

    'created': None,
    'edited': None,
}
option_keys = list(default_option.keys())

now = datetime.now()


def cleanup_by(config):
    client = NotionClient(token_v2=config['token'])
    global_option = new_option(default_option, config)

    if config['databases'] is None:
        config['databases'] = []

    for job in config['databases']:
        if 'url' not in job:
            continue

        job_option = new_option(global_option, job)
        result = cleanup(client, job['url'], job_option)

        print(result)


def cleanup(client, db_block_url, option):
    db = client.get_block(db_block_url)
    if 'collection' not in db.type:
        return 'fail: is not db'

    if db.role != 'editor':
        return 'fail: page access is %s, require: editor' % db.role

    rows = db.collection.get_rows()
    count = 0
    for row in rows:
        if is_remove_target(row, option):
            row.remove()
            count += 1

    return 'done: remove %d rows' % count


def is_remove_target(row, option):
    if not row.alive:
        return False

    if not is_check_target(row, option):
        return False

    q = [
        not option['title'] or len(row.title) == 0 or row.title.isspace(),
        not option['content'] or len(row.children) == 0,
    ]

    props = [
        prop
        for prop in row.schema
        if prop['name'] in option['props']
    ]

    if len(props) > 0:
        row_data = row.get_all_properties()
        target_data = []
        for prop in props:
            value = row_data.get(prop['slug'])
            target_data.append({
                'prop': prop,
                'value': value,
                'is_empty': is_empty_value(value),
            })

        q.append(all([d['is_empty'] for d in target_data]))

    return all(q)


def is_empty_value(value):
    if value is None:
        return True

    if isinstance(value, str):
        return value.isspace()

    if isinstance(value, list):
        return len(value) == 0

    return False


def is_check_target(row, option):
    row_info = row.get()

    if option['created'] is not None:
        created_time = parse_timestamp(row_info['created_time'])
        created_delta = (now - created_time).total_seconds()
        if created_delta < option['created']:
            return False

    if option['edited'] is not None:
        last_edited_time = parse_timestamp(row_info['last_edited_time'])
        edited_delta = (now - last_edited_time).total_seconds()
        if edited_delta < option['edited']:
            return False

    return True


def parse_timestamp(timestamp):
    return datetime.fromtimestamp(int(timestamp) / 1000.0)


def new_option(option, option2):
    new_dict = {**filter_option_keys(option), **filter_option_keys(option2)}

    if not isinstance(new_dict.get('title'), bool):
        new_dict['title'] = default_option['title']
    if not isinstance(new_dict.get('content'), bool):
        new_dict['content'] = default_option['content']
    if not isinstance(new_dict.get('props'), list):
        new_dict['props'] = default_option['props']

    created = new_dict.get('created')
    if not (created is None or isinstance(created, int)):
        new_dict['created'] = None
    edited = new_dict.get('edited')
    if not (edited is None or isinstance(edited, int)):
        new_dict['edited'] = None

    return new_dict


def filter_option_keys(d):
    return {k: v for k, v in d.items() if k in option_keys}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config', nargs='*', default=[], help='config files')
    args = parser.parse_args()

    for path in args.config:
        if not os.path.exists(path):
            print('not found `%s`' % path)
            continue

        with open(path) as stream:
            cf = yaml.safe_load(stream)

        cleanup_by(cf)

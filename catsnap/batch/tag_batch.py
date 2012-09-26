from __future__ import unicode_literals

from catsnap import Client, HASH_KEY
from boto.dynamodb.batch import BatchWriteList, BatchList
from boto.dynamodb.item import Item
import json

def get_tag_items(tag_names):
    if not tag_names:
        raise StopIteration
     
    tag_names = list(set(tag_names))

    dynamo = Client().get_dynamodb()
    table = Client().table('tag')
    batch_list = BatchList(dynamo)
    batch_list.add_batch(table, tag_names,
            attributes_to_get=['filenames', HASH_KEY])
    response = dynamo.batch_get_item(batch_list)
    items = response['Responses'][table.name]['Items']
    unprocessed_keys = []
    if response['UnprocessedKeys'] \
            and table.name in response['UnprocessedKeys']:
        for key in response['UnprocessedKeys'][table.name]['Keys']:
            unprocessed_keys.append(key['HashKeyElement'])

    for item in items:
        yield item
    for item in get_tag_items(unprocessed_keys):
        yield item

def get_tags(tag_names):
    for item in get_tag_items(tag_names):
        yield { 'tag': item[HASH_KEY],
                'filenames': json.loads(item['filenames'])}

def add_image_to_tags(filename, tag_names):
    items = list(get_tag_items(tag_names))
    for item in items:
        filenames = json.loads(item['filenames'])
        filenames.append(filename)
        item['filenames'] = json.dumps(filenames)

    table = Client().table('tag')
    for new_tag in set(tag_names) - set(x[HASH_KEY] for x in items):
        items.append(table.new_item(hash_key = new_tag,
                attrs={'filenames': json.dumps([filename])}))

    _submit_items(table, items)

def _submit_items(table, items):
    dynamo = Client().get_dynamodb()
    write_list = BatchWriteList(dynamo)
    write_list.add_batch(table, puts=items)
    response = write_list.submit()
    if 'UnprocessedItems' in response \
            and table.name in response['UnprocessedItems']:
        unprocessed_keys = set(x['PutRequest']['Item'][HASH_KEY]
                for x in response['UnprocessedItems'][table.name])
        unprocessed_items = filter(
                lambda x: x[HASH_KEY] in unprocessed_keys, items)
        _submit_items(table, unprocessed_items)

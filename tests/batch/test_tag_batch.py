from __future__ import unicode_literals

from mock import patch, Mock, MagicMock, call
from nose.tools import eq_
from tests import TestCase

from catsnap import HASH_KEY
from catsnap.batch.tag_batch import get_tags, add_image_to_tags, get_tag_items

class TestTagBatch(TestCase):
    @patch('catsnap.batch.tag_batch.Client')
    @patch('catsnap.batch.tag_batch.BatchList')
    def test_get_tags(self, BatchList, Client):
        mock_client = Mock()
        table = Mock()
        table.name = 'the-name-of-the-table'
        mock_client.table.return_value = table
        dynamo = Mock()
        dynamo.batch_get_item.return_value = {
                'UnprocessedKeys': {},
                'Responses': {
                    'the-name-of-the-table': {
                        'Items': [
                            {
                                HASH_KEY: 'cats',
                                'filenames': '["deadbeef", "badcafe", "defec8"]'},
                            {
                                HASH_KEY: 'dogs',
                                'filenames': '["5ca1ab1e", "deadbeef"]'}],
                        'ConsumedCapacityUnits': 10.0}}}
        mock_client.get_dynamodb.return_value = dynamo
        Client.return_value = mock_client
        batch_list = Mock()
        BatchList.return_value = batch_list

        tags = list(get_tags(['a', 'b']))
        BatchList.assert_called_once_with(dynamo)
        batch_list.add_batch.assert_called_once_with(
                table, ['a', 'b'], attributes_to_get=['filenames', HASH_KEY])
        dynamo.batch_get_item.assert_called_with(batch_list)
        eq_(tags, [
            {
                'tag': 'cats',
                'filenames': [ 'deadbeef', 'badcafe', 'defec8']},
            {
                'tag': 'dogs',
                'filenames': [ '5ca1ab1e', 'deadbeef']}])


    @patch('catsnap.batch.tag_batch.Client')
    @patch('catsnap.batch.tag_batch.BatchList')
    def test_get_tags__checks_back_on_unprocessed_keys(self,
            BatchList, Client):
        mock_client = Mock()
        table = Mock()
        table.name = 'thetablename'
        mock_client.table.return_value = table
        dynamo = Mock()
        first_getitem = {
                'UnprocessedKeys': {
                    'thetablename': {
                        'Keys': [ {'HashKeyElement': 'dogs'}],
                        'AttributesToGet': ['tags', HASH_KEY]}},
                'Responses': {
                    'thetablename': {
                        'Items': [
                            {
                                HASH_KEY: 'cats',
                                'filenames': '["deadbeef", "badcafe", "defec8"]'}],
                        'ConsumedCapacityUnits': 10.0}}}
        second_getitem = {
                'UnprocessedKeys': {},
                'Responses': {
                    'thetablename': {
                        'Items': [
                            {
                                HASH_KEY: 'dogs',
                                'filenames': '["5ca1ab1e", "deadbeef"]'}],
                        'ConsumedCapacityUnits': 10.0}}}
        dynamo.batch_get_item.side_effect = [first_getitem, second_getitem]
        mock_client.get_dynamodb.return_value = dynamo
        Client.return_value = mock_client
        batch_list = Mock()
        BatchList.return_value = batch_list

        tags = list(get_tags(['whatever']))
        eq_(tags, [
            {
                'tag': 'cats',
                'filenames': [ 'deadbeef', 'badcafe', 'defec8']},
            {
                'tag': 'dogs',
                'filenames': [ '5ca1ab1e', 'deadbeef']}])

    def test_get_tags__degenerate_case(self):
        eq_(list(get_tags([])), [])


    @patch('catsnap.batch.tag_batch.BatchWriteList')
    @patch('catsnap.batch.tag_batch.Client')
    @patch('catsnap.batch.tag_batch.get_tag_items')
    def test_add_image_to_tags(self, get_tag_items, Client, BatchWriteList):
        existing_tag_item = MagicMock()
        def existing_getitem(key):
            if key == 'filenames':
                return '["facade"]'
            elif key == HASH_KEY:
                return 'bleep'
            else:
                raise ValueError(key)
        existing_tag_item.__getitem__.side_effect = existing_getitem
        get_tag_items.return_value = [ existing_tag_item ]
        new_tag_item = MagicMock()
        new_tag_item.__getitem__.return_value = 'bloop'
        table = Mock()
        table.new_item.return_value = new_tag_item
        table.name = 'thetablename'
        client = Mock()
        client.table.return_value = table
        dynamo = Mock()
        client.get_dynamodb.return_value = dynamo
        Client.return_value = client
        write_list = Mock()
        first_response = {
                'UnprocessedItems': { 'thetablename': [
                        {'PutRequest': {
                            'Item': {
                                'tag': 'bloop',
                                'filenames': '["beefcafe"]'}}}]},
                'Responses': {'thetablename': {'ConsumedCapacityUnits': 5.0}}}
        second_response = {'Responses': {'thetablename':
                {'ConsumedCapacityUnits': 5.0}}}
        write_list.submit.side_effect = [first_response, second_response]
        BatchWriteList.return_value = write_list

        add_image_to_tags('beefcafe', ['bleep', 'bloop'])

        existing_tag_item.__setitem__.assert_called_with('filenames',
                '["facade", "beefcafe"]')
        get_tag_items.assert_called_with(['bleep', 'bloop'])
        table.new_item.assert_called_with(hash_key='bloop',
                attrs={'filenames':'["beefcafe"]'})
        BatchWriteList.assert_called_with(dynamo)
        write_list.add_batch.assert_has_calls([
                call(table, puts=[existing_tag_item, new_tag_item]),
                call(table, puts=[new_tag_item])])
        eq_(write_list.submit.call_count, 2)

    @patch('catsnap.batch.tag_batch.Client')
    @patch('catsnap.batch.tag_batch.BatchList')
    def test_get_tag_items__uniquifies_tags(self, BatchList, Client):
        client = Mock()
        client.get_dynamodb = MagicMock()
        Client.return_value = client

        batch_list = Mock()
        BatchList.return_value = batch_list
        table = client.table()

        #since get_tag_items is a generator, we need to force evaluation
        list(get_tag_items(['roadrunner', 'roadrunner']))
        batch_list.add_batch.assert_called_once_with(
                table, ['roadrunner'],
                attributes_to_get=['filenames', HASH_KEY])

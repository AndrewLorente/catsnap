from __future__ import unicode_literals

from tests import TestCase
import boto
from mock import patch, call, Mock
from nose.tools import eq_, assert_raises

from catsnap import Client

class TestSetup(TestCase):
    @patch('catsnap.MetaConfig')
    @patch('catsnap.Client.create_table')
    @patch('catsnap.boto')
    def test_creates_tables(self, mock_boto, create_table, MockMetaConfig):
        config = Mock(bucket='oodles', aws_access_key_id='foo',
                aws_secret_access_key='bar')
        MockMetaConfig.return_value = config
        client = Client()
        tables_created = client.setup()
        create_table.assert_has_calls([
            call('tag'),
            call('image')])
        eq_(tables_created, 2)

    @patch('catsnap.MetaConfig')
    @patch('catsnap.Client.create_table')
    @patch('catsnap.boto')
    def test_returns_number_of_new_tables(self, mock_boto, create_table, MockMetaConfig):
        config = Mock(bucket='oodles', aws_access_key_id='foo',
                aws_secret_access_key='bar')
        MockMetaConfig.return_value = config
        error = boto.exception.DynamoDBResponseError(400, 'table exists')
        error.error_code = 'ResourceInUseException'
        def do_create_table(table_name):
            if table_name == 'tag':
                return Mock()
            else:
                raise error
        create_table.side_effect = do_create_table

        client = Client()
        tables_created = client.setup()

        eq_(tables_created, 1)

    @patch('catsnap.MetaConfig')
    @patch('catsnap.boto')
    def test_creates_bucket(self, mock_boto, MockMetaConfig):
        config = Mock(bucket='oodles', aws_access_key_id='foo',
                aws_secret_access_key='bar')
        MockMetaConfig.return_value = config
        s3 = Mock()
        s3.get_all_buckets.return_value = []
        mock_boto.connect_s3.return_value = s3
        client = Client()
        client.setup()

        s3.create_bucket.assert_called_once_with('oodles')

    @patch('catsnap.MetaConfig')
    @patch('catsnap.boto')
    def test_failure_when_someone_else_has_that_bucket(self, mock_boto,
                                                       MockMetaConfig):
#        boto.exception.S3CreateError: S3CreateError: 409 Conflict
#<?xml version="1.0" encoding="UTF-8"?>
#<Error><Code>BucketAlreadyExists</Code><Message>The requested bucket name is not available. The bucket namespace is shared by all users of the system. Please select a different name and try again.</Message><BucketName>wp.patheos.com</BucketName><RequestId>3C6C1ED45C442F47</RequestId><HostId>J34v4gFkTThp5Gw1OpQzyWWnrc5hwfNL2DRUbk02Uqy3bd8euAYteVTJDIK2OLX1</HostId></Error>
        config = Mock(bucket='oodles', aws_access_key_id='foo',
                      aws_secret_access_key='bar')
        error = boto.exception.S3CreateError(409, 'Bucket exists')
        error.error_code = 'BucketAlreadyExists'
        s3 = Mock()
        s3.create_bucket.side_effect = error
        mock_boto.connect_s3.return_value = s3

        client = Client()

        with assert_raises(ValueError) as raise_manager:
            client.setup()
        eq_(unicode(raise_manager.exception),
                "It seems someone has already claimed your bucket name! "
                "You'll have to pick a new one with `catsnap config bucket`. "
                "Sorry about this; there's nothing I can do.")

class TestGetBucket(TestCase):
    @patch('catsnap.MetaConfig')
    @patch('catsnap.boto')
    def test_does_not_create_buckets(self, mock_boto, MockMetaConfig):
        config = Mock(bucket='oodles', aws_access_key_id='foo',
                aws_secret_access_key='bar')
        MockMetaConfig.return_value = config
        s3 = Mock()
        s3.get_all_buckets.return_value = []
        mock_boto.connect_s3.return_value = s3

        bucket = Client().bucket()
        eq_(s3.create_bucket.call_count, 0, "shouldn't've created a bucket")

    @patch('catsnap.MetaConfig')
    @patch('catsnap.boto')
    def test_get_bucket_is_memoized(self, mock_boto, MockMetaConfig):
        config = Mock(bucket='oodles', aws_access_key_id='foo',
                aws_secret_access_key='bar')
        MockMetaConfig.return_value = config
        mock_bucket = Mock()
        mock_bucket.name = 'oodles'
        s3 = Mock()
        s3.get_all_buckets.return_value = [ mock_bucket ]
        s3.get_bucket.side_effect = [ 1, 2 ]
        mock_boto.connect_s3.return_value = s3

        bucket1 = Client().bucket()
        bucket2 = Client().bucket()
        assert bucket1 is bucket2, 'multiple s3 connections were established'
        eq_(s3.get_bucket.call_count, 1)

class TestGetTable(TestCase):
    @patch('catsnap.MetaConfig')
    def test_memoization(self, MockMetaConfig):
        config = Mock(bucket='foo')
        MockMetaConfig.return_value = config
        client = Client()
        mock_table = Mock()
        client._dynamo_connection = Mock()
        client._dynamo_connection.get_table.return_value = mock_table

        table = client.table('tags')
        eq_(table, mock_table)
        eq_(client._dynamo_connection.get_table.call_count, 1)
        table = client.table('tags')
        eq_(client._dynamo_connection.get_table.call_count, 1)

class TestCreateTable(TestCase):
    @patch('catsnap.MetaConfig')
    @patch('catsnap.boto')
    def test_create_table(self, mock_boto, MockMetaConfig):
        config = Mock(bucket='myemmatable', aws_access_key_id='foo',
                aws_secret_access_key='bar')
        MockMetaConfig.return_value = config
        dynamo = Mock()
        mock_table = Mock()
        schema = Mock()
        dynamo.create_table.return_value = mock_table
        dynamo.create_schema.return_value = schema
        mock_boto.connect_dynamodb.return_value = dynamo

        table = Client().create_table('things')
        dynamo.create_schema.assert_called_with(
                hash_key_name='tag',
                hash_key_proto_value='S')
        dynamo.create_table.assert_called_with(name='myemmatable-things',
                schema=schema,
                read_units=3,
                write_units=5)
        eq_(table, mock_table)

class TestGetConnections(TestCase):
    @patch('catsnap.MetaConfig')
    @patch('catsnap.boto')
    def test_get_dynamodb(self, boto, MockMetaConfig):
        config = Mock(bucket='oodles', aws_access_key_id='foo',
                aws_secret_access_key='bar')
        MockMetaConfig.return_value = config
        Client().get_dynamodb()
        eq_(boto.connect_dynamodb.call_count, 1)

    @patch('catsnap.MetaConfig')
    @patch('catsnap.boto')
    def test_get_dynamodb__is_memoized(self, boto, MockMetaConfig):
        config = Mock(bucket='oodles', aws_access_key_id='foo',
                aws_secret_access_key='bar')
        MockMetaConfig.return_value = config
        boto.connect_dynamodb.side_effect = [1, 2]
        dynamo1 = Client().get_dynamodb()
        dynamo2 = Client().get_dynamodb()

        assert dynamo1 is dynamo2, 'different connections were established'
        eq_(boto.connect_dynamodb.call_count, 1)

    @patch('catsnap.MetaConfig')
    @patch('catsnap.boto')
    def test_get_s3(self, boto, MockMetaConfig):
        config = Mock(aws_access_key_id='itsme', aws_secret_access_key='letmein')
        MockMetaConfig.return_value = config
        Client().get_s3()
        boto.connect_s3.assert_called_once_with(
                aws_secret_access_key='letmein', aws_access_key_id='itsme')


    @patch('catsnap.MetaConfig')
    @patch('catsnap.boto')
    def test_get_s3__is_memoized(self, boto, MockMetaConfig):
        config = Mock(aws_access_key_id='itsme', aws_secret_access_key='letmein')
        MockMetaConfig.return_value = config
        boto.connect_dynamodb.side_effect = [1, 2]
        sss1 = Client().get_s3()
        sss2 = Client().get_s3()

        assert sss1 is sss2, 'different connections were established'
        eq_(boto.connect_s3.call_count, 1)


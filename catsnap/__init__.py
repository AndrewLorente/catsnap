from __future__ import unicode_literals
import boto

from catsnap.config import MetaConfig
from catsnap.singleton import Singleton
from boto.exception import DynamoDBResponseError, S3CreateError

#This really oughtta be, like, the tablename or something, but I screwed up, so
#now there're existing catsnap installs that use this schema. Sucks :(
#So yeah every table is keyed on an attribute called 'tag'
HASH_KEY = 'tag'

class Client(Singleton):
    _tables = {}
    _bucket = None

    _dynamo_connection = None
    _s3_connection = None

    def setup(self):

        bucket_name = MetaConfig().bucket
        s3 = self.get_s3()
        
        try: 
            s3.create_bucket(bucket_name)
        except S3CreateError:
            raise ValueError("It seems someone has already claimed your bucket name!"
             " You'll have to pick a new one with `catsnap config bucket`." 
             " Sorry about this; there's nothing I can do.")

        created_tables = 0
        try:
            self.create_table('tag')
            created_tables += 1
        except DynamoDBResponseError, e:
            if e.error_code != 'ResourceInUseException':
                raise
        try:
            self.create_table('image')
            created_tables += 1
        except DynamoDBResponseError, e:
            if e.error_code != 'ResourceInUseException':
                raise

        return created_tables

    def bucket(self):
        if not self._bucket:
            s3 = self.get_s3()
            bucket_name = MetaConfig().bucket
            self._bucket = s3.get_bucket(bucket_name)
        return self._bucket


    def create_table(self, table_name):
        table_prefix = MetaConfig().bucket
        table_name = '%s-%s' % (table_prefix, table_name)

        dynamo = self.get_dynamodb()
        schema = dynamo.create_schema(hash_key_name='tag',
                hash_key_proto_value='S')
        return dynamo.create_table(name=table_name,
                schema=schema,
                read_units=3,
                write_units=5)

    def table(self, table_name):
        table_prefix = MetaConfig().bucket
        table_name = '%s-%s' % (table_prefix, table_name)

        if table_name not in self._tables:
            dynamo = self.get_dynamodb()
            self._tables[table_name] = dynamo.get_table(table_name)
        return self._tables[table_name]

    def get_dynamodb(self):
        if not self._dynamo_connection:
            self._dynamo_connection = boto.connect_dynamodb(
                    aws_access_key_id=MetaConfig().aws_access_key_id,
                    aws_secret_access_key=MetaConfig().aws_secret_access_key)
        return self._dynamo_connection

    def get_s3(self):
        if not self._s3_connection:
            self._s3_connection = boto.connect_s3(
                    aws_access_key_id=MetaConfig().aws_access_key_id,
                    aws_secret_access_key=MetaConfig().aws_secret_access_key)
        return self._s3_connection


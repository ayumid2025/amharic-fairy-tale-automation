import os
import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client(
    's3',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)

def upload_to_s3(file_path, bucket_name, object_name=None):
    if object_name is None:
        object_name = os.path.basename(file_path)
    try:
        s3_client.upload_file(file_path, bucket_name, object_name)
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=3600
        )
        return url
    except ClientError as e:
        print(e)
        return None

def upload_fileobj_to_s3(file_obj, bucket_name, object_name, content_type=None):
    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type
    try:
        s3_client.upload_fileobj(file_obj, bucket_name, object_name, ExtraArgs=extra_args)
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=3600
        )
        return url
    except ClientError as e:
        print(e)
        return None

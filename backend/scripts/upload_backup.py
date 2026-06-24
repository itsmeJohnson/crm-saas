import os
import sys
import boto3
from botocore.exceptions import ClientError

def upload_backup():
    if len(sys.argv) < 2:
        print("Usage: upload_backup.py <filepath>")
        sys.exit(1)
        
    filepath = sys.argv[1]
    filename = os.path.basename(filepath)
    
    # Read environment variables
    spaces_key = os.environ.get("SPACES_KEY")
    spaces_secret = os.environ.get("SPACES_SECRET")
    spaces_endpoint = os.environ.get("SPACES_ENDPOINT")
    spaces_bucket = os.environ.get("SPACES_BUCKET")
    
    if not (spaces_key and spaces_secret and spaces_endpoint and spaces_bucket):
        print("DO Spaces environment variables (SPACES_KEY, SPACES_SECRET, SPACES_ENDPOINT, SPACES_BUCKET) are not fully configured. Skipping upload to remote space.")
        sys.exit(0)
        
    print(f"Uploading {filename} to DigitalOcean Space {spaces_bucket}...")
    
    try:
        session = boto3.session.Session()
        client = session.client(
            's3',
            region_name='nyc3',
            endpoint_url=spaces_endpoint,
            aws_access_key_id=spaces_key,
            aws_secret_access_key=spaces_secret
        )
        
        # Upload
        client.upload_file(
            Filename=filepath,
            Bucket=spaces_bucket,
            Key=f"backups/{filename}"
        )
        print("Upload successful!")
        
        # Backup rotation rules: delete backups in DO Spaces older than 30 days
        print("Evaluating remote backups rotation rules (retention limit: 30 days)...")
        response = client.list_objects_v2(Bucket=spaces_bucket, Prefix="backups/")
        if 'Contents' in response:
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            retention_limit = now - timedelta(days=30)
            
            for obj in response['Contents']:
                last_modified = obj['LastModified']
                if last_modified.tzinfo is None:
                    last_modified = last_modified.replace(tzinfo=timezone.utc)
                if last_modified < retention_limit:
                    key = obj['Key']
                    print(f"Rotating/Deleting old remote backup: {key} (LastModified: {last_modified})")
                    client.delete_object(Bucket=spaces_bucket, Key=key)
            print("Remote backup rotation completed.")
                    
    except Exception as e:
        print(f"Error during backup upload/rotation: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    upload_backup()

from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path

import boto3
from botocore.client import Config


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / "data-pipeline" / "data" / "processed"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish processed KOLTrust data to MinIO/S3.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--bucket", default="koltrust-processed")
    parser.add_argument("--prefix", default="processed")
    parser.add_argument("--endpoint-url", default="http://localhost:9000")
    parser.add_argument("--access-key", default="minioadmin")
    parser.add_argument("--secret-key", default="minioadmin")
    return parser.parse_args()


def content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def main() -> int:
    args = parse_args()
    source = Path(args.source)
    if not source.exists():
        raise SystemExit(f"Source path not found: {source}")

    client = boto3.client(
        "s3",
        endpoint_url=args.endpoint_url,
        aws_access_key_id=args.access_key,
        aws_secret_access_key=args.secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )

    buckets = {bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])}
    if args.bucket not in buckets:
        client.create_bucket(Bucket=args.bucket)

    uploaded = 0
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        key = f"{args.prefix.rstrip('/')}/{path.relative_to(source).as_posix()}"
        client.upload_file(
            str(path),
            args.bucket,
            key,
            ExtraArgs={"ContentType": content_type(path)},
        )
        uploaded += 1
        print(f"s3://{args.bucket}/{key}")

    print(f"Uploaded {uploaded} files from {source} to {args.endpoint_url}/{args.bucket}/{args.prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

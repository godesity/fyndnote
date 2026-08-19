import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class S3BackedCache:
    """Two-tier cache: local SSD for hot datasets, S3 for cold storage.

    Files are mirrored directly on S3 preserving their relative paths under
    ``{prefix}/{ds_id}/`` — no tar/archive layer.

    Local cache files are never deleted unless verified on S3 first.
    """

    def __init__(self, bucket: str, prefix: str = "datasets-cache", endpoint_url: str | None = None):
        self.bucket = bucket
        self.prefix = prefix
        self.endpoint_url = endpoint_url
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._s3 = None

    @property
    def _client(self):
        if self._s3 is None:
            import boto3
            kwargs = {}
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            self._s3 = boto3.client("s3", **kwargs)
        return self._s3

    def _object_key(self, ds_id: str, relative: str) -> str:
        return f"{self.prefix}/{ds_id}/{relative}"

    def _ds_prefix(self, ds_id: str) -> str:
        return f"{self.prefix}/{ds_id}/"

    def upload(self, ds_id: str, local_path: Path) -> None:
        """Upload every file under *local_path* to ``s3://bucket/prefix/{ds_id}/``.

        Safe to call from a background thread.
        """
        if not local_path.is_dir():
            return
        files = [p for p in local_path.rglob("*") if p.is_file()]
        if not files:
            return
        for f in files:
            relative = str(f.relative_to(local_path))
            key = self._object_key(ds_id, relative)
            try:
                self._client.upload_file(str(f), self.bucket, key)
            except Exception:
                logger.exception("Failed to upload %s to s3://%s/%s", relative, self.bucket, key)
                raise
        logger.info("Uploaded %d files for %s to s3://%s/%s", len(files), ds_id, self.bucket, self._ds_prefix(ds_id))

    def upload_async(self, ds_id: str, local_path: Path):
        """Dispatch upload to background thread. Returns ``Future``."""
        return self._executor.submit(self.upload, ds_id, local_path)

    def download(self, ds_id: str, local_path: Path) -> bool:
        """Download all cached files for *ds_id* from S3.

        Files are restored under *local_path* preserving their relative paths.
        Returns ``True`` if any files were restored, ``False`` if nothing on S3.
        """
        local_path.mkdir(parents=True, exist_ok=True)
        prefix = self._ds_prefix(ds_id)
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)
            restored = 0
            for page in pages:
                for obj in page.get("Contents", []):
                    relative = obj["Key"][len(prefix):]
                    if not relative:
                        continue
                    dest = local_path / relative
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    self._client.download_file(self.bucket, obj["Key"], str(dest))
                    restored += 1
        except Exception:
            logger.exception("Failed to download cache for %s", ds_id)
            return False
        if restored:
            logger.info("Restored %d files for %s from s3://%s/%s", restored, ds_id, self.bucket, prefix)
            return True
        return False

    def exists(self, ds_id: str) -> bool:
        """Check whether any cached files exist on S3 for this dataset."""
        try:
            resp = self._client.list_objects_v2(
                Bucket=self.bucket, Prefix=self._ds_prefix(ds_id), MaxKeys=1
            )
            return resp.get("KeyCount", 0) > 0
        except Exception:
            return False

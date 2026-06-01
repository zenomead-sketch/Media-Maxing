# Media Library

The Media Library stores user-selected photos and videos locally. No media is
uploaded to a cloud service.

## Browser Import

Run the localhost bridge:

```text
python -m apps.api.local_server --database data/app.sqlite --port 8000
```

Open `http://127.0.0.1:8000/#media`, choose **Import media**, and select an
image or video. The browser posts the file bytes only to the loopback server.
The server:

1. Validates that the original filename is safe.
2. Accepts supported image or video extensions only.
3. Rejects empty files and files larger than 100 MB.
4. Generates an internal filename.
5. Writes the original under `data/media/originals`.
6. Creates the matching `media_assets` row in SQLite.

The `data/media` tree is ignored by Git.

## Direct-File Fallback

Opening `apps/web/index.html` directly keeps a metadata-only browser demo.
That fallback is useful for static inspection, but it does not copy selected
files into durable local app storage.

## Current Limits

- Validation is intentionally basic: extension, inferred MIME family, size,
  safe filename, and safe destination checks.
- Thumbnail generation and video processing are not implemented yet.
- Packaged desktop file-picker hardening remains future work.

# app

`v1/app/` is the legacy v1 application area.

- `v1/app/main.py`: v1 PDF-to-audio FastAPI service.
- v2 does not live in this folder anymore.

Run v1 only when the required cloud/API environment variables are configured:

```bash
uvicorn v1.app.main:app
```

Run the v2 local demo from `v2/main.py` instead:

```bash
uvicorn v2.main:app --reload --port 8000
```


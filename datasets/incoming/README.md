# Drop CCTV footage here

Put the video files you want the platform to process in this folder, then run:

```bash
# Validate only (writes datasets/manifests/prepared.json)
python scripts/prepare_dataset.py --input datasets/incoming

# Validate, upload and wait for the AI job
DEMO_SEED_PASSWORD=... python scripts/prepare_dataset.py \
  --input datasets/incoming --upload \
  --api-url http://localhost:8000 --email ops@demo.roadguard.ai --wait-seconds 300
```

Accepted: `.mp4`, `.mov`, `.mkv`, `.webm`. Default limits: 200 MB and 600 s per file,
3840×2160. The script hashes every clip (SHA-256), rejects anything the API would
reject, and writes a provenance manifest.

For each junction, also send (in the ticket or a sidecar note, not in this folder):

- camera code and name, junction/road name
- latitude and longitude (or a surveyed point)
- recording date and time with timezone
- which direction of travel the camera faces
- owner of the footage and the legal basis for processing it
- whether faces/plates must be blurred and the retention period

Read `docs/DATASETS.md` first: no public Indian municipal CCTV accident corpus exists,
so real footage has to come from the city. The default detector is tuned for the
synthetic demo clip, not for real footage.

FROM python:3.12-slim

# Hugging Face Spaces requires running as non-root UID 1000
RUN useradd -m -u 1000 user

WORKDIR /app

COPY --chown=user:user src ./src
COPY --chown=user:user scripts ./scripts
COPY --chown=user:user data/medicine_catalog.json ./data/medicine_catalog.json
COPY --chown=user:user data/chronic_baskets.json ./data/chronic_baskets.json

USER user

# Download & compile the full ~253k A-Z Indian Medicines SQLite+FTS5 catalog at image build time
RUN python scripts/ingest_az_dataset.py --download && rm -rf data/raw

ENV PORT=7860 PYTHONUNBUFFERED=1
EXPOSE 7860

CMD ["python", "-u", "-m", "src.server"]

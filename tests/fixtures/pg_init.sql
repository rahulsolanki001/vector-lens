CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    embedding vector(3) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb
);

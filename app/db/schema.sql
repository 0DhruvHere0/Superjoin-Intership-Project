CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    uploaded_at TEXT NOT NULL,
    num_pages INTEGER,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'extracting', 'done', 'error'))
);
CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    quote TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value TEXT NOT NULL,
    unit TEXT,
    time_scope TEXT,
    raw_statement TEXT NOT NULL,
    confidence REAL NOT NULL
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    embed_key TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (doc_id)
        REFERENCES documents(id)
        ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS relations (
    id TEXT PRIMARY KEY,
    fact_a_id TEXT NOT NULL,
    fact_b_id TEXT NOT NULL,
    relationship TEXT NOT NULL
        CHECK (
            relationship IN (
                'corroborate',
                'contradict',
                'reconcile',
                'unrelated'
            )
        ),
    explanation TEXT NOT NULL,
    similarity REAL NOT NULL
        CHECK (similarity >= -1.0 AND similarity <= 1.0),
    created_at TEXT NOT NULL,
    CHECK (fact_a_id <> fact_b_id),
    FOREIGN KEY (fact_a_id)
        REFERENCES facts(id)
        ON DELETE CASCADE,
    FOREIGN KEY (fact_b_id)
        REFERENCES facts(id)
        ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS extraction_issues (
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    page INTEGER,
    issue_type TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (doc_id)
        REFERENCES documents(id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_facts_doc_id
    ON facts(doc_id);

CREATE INDEX IF NOT EXISTS idx_relations_fact_a_id
    ON relations(fact_a_id);

CREATE INDEX IF NOT EXISTS idx_relations_fact_b_id
    ON relations(fact_b_id);

CREATE INDEX IF NOT EXISTS idx_extraction_issues_doc_id
    ON extraction_issues(doc_id);
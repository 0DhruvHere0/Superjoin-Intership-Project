const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("pdf-file");
const message = document.getElementById("message");
const documentList = document.getElementById("document-list");
const documentDetail = document.getElementById("document-detail");
function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
function showMessage(text) {
    message.hidden = false;
    message.textContent = text;
}
function formatStatus(status) {
    const value = String(status || "");

    return value.charAt(0).toUpperCase() + value.slice(1);
}
function formatPages(record) {
    if (!record.num_pages) {
        return "Pages not available";
    }
    return `${record.num_pages} page(s)`;
}
function renderDocuments(records) {
    documentList.innerHTML = "";
    if (!records.length) {
        documentList.innerHTML = `
            <p class="empty">
                No documents uploaded yet.
            </p>
        `;
        return;
    }
    records.forEach((record) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "document-button";
        button.dataset.documentId = record.id;
        button.innerHTML = `
            <span class="document-name">
                ${escapeHtml(record.filename)}
            </span>
            <span class="document-status">
                ${escapeHtml(formatStatus(record.status))}
            </span>
        `;
        button.addEventListener("click", () => {
            loadDocument(record.id);
        });
        documentList.appendChild(button);
    });
}
function renderFacts(facts) {
    if (!facts.length) {
        return `
            <p class="empty">
                No valid facts were stored.
            </p>
        `;
    }
    return facts.map((fact) => {
        const pageLabel = fact.page_start === fact.page_end
            ? `Page ${fact.page_start}`
            : `Pages ${fact.page_start}-${fact.page_end}`;
        const value = fact.unit
            ? `${fact.value} ${fact.unit}`
            : fact.value;
        return `
            <article class="fact">
                <div class="fact-header">
                    <div>
                        <div class="label">
                            ${escapeHtml(fact.subject)}
                        </div>
                        <h3>
                            ${escapeHtml(fact.predicate)}
                        </h3>
                    </div>
                    <div class="fact-value">
                        ${escapeHtml(value)}
                    </div>
                </div>
                <p>
                    <strong>Time scope:</strong>
                    ${escapeHtml(
                        fact.time_scope || "Not specified"
                    )}
                </p>
                <p>
                    <strong>Confidence:</strong>
                    ${escapeHtml(
                        Number(fact.confidence).toFixed(2)
                    )}
                </p>
                <p>
                    <strong>Source:</strong>
                    ${escapeHtml(pageLabel)}
                </p>
                <p>
                    <strong>Statement:</strong>
                    ${escapeHtml(fact.raw_statement)}
                </p>
                <p class="quote">
                    “${escapeHtml(fact.quote)}”
                </p>
            </article>
        `;
    }).join("");
}
function renderRelations(relations) {
    const meaningfulRelations = relations.filter(
        (relation) => relation.relationship !== "unrelated"
    );
    if (!meaningfulRelations.length) {
        return `
            <p class="empty">
                No meaningful relationships found yet.
            </p>
        `;
    }
    return meaningfulRelations.map((relation) => `
        <article class="relation">
            <div class="relation-header">
                <strong>
                    ${escapeHtml(relation.fact_a_id)}
                    ↔
                    ${escapeHtml(relation.fact_b_id)}
                </strong>
                <span class="badge badge-${escapeHtml(
                    relation.relationship
                )}">
                    ${escapeHtml(relation.relationship)}
                </span>
            </div>
            <p>
                <strong>Similarity:</strong>
                ${escapeHtml(
                    Number(relation.similarity).toFixed(4)
                )}
            </p>
            <p>
                ${escapeHtml(relation.explanation)}
            </p>
        </article>
    `).join("");
}
function renderIssues(issues) {
    if (!issues.length) {
        return `
            <p class="empty">
                No processing issues recorded.
            </p>
        `;
    }
    return issues.map((issue) => `
        <article class="issue">
            <strong>
                ${escapeHtml(issue.issue_type)}
            </strong>
            <p>
                ${escapeHtml(issue.detail)}
            </p>
            <span class="label">
                ${
                    issue.page
                        ? `Page ${escapeHtml(issue.page)}`
                        : "Document-level issue"
                }
            </span>
        </article>
    `).join("");
}
function renderDocument(record) {
    documentDetail.innerHTML = `
        <h2>${escapeHtml(record.filename)}</h2>
        <p>
            <strong>Status:</strong>
            ${escapeHtml(formatStatus(record.status))}
        </p>
        <p>
            <strong>Pages:</strong>
            ${escapeHtml(formatPages(record))}
        </p>
        <section class="section">
            <h2>Facts</h2>
            ${renderFacts(record.facts || [])}
        </section>
        <section class="section">
            <h2>Relationships</h2>
            ${renderRelations(record.relations || [])}
        </section>
        <section class="section">
            <h2>Processing Issues</h2>
            ${renderIssues(record.issues || [])}
        </section>
    `;
}
async function loadDocuments() {
    const response = await fetch("/documents");
    if (!response.ok) {
        throw new Error("Could not load documents.");
    }
    const records = await response.json();
    renderDocuments(records);
}
async function loadDocument(documentId) {
    const response = await fetch(
        `/documents/${encodeURIComponent(documentId)}`
    );
    if (!response.ok) {
        throw new Error("Could not load document details.");
    }
    const record = await response.json();
    renderDocument(record);
}
function wait(milliseconds) {
    return new Promise((resolve) => {
        setTimeout(resolve, milliseconds);
    });
}
async function waitForProcessing(documentId) {
    for (let attempt = 0; attempt < 90; attempt += 1) {
        const response = await fetch(
            `/documents/${encodeURIComponent(documentId)}`
        );
        if (!response.ok) {
            throw new Error(
                "Could not check document status."
            );
        }
        const record = await response.json();
        renderDocument(record);
        if (
            record.status === "done"
            || record.status === "error"
        ) {
            await loadDocuments();
            return;
        }
        await wait(2000);
    }
    showMessage(
        "The document is still processing. Refresh later to view the result."
    );
}
uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file) {
        showMessage("Please select a PDF first.");
        return;
    }
    const formData = new FormData();
    formData.append("file", file);
    try {
        showMessage("Uploading PDF...");
        const response = await fetch(
            "/upload",
            {
                method: "POST",
                body: formData,
            }
        );
        const result = await response.json();
        if (!response.ok) {
            throw new Error(
                result.detail || "Upload failed."
            );
        }
        fileInput.value = "";
        if (result.duplicate) {
            showMessage(
                "This PDF was already uploaded. Loading existing results."
            );
        } else {
            showMessage(
                "Upload accepted. Processing has started."
            );
        }
        await loadDocuments();
        await waitForProcessing(result.document_id);
    } catch (error) {
        showMessage(error.message);
    }
});
async function initializePage() {
    try {
        await loadDocuments();
    } catch (error) {
        showMessage(error.message);
    }
}
initializePage();
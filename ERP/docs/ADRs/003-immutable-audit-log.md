# ADR 003: Immutable Audit Log

**Status:** Proposed

**Context:**

For Sarbanes-Oxley (SOX) compliance and general data integrity, all changes to journal entries must be logged in a way that is both tamper-evident and immutable. This requires a system that can record every change (create, update, delete) to a journal entry, including the before and after values of each field, the user who made the change, and the timestamp. The integrity of the log itself must be cryptographically verifiable.

**Decision:**

We will implement an immutable audit log system using a hash chain. Each new audit log entry will be cryptographically linked to the previous entry, creating a verifiable chain of events.

*   **Data Structure:** Each audit log entry will be a JSON object containing:
    *   `log_id`: A unique identifier for the log entry.
    *   `timestamp`: The UTC timestamp of the event.
    *   `user_id`: The identifier of the user who performed the action.
    *   `action`: The type of action (e.g., `CREATE_JOURNAL`, `UPDATE_LINE`, `DELETE_LINE`).
    *   `entity_id`: The ID of the journal or journal line being modified.
    *   `before_state`: A JSON object representing the state of the data *before* the change.
    *   `after_state`: A JSON object representing the state of the data *after* the change.
    *   `previous_hash`: The SHA-256 hash of the preceding log entry in the chain.
    *   `current_hash`: The SHA-256 hash of the current log entry (calculated over all other fields in the entry, including `previous_hash`).

*   **Storage:** The audit log will be stored in a dedicated, append-only data store. A relational database table with strict permissions (allowing only inserts) or a specialized immutable ledger database (like Amazon QLDB, or a custom solution built on a standard database) will be used.

*   **Verification:** A separate process or tool will be created to verify the integrity of the hash chain. This tool will iterate through the log entries, recalculate the hash of each entry, and compare it to the stored `current_hash` and the `previous_hash` of the next entry. Any mismatch would indicate tampering.

**Consequences:**

*   **Pros:**
    *   **SOX Compliance:** Provides a strong, verifiable audit trail that meets regulatory requirements.
    *   **Data Integrity:** The hash chain makes it computationally infeasible to alter or delete log entries without detection.
    *   **Clear Audit Trail:** Creates a detailed and unambiguous history of all changes, which is invaluable for forensic analysis and debugging.

*   **Cons:**
    *   **Storage Growth:** The audit log can grow very large, especially for a high-volume system. This will require a robust data management and archiving strategy.
    *   **Performance Overhead:** Calculating hashes and writing to an append-only log for every change introduces a small performance overhead to the transaction processing. This must be carefully benchmarked.
    *   **Complexity:** Implementing and managing a hash-chained log is more complex than a simple logging table. The verification process adds another operational requirement.
    *   **No Deletions:** By design, data cannot be corrected or removed from the audit log. Any "correction" must be logged as a new, compensating entry, which can complicate analysis if not handled carefully.
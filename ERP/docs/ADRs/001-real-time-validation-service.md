# ADR 001: Real-time Validation Service

**Status:** Proposed

**Context:**

The journal entry screen requires immediate feedback to users to prevent errors and ensure data quality. Traditional batch validation after form submission leads to a poor user experience and slower data entry. A real-time, keystroke-level validation mechanism is needed to check journal lines against the ERP's complex posting logic as the user types. The validation must be fast enough to feel instantaneous, with a target round-trip latency of less than 30 milliseconds on a local area network (LAN).

**Decision:**

We will implement a stateless REST microservice dedicated to real-time validation. This service will expose a single endpoint (e.g., `/validate-line`) that accepts a journal entry line and returns validation status and error messages.

*   **Technology Stack:** The service will be built using a high-performance framework suitable for I/O-bound tasks, such as Python with FastAPI or Node.js with Express.
*   **Stateless Architecture:** The service will be stateless. Each validation request will contain all necessary information, allowing for horizontal scaling and high availability. The service will not maintain any session state between requests.
*   **Deployment:** The service will be containerized using Docker and deployed on a Kubernetes cluster, allowing for easy scaling and management.
*   **Communication:** The frontend (AG-Grid) will communicate with this service asynchronously. A debounce mechanism will be implemented on the client-side to send validation requests only when the user pauses typing, optimizing network traffic.

**Consequences:**

*   **Pros:**
    *   **Improved User Experience:** Users receive instant feedback, reducing errors and improving data entry speed.
    *   **Decoupled Architecture:** The validation logic is decoupled from the main ERP monolith, allowing for independent development, deployment, and scaling.
    *   **High Performance:** A dedicated, lightweight microservice can be optimized to meet the strict <30ms latency requirement.
    *   **Scalability:** The stateless nature allows the service to be scaled horizontally to handle high loads.

*   **Cons:**
    *   **Increased Complexity:** Introduces another service to the architecture that needs to be maintained, monitored, and deployed.
    *   **Network Overhead:** Relies on network communication, which could be a point of failure. The <30ms requirement necessitates a stable and fast LAN.
    *   **Data Consistency:** The validation service will need access to the same business logic and data as the main ERP. Keeping this logic synchronized can be a challenge. A shared library or data replication strategy might be needed.
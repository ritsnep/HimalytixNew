# ADR 002: AI Assistance Module

**Status:** Proposed

**Context:**

To enhance user productivity and reduce manual data entry errors, the journal entry module requires AI-powered assistance. Two key features are required:
1.  **Natural Language to Account Mapping:** Users should be able to describe a transaction in natural language (e.g., "Accrue March AWS bill"), and the system should suggest the correct GL account code (e.g., `6150-02-AWS`).
2.  **Anomaly Explanation:** The system should be able to analyze a completed journal entry, identify potential anomalies (e.g., unusual account combinations, deviations from historical patterns), and provide a clear explanation of the issue.

A key constraint is the requirement to use a locally-hosted, fine-tuned Gemini API to ensure data privacy and control over the model.

**Decision:**

We will create a dedicated AI Assistance microservice. This service will host the fine-tuned Gemini model and expose two RESTful endpoints:

*   `/suggest`: This endpoint will take a natural language string as input and return a list of suggested account codes with confidence scores.
    *   **Input:** `{ "query": "Accrue March AWS bill" }`
    *   **Output:** `[{ "account_code": "6150-02-AWS", "confidence": 0.95 }, ...]`
*   `/explain`: This endpoint will take a full journal entry (e.g., in JSON format) as input and return a list of detected anomalies with human-readable explanations.
    *   **Input:** `{ "journal_lines": [...] }`
    *   **Output:** `[{ "anomaly_type": "Unusual_Account_Pair", "explanation": "Account 6150-02-AWS is rarely used with department 700." }]`

**Technology Stack:**
*   **Model:** A fine-tuned version of the Gemini model, hosted locally. The fine-tuning process will involve training the model on the company's historical journal entry data and chart of accounts.
*   **Service:** A Python-based service using a framework like FastAPI or Flask to wrap the model and expose the REST API.
*   **Deployment:** The service will be containerized using Docker and deployed on a dedicated GPU-enabled node within the on-premise Kubernetes cluster to meet the computational demands of the AI model.

**Consequences:**

*   **Pros:**
    *   **Enhanced User Experience:** Simplifies the journal entry process, making it faster and more intuitive.
    *   **Improved Accuracy:** Reduces the likelihood of misclassifying transactions.
    *   **Proactive Error Detection:** The `/explain` endpoint helps catch errors and compliance issues before posting.
    *   **Data Privacy:** Using a local Gemini instance keeps sensitive financial data within the company's infrastructure.

*   **Cons:**
    *   **Infrastructure Cost:** Requires dedicated hardware (GPU servers) to run the local AI model, which can be expensive.
    *   **Model Maintenance:** The fine-tuned model will require ongoing maintenance, monitoring, and retraining as the business and chart of accounts evolve.
    *   **Expertise:** Requires specialized expertise in machine learning and MLOps to build, deploy, and maintain the service.
    *   **Latency:** AI model inference can be slow. The service needs to be carefully optimized to provide responses in a timely manner, though it is not subject to the same sub-30ms constraint as the validation service.
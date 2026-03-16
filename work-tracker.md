# NetBox WAN IP Automation & CI Integration

## Epic Overview

**Goal**

Automate ingestion, validation, reconciliation, and lifecycle management of WAN IP data in NetBox using Git-based workflows and Jenkins CI pipelines.

**Key Outcomes**

* Git-driven infrastructure data management
* Automated NetBox reconciliation pipelines
* Structured artifact storage and traceability
* Automated cleanup and retention management
* Secure credential handling across integrations

---

# Story 1 — Git-based WAN IP Data Source

**Objective**

Establish Git as the authoritative source for WAN IP configuration data.

### Tasks

* Define `wan_ips.json` schema and repository structure
* Implement validation for WAN IP records
* Implement change detection for pipeline triggers
* Document Git workflow (branching, PR expectations)

---

# Story 2 — Jenkins CI Pipeline Integration

**Objective**

Automate NetBox reconciliation through Jenkins pipelines triggered by Git commits.

### Tasks

* Create Jenkins multibranch pipeline
* Implement stage execution logic using `when` conditions
* Configure **Basic Branch Build Strategies plugin** to monitor `main`
* Ensure pipeline executes reconciliation only for relevant data changes

---

# Story 3 — NetBox Reconciliation Automation

**Objective**

Synchronize Git WAN IP data with NetBox using automated reconciliation logic.

### Tasks

* Implement NetBox API client wrapper
* Develop reconciliation logic (create / update / remove records)
* Implement reconciliation cases and validation checks
* Generate structured JSON artifacts for reconciliation results

---

# Story 4 — Artifact Management & Storage

**Objective**

Store pipeline artifacts outside Jenkins for long-term traceability.

### Tasks

* Generate structured artifact output (JSON)
* Offload artifacts to SMB storage
* Organize artifacts by job / branch / run ID
* Secure SMB access using Jenkins credentials

**Example Layout**

```
netbox/
  Netbox_Git_WAN_IP_Reconcilation_Auto/
    main/
      26/
        artifacts.json
```

---

# Story 5 — Artifact Retention & Maintenance

**Objective**

Prevent uncontrolled artifact growth on shared storage.

### Tasks

* Develop SMB maintenance script for artifact pruning
* Implement retention policy (keep newest N runs)
* Support both job and job/branch layouts
* Integrate maintenance script into Jenkins pipeline

---

# Story 6 — Scheduled Cleanup Automation

**Objective**

Automate removal of stale or obsolete NetBox WAN IP records.

### Tasks

* Develop cleanup pipeline logic
* Detect obsolete WAN IP entries
* Generate cleanup logs and artifacts
* Schedule weekly Jenkins execution

---

# Story 7 — CI Observability & Traceability

**Objective**

Ensure pipeline execution is transparent and traceable.

### Tasks

* Standardize artifact naming conventions
* Implement structured logging across pipelines
* Improve pipeline stage visibility and debugging

Example artifact naming:

```
<buildID>_<timestamp>_case_1_artifacts.json
```

---

# Story 8 — Security & Credential Management

**Objective**

Secure all platform integrations and remove plaintext credentials.

### Tasks

* Configure Jenkins credential store for integrations
* Remove plaintext credential files from scripts
* Inject credentials into pipelines securely

---

# Story 9 — Documentation & Operational Runbooks

**Objective**

Provide documentation for maintainability and operational support.

### Tasks

* Document system architecture and workflow
* Document artifact storage design
* Create troubleshooting runbooks for pipelines and integrations

---

# Story 10 — WAN IP Data Aggregation App Refactor (Meraki + Aruba → Git)

**Objective**

Refactor the existing WAN IP data aggregation application so it can run securely in Jenkins, collect WAN IP data from **Meraki and Aruba**, and generate a consolidated dataset for the Git source of truth.

### Tasks

* Refactor application into a CI-compatible CLI tool
* Implement secure credential handling via Jenkins
* Extend Meraki data collection to include **organization name**
* Validate and align Aruba data collection with unified schema
* Consolidate platform data into a single `wan_ips.json`
* Implement automated Git commit logic for dataset updates
* Integrate the application into Jenkins pipeline execution
* Add structured logging and execution summaries

---
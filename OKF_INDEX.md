# OKF Index — Google Open Knowledge Format repositories

Curated list of Google Open Knowledge Format (OKF) repositories and tools used
to work with the SII knowledge base in this repository.

## Official Google repositories

| Repository | Description |
| --- | --- |
| [GoogleCloudPlatform/open-knowledge-format](https://github.com/GoogleCloudPlatform/open-knowledge-format) | OKF specification (v0.1 / v0.2) source of truth |
| [GoogleCloudPlatform/knowledge-catalog](https://github.com/GoogleCloudPlatform/knowledge-catalog) | Google's reference implementation and public dataset bundles (OKF) |
| [GoogleCloudPlatform/knowledge-catalog/okf/SPEC.md](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) | OKF spec document |

## Official Google OKF bundles

| Bundle | Description |
| --- | --- |
| [Google Knowledge Catalog (OKF Reference)](https://bundledex.net/bundles/google-knowledge-catalog) | Official GCP reference implementation of OKF |
| [Bitcoin Blockchain Bundle](https://bundledex.net/bundles/crypto-bitcoin-bundle) | Google's OKF bundle for the Bitcoin Blockchain dataset |
| [GA4 E-Commerce Dataset](https://bundledex.net/bundles/ga4-ecommerce-bundle) | Google's OKF bundle for GA4 e-commerce |
| [Stack Overflow Public Dataset](https://bundledex.net/bundles/stackoverflow-dataset-bundle) | Google's OKF bundle for the Stack Overflow dataset |

## Tools

| Tool | Link |
| --- | --- |
| BundleDex (directory of 240+ OKF bundles) | [bundledex.net](https://bundledex.net) |
| BundleDex API (agent-friendly JSON index) | [bundledex.net/api/bundles.json](https://bundledex.net/api/bundles.json) |
| Open Knowledge CLI | [github.com/openknowledge-sh/openknowledge](https://github.com/openknowledge-sh/openknowledge) |
| OKFy (convert docs to OKF bundles) | [github.com/0dust/OKFy](https://github.com/0dust/OKFy) |
| OKF Skill Toolkit (validate/query/lint/create) | [github.com/ifuture-pro/okf-skill-toolkit](https://github.com/ifuture-pro/okf-skill-toolkit) |
| OKF Go Parser / validator | [github.com/dogmatiq/okf](https://github.com/dogmatiq/okf) |
| okf-lint | [github.com/thisismydesign/okf-lint](https://github.com/thisismydesign/okf-lint) |
| awesome-okf (curated list) | [github.com/McClawdDigital/awesome-okf](https://github.com/McClawdDigital/awesome-okf) |

## How this repo fits

This repository is a plain collection of source `.docx` documents. To make it
OKF-compatible, convert each circular/resolución into an OKF concept markdown
file (YAML frontmatter + body) under a `knowledge/` directory, then validate
with the tools above.
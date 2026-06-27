---
description: Defines the service name, version, and API endpoint for the OKF demo
  conversion service.
source_file: config.yaml
source_format: yaml
tags:
- configuration
- api
- service
- demo
timestamp: '2026-06-27T10:00:40Z'
title: OKF Demo Service Configuration
type: Configuration
---

# Content

*Source: `yaml`*

```yaml
service: okf-demo
version: 1.0
endpoints:
  - path: /api/v1/convert
    method: POST

```

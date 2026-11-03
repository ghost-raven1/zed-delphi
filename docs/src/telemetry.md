---
title: Telemetry
description: "Telemetry removal in Zed Delphi, local diagnostics, and the limits of external-tool privacy."
---

# Telemetry in Zed Delphi

## This fork

This build removes the desktop telemetry collectors and senders. Existing settings cannot turn them back on. The Settings Editor shows that telemetry has been removed instead of offering enable switches.

Removed paths include:

- Usage-event queues, telemetry log creation, installation/system tracking identifiers, and project-type reporting.
- Crash/minidump uploads, automatic build-timing uploads, and hang-event reporting.
- Remote event forwarding and automatic retrieval of remote crash files.
- Anthropic usage-event logging.
- Zed edit-prediction accept, reject, and settled-outcome reporting, training-data collection, and Mercury acceptance/rejection feedback.

Local application, performance, and error logs remain available for troubleshooting. A local session identifier still supports restoring your windows. Existing files from upstream installations are not deleted.

This does not disable the network. Explicit AI requests, collaboration, extension and tool downloads, and manually submitted feedback can still send data required for those actions. Hosted services may retain their own request logs. Separately installed language servers, debug adapters, extensions, and provider processes have their own behavior; the fork does not control their telemetry. You must configure or audit those tools separately.

The removal is implemented in source. A complete application build and runtime traffic inspection on each supported platform are still required before claiming a verified release.

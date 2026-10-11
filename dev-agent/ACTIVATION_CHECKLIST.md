# Controlled activation procedure (staging)

Do not set provider credentials or enable model calls until all of the following
are true:

1. Current branch tests pass on Droplet 2.
2. Provider credentials are stored outside GitHub in a mode-0600 runtime file,
   readable only by the dedicated service account.
3. The real service authenticates the owner granting approval. A boolean in
   Python is not authentication.
4. Provider-side billing alerts and spending controls are configured.
5. Requests use fixed HTTPS vendor origins, timeouts, no redirects, and bounded
   response parsing.
6. A one-request dry run has a documented maximum spend and verified result.
7. Unknown billing outcomes preserve reservations and require reconciliation.
8. No Docker socket access, production trading keys, automatic merges or live
   broker connections are available to the model worker.

The current `Activation` dataclass is a code-level safety gate, not a
user-facing activation endpoint. No unattended service has been enabled.

# Product FAQ

## Account & Access

**How do I reset my password?**
Go to the sign-in page and select "Forgot password". Enter your work email and
follow the reset link, which expires after 30 minutes. If you do not receive the
email within 10 minutes, check spam or contact support.

**How do I enable two-factor authentication (2FA)?**
Open Settings → Security → Two-Factor Authentication and scan the QR code with
an authenticator app. Recovery codes are shown once—store them safely.

## Tenancy & Data

**Is my organization's data isolated from other customers?**
Yes. Every document, chunk, and chat session is scoped to your tenant ID and is
never returned to another tenant. Retrieval queries are filtered by tenant at
the database layer.

**Where is my data stored?**
Documents are chunked, embedded, and stored in an encrypted PostgreSQL database.
Raw files are not retained after ingestion completes.

## Billing

**How does billing work?**
Plans are billed monthly based on the number of active seats and documents
indexed. You can view current usage under Settings → Billing.

**Can I export my data?**
Yes. Use Settings → Data → Export to download all documents and chat history for
your tenant as a ZIP archive.

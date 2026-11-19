Verifiable Credentials
======================

MITx Online can issue a verifiable credential (an Open Badges 3.0 ``OpenBadgeCredential``) alongside each course run certificate and program certificate. The credential is signed by an external VC signer service and stored as a ``VerifiableCredential`` record that the certificate points to through its ``verifiable_credential`` field.

Normally a credential is requested when its certificate is issued. When that doesn't happen, for example because the certificate page wasn't set up yet or the signer returned an error, the certificate is still issued but has no credential. The backfill tools described here fill those gaps.

.. toctree::
   :maxdepth: 3

   backfill.md

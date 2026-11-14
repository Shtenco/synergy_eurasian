# SLE checkpoint anchor backup and restore

Use `src/synergy_labor_checkpoint_backup.py` for online SQLite backup and fail-closed
restore validation. The helper uses SQLite's online backup API, so committed WAL
content is included in the copied database.

## Backup

Call `backup_anchor_database(source, destination, registry_id=..., expected_tail_digest=...)`.
The expected tail digest must come from a separate trusted channel, not from the same
database being copied. The returned SHA-256 of the backup file must also be retained
outside the anchor service host and account.

## Restore

Stop all writers and the service before replacing a live database. Call
`restore_anchor_database(..., expected_tail_digest=..., expected_backup_sha256=...)`.
Restore refuses a backup with altered bytes, broken checkpoint links, altered
checkpoint records, or a tail older/newer than the independently supplied digest.
The restore is staged into a temporary file, validated, and atomically renamed into
place. Restart only after the restored tail has been independently confirmed.

## Security boundary

The helper validates database integrity and checkpoint-chain digests, not Ed25519
signatures. An independent auditor must additionally call
`verify_registry_checkpoints` with the trusted checkpoint-key registry and verify
the underlying award-registry history. The expected tail digest and backup SHA-256
are external trust inputs: keep them in a separately administered immutable store.
This is a backup/restore control for one SQLite service, not multi-region consensus.

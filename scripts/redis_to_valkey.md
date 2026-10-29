# Redis to Valkey one-time migration

`redis_to_valkey.py` copies key data with Redis commands instead of RDB files. It
supports strings, hashes (including field expirations), lists, sets, and sorted
sets. It stops before writing if it finds streams, module data, or Redis
function libraries, since those require separate migration handling.

The copy is not a live snapshot. Stop all application writes to Redis before
running it with `--execute`, and keep them paused until applications are
switched to Valkey. The script's default mode is a read-only dry run. It refuses
to write to a Valkey replica or a non-empty target database unless
`--flush-target` is explicitly supplied.

## Prepare

1. Remove the `replicaof` line from Valkey's Helm values and let Argo CD sync.
   The target must be a writable standalone instance before importing data.
2. Pause applications that write to Redis.
3. Forward both services to the machine where the script will run:

   ```bash
   kubectl port-forward -n databases svc/redis-master 6379:6379
   kubectl port-forward -n databases svc/valkey 6380:6379
   ```

   Run each command in its own terminal, then configure the connection URLs:

   ```bash
   export REDIS_SOURCE_URL=redis://127.0.0.1:6379
   export VALKEY_TARGET_URL=redis://127.0.0.1:6380
   ```

4. Install the client dependency and inspect the source/target:

   ```bash
   python3 -m venv /tmp/redis-to-valkey-venv
   . /tmp/redis-to-valkey-venv/bin/activate
   python -m pip install -r scripts/requirements-redis-to-valkey.txt
   python scripts/redis_to_valkey.py
   ```

The dry run reports key counts by database and type. Review it and ensure the
target is the intended Valkey instance.

## Copy

After confirming the source is quiesced and the dry-run results are expected:

```bash
python scripts/redis_to_valkey.py --execute --source-writes-paused
```

By default, the script requires selected Valkey databases to be empty. Only use
`--flush-target` if you explicitly intend to delete all existing keys in those
databases:

```bash
python scripts/redis_to_valkey.py --execute --source-writes-paused --flush-target
```

The script discovers active database numbers on both servers by default; use
`--databases 0,7` to select specific databases. It never uses `DUMP`, `RESTORE`,
or RDB files. Verify destination key counts and application behavior before
switching clients and resuming writes.

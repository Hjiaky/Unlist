# Backup and restore

A backup is one file that holds everything Unlist knows. You can restore it into a fresh Unlist on the same or another machine. Unlist keeps running while a backup is made.

Unlist never reminds you to back up. It only shows the date of the last backup on the backup page. Make one before every [upgrade](install.md#upgrading) and before you delete anything big.

## What a backup contains, and what it does not

**Contains** (in one `.tar.gz` file):

- A consistent copy of the SQLite database: Subjects, consent records, Cases, drafts, replies, discoveries, overrides, settings.
- The `attachments` folder: replies and evidence files.
- Django's signing secret (`django_secret`).
- A `manifest.json` with the Unlist version, the date, and a checksum for every file. Restore checks the checksums.

**Does not contain:**

- **The encryption key.** This is on purpose. A stolen backup then cannot reveal the stored mailbox and language-model passwords. Keep the key in a separate place. See [the key](install.md#the-key).
- Earlier backups, and temporary import files.

The backup holds the household's data and replies **in readable form** (only passwords are encrypted). Treat it like the data itself.

## Make a backup

Two ways. Both write the same kind of file.

**In the browser.** Open the backup page (`/backup/`, "Backup" in the settings part of the sidebar) and press **Download backup**. Your browser downloads the file. A copy also stays in the `backups` folder of the data directory.

**From the command line.** In the folder with `compose.yaml`:

```sh
docker compose exec --user unlist unlist python manage.py backup
```

It prints the path of the file inside the container, for example `/data/backups/unlist-backup-20261126-213450.tar.gz`. Because `./data` is mounted at `/data`, that file is on your computer at `./data/backups/unlist-backup-20261126-213450.tar.gz`. The file is readable only by its owner (the container's user), so you may need `sudo` to copy it. To write somewhere else inside the container, add `--output <folder>`.

Why `--user unlist`? Without it, the command runs as root inside the container and may create the `backups` folder owned by root, which the web page's download button then cannot write to.

## Keep backups safe

The backup file is personal data about several people.

- **Store it encrypted and private.** For example, an encrypted disk or an encrypted archive (`age`, GnuPG, or a VeraCrypt volume). Do not put it in a shared folder or an unencrypted cloud drive.
- **Keep the key apart.** Store the key file in a different place from the backups, such as a password manager.
- **Copy it off the machine.** A backup that sits only in `./data/backups` is lost together with the disk.
- Delete old backups you no longer need. The `backups` folder grows by one file each time.

## Restore into an empty instance

Restore **only works into an empty instance**: no Operator account, no Subject or Case data, no stored attachments. If it finds data, it refuses and writes nothing. That keeps a restore from mixing two households.

You need: the backup file, and (if you want stored passwords to keep working) your saved copy of the key.

1. **Prepare an empty place.** Use a new folder with a copy of `compose.yaml`, or move the old `data` and `key` folders aside. Create the folders and put the archive and the key in them:

   ```sh
   mkdir -p data/backups key
   cp /path/to/unlist-backup-20261126-213450.tar.gz data/backups/
   cp /path/to/your-saved-unlist.key key/unlist.key      # skip this if you have lost the key
   ```

   The archive must be somewhere inside `./data`, because that is the only part of your computer the container can see (`/data`).

2. **Restore:**

   ```sh
   docker compose run --rm unlist python manage.py restore /data/backups/unlist-backup-20261126-213450.tar.gz
   ```

   Replace the file name with yours. The command prepares the folders, checks the archive and its checksums, restores the database, attachments and signing secret, brings the database up to date (an archive from an older release has an older schema), and checks that every file is there. At the end, it tells you whether the key fits. The start script runs first, as for every command: it prepares the folders and loads the bundled Organization Lists and breach list, which do not count as data, so the instance still counts as empty.

3. **Start Unlist** (it must be restarted to use the restored signing secret) and sign in with the Operator account from the backup:

   ```sh
   docker compose up -d
   ```

### Test a restore in three steps

A backup you have never restored is a hope, not a backup. Test it once, on a spare port, without touching your real instance:

1. **Make a backup** (above) and copy it into an empty test folder: `mkdir -p ../unlist-test/data/backups ../unlist-test/key`, then copy the archive and your saved key into them.
2. **Restore it there.** In `../unlist-test`, create a `compose.yaml` that uses the already built image on another port, then run the restore command from step 2 above:

   ```yaml
   services:
     unlist:
       image: ghcr.io/hjiaky/unlist:1.0.0b1
       ports: ["8001:8000"]
       volumes: ["./data:/data", "./key:/key"]
   ```

   Then `docker compose up -d` in that folder.
3. **Look.** Open <http://localhost:8001>, sign in, and check that the Subjects, their Cases and one reply are there. If you saved a mailbox password, check its connection page. Then `docker compose down` in the test folder and delete the folder: it holds a full copy of your data.

## Without the key

If you restore without the original key, **everything restores except the secrets**. The Cases, replies, attachments and settings are all there. The stored **mailbox app passwords and the language-model key cannot be read**: Unlist tells you so at the end of the restore ("the encryption key here does not match", or "no encryption key is available"). Enter them again on the connection pages and the language model page. Nothing else needs doing. For a household that imports mail files and has no live connection, losing the key costs nothing.

(Without a saved key, the first start of the new instance creates a fresh one. Copy that one somewhere safe too.)

## Known rough edges

- The container commands on this page (`docker compose run`, `--user unlist`) are written from the Dockerfile and start script and were not run inside a container when this page was written. The restore itself was run end to end outside Docker, prepared exactly as the start script prepares a container (bootstrap, migrations, bundled lists, breach list, then restore). If a command fails for you, please report it.
- `docker compose exec` runs commands as root unless you add `--user unlist`. If you forget, files it creates are handed back to Unlist's own user the next time the container starts.

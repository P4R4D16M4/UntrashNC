# UntrashNC

The UntrashOS app for Nextcloud. With it a Nextcloud joins **UntrashMesh**,
the encrypted network of [UntrashOS](https://github.com/P4R4D16M4/ZyxelUntrash)
devices:

- **Directory:** mesh members keep their signed address records at the stable
  internet address of the Nextcloud and find each other again after their
  addresses changed.
- **Change feed:** a linked UntrashOS NAS tells the Nextcloud which files
  changed in its shares. External storages (WebDAV) on that NAS are updated
  path by path instead of being scanned, so the NAS disks can sleep.
- **Tunnel (optional):** with the root helper `untrash-cloud-wg`, the
  Nextcloud server also becomes a WireGuard peer of the mesh, so it reaches
  the NAS shares with no port forwarded at home.

Requirements: Nextcloud 25 to 35, PHP with sodium, the app *External storage
support* for the shares. On the NAS: UntrashOS 1.2 or newer.

**Download:** [releases](https://github.com/P4R4D16M4/UntrashNC/releases).
Installation, setup and commands: [`untrash/README.md`](untrash/README.md).

## Repository

| Path | What it is |
|---|---|
| `untrash/` | the Nextcloud app (app id `untrash`) |
| `server/` | `untrash-cloud-wg`, the optional tunnel helper, and its systemd unit |
| `l10n/` | translation source (`catalog.py`); `build.py` writes `untrash/l10n/` |
| `tests/` | `make test`, `make test-nextcloud` |
| `package.py` | `make app`: reproducible release archives in `build/` |

The interface to the NAS is specified in UntrashOS:
[`docs/architecture/cloud-api.md`](https://github.com/P4R4D16M4/UntrashOS/blob/v1.2/docs/architecture/cloud-api.md).

## Licence

AGPL-3.0-or-later, see [LICENSE](LICENSE).

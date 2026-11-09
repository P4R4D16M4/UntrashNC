<?php

declare(strict_types=1);

namespace OCA\Untrash\Cloudlink;

use OCA\Untrash\Mesh\Mesh;
use OCA\Untrash\Mesh\MeshException;
use OCP\IConfig;
use Psr\Log\LoggerInterface;

/**
 * External storages for the shares the linked NAS offer this Nextcloud.
 *
 * For every NAS with a feed address, GET /v1/info lists the shares linked
 * for this cloud (cloud-api.md §3).  Each one gets an admin mount: WebDAV
 * backend, the NAS's WebDAV port from the feed address, folder
 * webdav/<share>, credentials entered by each user ("user entered"), for the
 * groups in the setting.  "Check for changes" is "Never" while the NAS
 * reports a change feed for the share, else "Once every direct access".
 *
 * A mount that already points at the share (made by hand) is adopted: it is
 * counted, never changed or removed.  Mounts made here are removed when the
 * NAS no longer offers the share or the NAS leaves.  A NAS that does not
 * answer keeps its mounts as they are.
 */
class Mounts {
    public const AUTH = 'password::userprovided';
    private const EVERY = 60;               // seconds between two automatic rounds

    private Mesh $mesh;
    private Client $client;
    private IConfig $config;
    private LoggerInterface $log;

    public function __construct(Mesh $mesh, Client $client, IConfig $config, LoggerInterface $log) {
        $this->mesh = $mesh;
        $this->client = $client;
        $this->config = $config;
        $this->log = $log;
    }

    public function enabled(): bool {
        return $this->config->getAppValue('untrash', 'auto_mounts', 'yes') === 'yes';
    }

    /** @return string[] the groups the automatic mounts are for ([] = everyone) */
    public function groups(): array {
        $g = json_decode($this->config->getAppValue('untrash', 'mount_groups', '["admin"]'), true);
        return is_array($g) ? array_values(array_filter($g, 'is_string')) : ['admin'];
    }

    public function configure(?bool $enabled, ?array $groups): void {
        if ($enabled !== null) {
            $this->config->setAppValue('untrash', 'auto_mounts', $enabled ? 'yes' : 'no');
        }
        if ($groups !== null) {
            $groups = array_values(array_unique(array_filter(array_map('trim', $groups), function ($g) {
                return $g !== '';
            })));
            $this->config->setAppValue('untrash', 'mount_groups', json_encode($groups));
        }
    }

    /** The mounts made or adopted here, for the status: {node: {share: {id, mount, adopted}}}. */
    public function state(): \stdClass {
        return $this->mesh->load('mounts.json', new \stdClass());
    }

    /**
     * One round.  $force: also within EVERY seconds of the last round.
     * @return array {node: {"ok", "shares"?, "error"?}} or {"skipped"|"error": ...}
     */
    public function sync(bool $force = false): array {
        if (!$this->enabled()) {
            return ['skipped' => 'off'];
        }
        $last = (int)$this->config->getAppValue('untrash', 'mounts_t', '0');
        if (!$force && time() - $last < self::EVERY) {
            return ['skipped' => 'recent'];
        }
        $this->config->setAppValue('untrash', 'mounts_t', (string)time());
        try {
            $svc = \OCP\Server::get(\OCA\Files_External\Service\GlobalStoragesService::class);
        } catch (\Throwable $e) {
            return ['error' => 'files_external is off'];
        }
        $names = [];
        $members = [];
        foreach ($this->mesh->status()['members'] as $m) {
            $names[$m['node']] = $m['name'];
            $members[$m['node']] = true;
        }
        $nas = get_object_vars($this->mesh->load('nas.json', new \stdClass()));
        $offered = [];                          // node => {share: feed} for the NAS that answered
        $out = [];
        foreach ($nas as $node => $n) {
            $node = (string)$node;
            if (!isset($members[$node])) {
                continue;
            }
            try {
                $info = $this->client->get($n, '/v1/info', 15, $this->mesh->tlsPin($node));
                $offered[$node] = [];
                foreach ($info['shares'] ?? [] as $s) {
                    if (is_array($s) && preg_match('/^[^\/\\\\\x00-\x1f]{1,80}$/u', (string)($s['name'] ?? ''))) {
                        $offered[$node][(string)$s['name']] = !empty($s['feed']);
                    }
                }
                $out[$node] = ['ok' => true, 'shares' => (object)$offered[$node]];
            } catch (MeshException $e) {
                $out[$node] = ['ok' => false, 'error' => $e->getMessage()];
            }
        }
        $this->mesh->locked(function () use ($svc, $nas, $offered, $names, $members) {
            $state = $this->mesh->load('mounts.json', new \stdClass());
            $all = $svc->getAllStorages();
            foreach (get_object_vars($state) as $node => $shares) {
                $node = (string)$node;
                $gone = !isset($members[$node]) || !isset($nas[$node]);
                foreach (get_object_vars($shares) as $share => $rec) {
                    $share = (string)$share;
                    if (($gone || (isset($offered[$node]) && !isset($offered[$node][$share])))) {
                        if (empty($rec->adopted)) {
                            $this->remove($svc, (int)$rec->id);
                        }
                        unset($state->$node->$share);
                    }
                }
                if (!get_object_vars($state->$node)) {
                    unset($state->$node);
                }
            }
            foreach ($offered as $node => $shares) {
                [$host, $secure] = self::target((string)$nas[$node]->base);
                foreach ($shares as $share => $feed) {
                    $state->$node = $state->$node ?? new \stdClass();
                    $rec = $state->$node->$share ?? null;
                    $cfg = $rec ? self::find($all, (int)$rec->id) : null;
                    if (!$cfg) {
                        $adopt = self::matching($all, $host, (string)$share);
                        if ($adopt) {
                            $state->$node->$share = (object)['id' => $adopt->getId(), 'mount' => $adopt->getMountPoint(), 'adopted' => true];
                            continue;
                        }
                        $cfg = $this->create($svc, $all, $host, $secure, (string)$share, $feed, $names[$node] ?? $node);
                        if (!$cfg) {
                            unset($state->$node->$share);
                            continue;
                        }
                        $all[] = $cfg;
                        $state->$node->$share = (object)['id' => $cfg->getId(), 'mount' => $cfg->getMountPoint(), 'adopted' => false];
                    } elseif (empty($rec->adopted)) {
                        $this->refresh($svc, $cfg, $host, $secure, (string)$share, $feed);
                    }
                }
            }
            $this->mesh->save('mounts.json', $state);
        });
        return $out;
    }

    /** Uninstall: remove the mounts made here (adopted ones stay); returns how many. */
    public function removeAll(): int {
        try {
            $svc = \OCP\Server::get(\OCA\Files_External\Service\GlobalStoragesService::class);
        } catch (\Throwable $e) {
            return 0;
        }
        $n = 0;
        foreach (get_object_vars($this->state()) as $shares) {
            foreach (get_object_vars($shares) as $rec) {
                if (empty($rec->adopted)) {
                    $this->remove($svc, (int)$rec->id);
                    $n++;
                }
            }
        }
        $this->mesh->save('mounts.json', new \stdClass());
        return $n;
    }

    /** [host[:port] for the WebDAV backend, https?] from a feed address. */
    public static function target(string $base): array {
        $u = parse_url($base) ?: [];
        $host = (string)($u['host'] ?? '');
        if (strpos($host, ':') !== false && $host[0] !== '[') {
            $host = '[' . $host . ']';
        }
        return [$host . (isset($u['port']) ? ':' . $u['port'] : ''), strtolower((string)($u['scheme'] ?? '')) === 'https'];
    }

    private static function hostOf(array $opt): string {
        $h = (string)($opt['host'] ?? '');
        return trim((string)(parse_url(strpos($h, '://') === false ? 'http://' . $h : $h, PHP_URL_HOST) ?: ''), '[]');
    }

    private static function find(array $all, int $id) {
        foreach ($all as $c) {
            if ($c->getId() === $id) {
                return $c;
            }
        }
        return null;
    }

    /** A WebDAV mount on this host and share that is not ours (made by hand). */
    private static function matching(array $all, string $host, string $share) {
        $h = self::hostOf(['host' => $host]);
        foreach ($all as $c) {
            if ($c->getBackend()->getIdentifier() !== 'dav') {
                continue;
            }
            $o = $c->getBackendOptions();
            if (Feed::sameHost(self::hostOf($o), $h) && trim(rawurldecode((string)($o['root'] ?? '')), '/') === 'webdav/' . $share) {
                return $c;
            }
        }
        return null;
    }

    private function create($svc, array $all, string $host, bool $secure, string $share, bool $feed, string $nasName) {
        $taken = [];
        foreach ($all as $c) {
            $taken[strtolower(trim($c->getMountPoint(), '/'))] = true;
        }
        $mp = $share;
        if (isset($taken[strtolower($mp)])) {
            $mp = $share . ' (' . $nasName . ')';
        }
        for ($i = 2; isset($taken[strtolower($mp)]); $i++) {
            $mp = $share . ' (' . $nasName . ' ' . $i . ')';
        }
        try {
            $cfg = $svc->createStorage('/' . $mp, 'dav', self::AUTH,
                ['host' => $host, 'root' => 'webdav/' . $share, 'secure' => $secure],
                self::mountOptions($feed), [], $this->groups());
            return $svc->addStorage($cfg);
        } catch (\Throwable $e) {
            $this->log->warning('untrash mounts: cannot create /' . $mp . ': ' . $e->getMessage());
            return null;
        }
    }

    private function refresh($svc, $cfg, string $host, bool $secure, string $share, bool $feed): void {
        $o = $cfg->getBackendOptions();
        $m = $cfg->getMountOptions();
        $want = self::mountOptions($feed);
        $changed = false;
        if (($o['host'] ?? '') !== $host || (bool)($o['secure'] ?? false) !== $secure
            || ($o['root'] ?? '') !== 'webdav/' . $share) {
            $o['host'] = $host;
            $o['secure'] = $secure;
            $o['root'] = 'webdav/' . $share;
            $cfg->setBackendOptions($o);
            $changed = true;
        }
        if ((int)($m['filesystem_check_changes'] ?? -1) !== $want['filesystem_check_changes']) {
            $m['filesystem_check_changes'] = $want['filesystem_check_changes'];
            $cfg->setMountOptions($m);
            $changed = true;
        }
        $groups = $this->groups();
        $cur = $cfg->getApplicableGroups();
        sort($cur);
        sort($groups);
        if ($cur !== $groups || $cfg->getApplicableUsers()) {
            $cfg->setApplicableGroups($groups);
            $cfg->setApplicableUsers([]);
            $changed = true;
        }
        if ($changed) {
            try {
                $svc->updateStorage($cfg);
            } catch (\Throwable $e) {
                $this->log->warning('untrash mounts: cannot update ' . $cfg->getMountPoint() . ': ' . $e->getMessage());
            }
        }
    }

    private function remove($svc, int $id): void {
        try {
            $svc->removeStorage($id);
        } catch (\Throwable $e) {
            // already removed by an admin
        }
    }

    private static function mountOptions(bool $feed): array {
        return ['filesystem_check_changes' => $feed ? 0 : 1, 'enable_sharing' => false, 'previews' => true,
                'encrypt' => true, 'readonly' => false, 'encoding_compatibility' => false];
    }
}

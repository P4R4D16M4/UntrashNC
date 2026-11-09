<?php

declare(strict_types=1);

namespace OCA\Untrash\Migration;

use OCA\Untrash\Cloudlink\Mounts;
use OCA\Untrash\Mesh\Mesh;
use OCP\IConfig;
use OCP\Migration\IOutput;
use OCP\Migration\IRepairStep;

/**
 * On uninstall: the external storages this app made go too (storages made by
 * hand stay), then its mesh identity and state and its settings.
 */
class RemoveMounts implements IRepairStep {
    private Mounts $mounts;
    private Mesh $mesh;
    private IConfig $config;

    public function __construct(Mounts $mounts, Mesh $mesh, IConfig $config) {
        $this->mounts = $mounts;
        $this->mesh = $mesh;
        $this->config = $config;
    }

    public function getName(): string {
        return 'Remove the external storages and the data of the UntrashOS app';
    }

    public function run(IOutput $output): void {
        $output->info('removed ' . $this->mounts->removeAll() . ' external storages');
        $this->mesh->forget();
        $this->config->deleteAppValues('untrash');
    }
}

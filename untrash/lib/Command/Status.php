<?php

declare(strict_types=1);

namespace OCA\Untrash\Command;

use OCA\Untrash\Cloudlink\Mounts;
use OCA\Untrash\Mesh\Mesh;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

class Status extends Command {
    private Mesh $mesh;
    private Mounts $mounts;

    public function __construct(Mesh $mesh, Mounts $mounts) {
        parent::__construct();
        $this->mesh = $mesh;
        $this->mounts = $mounts;
    }

    protected function configure(): void {
        $this->setName('untrash:status')->setDescription('UntrashMesh membership of this Nextcloud (JSON)');
    }

    protected function execute(InputInterface $in, OutputInterface $out): int {
        $out->writeln(json_encode($this->mesh->status() + ['mounts' => ['enabled' => $this->mounts->enabled(),
            'groups' => $this->mounts->groups(), 'made' => $this->mounts->state()]], JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT));
        return 0;
    }
}

<?php

declare(strict_types=1);

namespace OCA\Untrash\Command;

use OCA\Untrash\Cloudlink\Mounts as MountsService;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

/** The automatic external storages for the shares the NAS offer (one round now, settings). */
class Mounts extends Command {
    private MountsService $mounts;

    public function __construct(MountsService $mounts) {
        parent::__construct();
        $this->mounts = $mounts;
    }

    protected function configure(): void {
        $this->setName('untrash:mounts')->setDescription('External storages for the shares the UntrashOS NAS offer: one round now')
            ->addOption('groups', null, InputOption::VALUE_REQUIRED, 'groups the storages are for, comma-separated ("" = everyone)')
            ->addOption('on', null, InputOption::VALUE_NONE, 'make the storages automatically (default)')
            ->addOption('off', null, InputOption::VALUE_NONE, 'stop making them (existing ones stay)');
    }

    protected function execute(InputInterface $in, OutputInterface $out): int {
        $g = $in->getOption('groups');
        $this->mounts->configure($in->getOption('on') ? true : ($in->getOption('off') ? false : null),
                                 $g === null ? null : explode(',', (string)$g));
        $r = $this->mounts->sync(true);
        $out->writeln(json_encode(['enabled' => $this->mounts->enabled(), 'groups' => $this->mounts->groups(),
                                   'round' => $r, 'made' => $this->mounts->state()], JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT));
        return isset($r['error']) ? 1 : 0;
    }
}

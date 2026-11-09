<?php

declare(strict_types=1);

namespace OCA\Untrash\BackgroundJob;

use OCA\Untrash\Cloudlink\Feed;
use OCA\Untrash\Cloudlink\Mounts;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\TimedJob;

/**
 * Every 5 minutes: the external storages for the shares the NAS offer, then
 * the changes the NAS collected since the last run.  For
 * changes within seconds run "occ untrash:feed" as a service instead (it
 * long-polls; this job then finds the NAS busy and skips it).
 */
class FeedJob extends TimedJob {
    private Feed $feed;
    private Mounts $mounts;

    public function __construct(ITimeFactory $time, Feed $feed, Mounts $mounts) {
        parent::__construct($time);
        $this->feed = $feed;
        $this->mounts = $mounts;
        $this->setInterval(300);
    }

    protected function run($argument): void {
        $this->mounts->sync();
        $this->feed->run(0);
    }
}

from collections import deque
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from multiprocessing import Semaphore

from datatrove.executor.base import PipelineExecutor

download_semaphore, upload_semaphore = None, None


def init_pool_processes(dl_sem, up_sem):
    global download_semaphore, upload_semaphore
    download_semaphore = dl_sem
    upload_semaphore = up_sem


class LocalPipelineExecutor(PipelineExecutor):
    def __init__(
            self,
            tasks: int,
            workers: int = -1,
            max_concurrent_uploads: int = 20,
            max_concurrent_downloads: int = 50,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.tasks = tasks
        self.workers = workers if workers != -1 else tasks
        self.max_concurrent_uploads = max_concurrent_uploads
        self.max_concurrent_downloads = max_concurrent_downloads

    def _run_for_rank(self, rank: int):
        if self.workers == 1:
            # make a deepcopy of the pipeline steps
            self.pipeline = deepcopy(self.pipeline)
        else:
            for pipeline_step in self.pipeline:
                pipeline_step.set_up_dl_locks(download_semaphore, upload_semaphore)
        super()._run_for_rank(rank)

    def run(self):
        if self.workers == 1:
            for rank in range(self.tasks):
                self._run_for_rank(rank)
        else:
            dl_sem = Semaphore(self.max_concurrent_downloads)
            up_sem = Semaphore(self.max_concurrent_uploads)
            with ProcessPoolExecutor(max_workers=self.workers, initializer=init_pool_processes,
                                     initargs=(dl_sem, up_sem)) as pool:
                deque(pool.map(self._run_for_rank, range(self.tasks)), maxlen=0)

    @property
    def world_size(self):
        return self.tasks

import asyncio
import uuid
from typing import Callable, Awaitable, Dict, Any, Optional
from .repository import ExecutionRepository
from ..contracts.execution import ExecutionInfo

class ExecutionManager:
    """Manages background execution tasks and updates their state.

    - Starts a new execution and returns its UUID.
    - Runs a provided coroutine (the analysis pipeline) in the background.
    - Persists intermediate state via ExecutionRepository.
    - Supports cancellation via an asyncio.Event flag.
    """

    def __init__(self, repository: Optional[ExecutionRepository] = None) -> None:
        self.repo = repository or ExecutionRepository()
        self._tasks: Dict[str, asyncio.Task] = {}
        self._cancel_flags: Dict[str, asyncio.Event] = {}

    def start_execution(self, coro_factory: Callable[[str, asyncio.Event], Awaitable[Dict[str, Any]]]) -> str:
        """Create a new execution entry and schedule the coroutine.

        Parameters
        ----------
        coro_factory: Callable[[execution_id, cancel_event], Awaitable[dict]]
            A coroutine factory that receives the execution_id and a cancellation event.
            It should return a dict representing the final execution payload to be stored.
        Returns
        -------
        str
            The generated execution_id.
        """
        execution_id = uuid.uuid4().hex
        # initialise repository entry with PENDING status
        exec_info = ExecutionInfo.start()
        exec_info.execution_id = execution_id  # overwrite generated id with our own
        self.repo.save(execution_id, exec_info.to_dict())
        cancel_event = asyncio.Event()
        self._cancel_flags[execution_id] = cancel_event
        task = asyncio.create_task(self._run_task(execution_id, coro_factory, cancel_event))
        self._tasks[execution_id] = task
        return execution_id

    async def _run_task(
        self,
        execution_id: str,
        coro_factory: Callable[[str, asyncio.Event], Awaitable[Dict[str, Any]]],
        cancel_event: asyncio.Event,
    ) -> None:
        """Execute the underlying coroutine and persist results.
        Updates the repository with intermediate status changes.
        """
        exec_info = ExecutionInfo.start()
        exec_info.execution_id = execution_id
        exec_info.status = "RUNNING"
        self.repo.save(execution_id, exec_info.to_dict())
        try:
            result = await coro_factory(execution_id, cancel_event)
            exec_info = exec_info.mark_succeeded()
            payload = {**exec_info.to_dict(), **result}
            self.repo.save(execution_id, payload)
        except asyncio.CancelledError:
            exec_info = exec_info.mark_failed()
            exec_info.status = "CANCELLED"
            self.repo.save(execution_id, exec_info.to_dict())
        except Exception:
            exec_info = exec_info.mark_failed()
            self.repo.save(execution_id, exec_info.to_dict())
        finally:
            self._tasks.pop(execution_id, None)
            self._cancel_flags.pop(execution_id, None)

    def cancel(self, execution_id: str) -> bool:
        """Request cancellation of a running execution.
        Returns True if a cancel flag was set, False if execution not found.
        """
        flag = self._cancel_flags.get(execution_id)
        if flag:
            flag.set()
            task = self._tasks.get(execution_id)
            if task:
                task.cancel()
            return True
        return False

    def get_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the stored JSON payload for the given execution."""
        return self.repo.load(execution_id)

    def list_executions(self) -> list:
        """Return a list of execution summaries."""
        return self.repo.list_executions()

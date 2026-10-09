from collections import deque
from pyjab.common.logger import Logger
from pyjab.common.singleton import singleton


@singleton
class ActorScheduler:
    """Cooperative generator scheduler. **Deprecated and no longer used.**

    .. deprecated:: 1.3.0
       pyjab used to run the Windows message pump through this class, by
       registering a generator and advancing it one step per call.  That design
       was broken in three ways and has been replaced by the plain, blocking-free
       :meth:`pyjab.common.win32utils.Win32Utils.pump_messages`:

       * ``run()`` popped one entry and sent one value, so the pump advanced a
         single step per call and no state survived between calls;
       * when a discarded pump generator was garbage collected its ``finally``
         clause set the shared stop event, which made every second pump call a
         no-op;
       * the pump only ran while waiting for the first window, so nothing was
         serviced during element lookups.

       The class is kept only so that existing imports do not break.  Do not use
       it for new code.

    Note that it is **not** a thread pool: ``run()`` calls ``actor.send()``
    synchronously in the calling thread and never creates a thread.

    Sample:

        sched = ActorScheduler()
        sched.new_actor("jab", some_generator())
        sched.run()
    """

    def __init__(self):
        self.actors = {}  # Mapping of names to actors
        self.msg_queue = deque()  # Message queue
        self.logger = Logger("pyjab")

    def new_actor(self, name, actor):
        """
        Admit a newly started actor to the scheduler and give it a name
        """
        self.logger.debug(f"msg queue append new actor '{name}'")
        self.msg_queue.append((actor, None))
        self.actors[name] = actor

    def send(self, name, msg):
        """
        Send a message to a named actor
        """
        if actor := self.actors.get(name):
            self.logger.debug(f"send msg '{msg}' to actor '{actor}'")
            self.msg_queue.append((actor, msg))

    def run(self):
        """
        Run as long as there are pending messages.
        """
        while self.msg_queue:
            actor, msg = self.msg_queue.popleft()
            try:
                self.logger.debug(f"run actor '{actor}' with msg '{msg}'")
                actor.send(msg)
            except StopIteration:
                self.logger.debug("stop run action in scheduler")

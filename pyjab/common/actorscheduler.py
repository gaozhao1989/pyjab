from collections import deque
from pyjab.common.logger import Logger
from pyjab.common.singleton import singleton


@singleton
class ActorScheduler:
    """Message queue for run generator func as thread.

    Sample:

        sched = ActorScheduler()
        sched.new_actor("jab", win32utils.setup_msg_pump())
        sched.run()
    """

    def __init__(self) -> None:
        # Mapping of names to actors
        self.actors = {}
        # Message queue
        self.msg_queue = deque()
        self.logger = Logger("pyjab")

    def new_actor(self, name: str, actor) -> None:
        """
        Admit a newly started actor to the scheduler and give it a name
        """
        self.logger.debug(f"Append new actor '{actor}' to msg deque")
        self.logger.debug(f"actor type => {type(actor)}")
        self.msg_queue.append((actor, None))
        self.actors[name] = actor

    def send(self, name: str, msg: str) -> None:
        """
        Send a message to a named actor
        """
        if actor := self.actors.get(name):
            self.logger.debug(f"Send msg '{msg}' to actor '{actor}'")
            self.msg_queue.append((actor, msg))

    def run_actor(self) -> None:
        """
        Run as long as there are pending messages.
        """
        while self.msg_queue:
            actor, msg = self.msg_queue.popleft()
            try:
                self.logger.debug(f"Run actor '{actor}' with msg '{msg}'")
                actor.send(msg)
            except StopIteration:
                self.logger.debug("Stop run action in scheduler")

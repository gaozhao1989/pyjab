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

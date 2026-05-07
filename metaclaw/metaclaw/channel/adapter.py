"""Channel adapter interface for external messaging integrations."""

from abc import ABC, abstractmethod
from typing import Iterable


class ChannelAdapter(ABC):
    """Base contract for channel integrations.

    Adapters own the transport-specific lifecycle and translate external
    platform payloads into MetaClaw message objects. Implementations should be
    idempotent where practical: calling ``start`` on an already-running adapter
    or ``stop`` on an already-stopped adapter should not corrupt state.

    ``send_message`` should raise a descriptive exception when delivery fails.
    ``receive_messages`` should return any messages currently available without
    blocking indefinitely; long-polling adapters should use a bounded timeout.
    """

    @abstractmethod
    def start(self):
        """Open network connections, register webhooks, or start workers."""
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        """Release resources and stop background work gracefully."""
        raise NotImplementedError

    @abstractmethod
    def send_message(self, message):
        """Send a MetaClaw reply or transport-native message payload."""
        raise NotImplementedError

    @abstractmethod
    def receive_messages(self) -> Iterable:
        """Return newly received messages as an iterable."""
        raise NotImplementedError

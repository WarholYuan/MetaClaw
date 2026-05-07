# Channel Adapter Development

Channel adapters connect MetaClaw to external messaging systems. New adapters
should implement `channel.adapter.ChannelAdapter`.

## Interface

- `start()`: Open connections, register webhooks, or start bounded workers.
- `stop()`: Release resources and stop background work.
- `send_message(message)`: Deliver a MetaClaw reply or transport-native payload.
- `receive_messages()`: Return currently available messages without blocking
  indefinitely.

Adapters should translate platform payloads into MetaClaw message objects as
early as possible and keep platform-specific fields in a documented raw payload
field when they are needed later.

## Reliability

`start()` and `stop()` should be idempotent where practical. Network failures
should raise descriptive exceptions or emit structured errors that include the
channel name, operation, and upstream status. Long-polling implementations must
use bounded timeouts so the runtime can shut down cleanly.

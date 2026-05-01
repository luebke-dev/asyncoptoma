# asyncoptoma
## Control your Optoma projector with python


## Installation

```bash
pip install asyncoptoma
```

## Usage
```python
import asyncio

from asyncoptoma import Optoma

async def main():
    async with Optoma("http://<IP>", username="admin", password="admin") as projector:
        await projector.login()

        await projector.turn_on()
        print(projector.get_available_brightness_modes())

        await projector.set_active_brightness_mode("Power 50%")
        await asyncio.sleep(10)
        await projector.set_active_brightness_mode("DynamicBlack 1")
        await asyncio.sleep(10)
        await projector.set_active_source("HDMI 1")
        await asyncio.sleep(10)
        await projector.set_active_source("HDMI 2/MHL")
        await asyncio.sleep(30)
        await projector.set_zoom(-5)
        await projector.turn_off()

asyncio.run(main())
```

If you skip `async with`, remember to call `await projector.close()` to release
the underlying HTTP connection pool.

Errors raised from the projector or the HTTP layer are wrapped in
`asyncoptoma.OptomaError` (with `OptomaAuthError` for authentication failures).

### Generic accessors

Every named convenience method (`set_active_source`, `get_brightness`, …) is a
thin wrapper around a generic accessor. You can address any field by its raw
projector name directly:

```python
await projector.set_active("source", "HDMI 1")
print(projector.get_active("source"))
print(projector.get_available("lampmd"))

await projector.set_toggle("avmute", True)
print(projector.get_toggle("freeze"))

await projector.set_value("zoom", -5)
print(projector.get_value("bright"))
```

## Tested models

|Model|
|-----|
|UHZ4000|

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

## Tested models

|Model|
|-----|
|UHZ4000|

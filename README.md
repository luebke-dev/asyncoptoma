# asyncoptoma
## Control your Optoma projector with python


## Installation

```bash
pip insall asyncoptoma
```

## Usage
```python
import asyncio

from asyncoptoma import Optoma

async def main():
    projector = Optoma("http://<IP>", username="admin", password="admin")

    await projector.login()
    
    await projector.turn_on()
    print(projector.get_available_brightness_modes())
    #
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

## Tested models

|Model|
|-----|
|UHZ4000|


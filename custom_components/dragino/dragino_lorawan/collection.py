"""Match Dragino devices reported by LoRaWAN connections."""

from lorawan_connection import DeviceCollection, DeviceDescriptor

from .cpl03lb import Cpl03Lb
from .device import BRAND_IDS, DraginoDevice
from .ldds75 import Ldds75
from .lds02 import Lds02, Lwl02
from .lht65n import Lht65n
from .lt22222l import Lt22222l
from .t68dl import T68dl

DEVICES: tuple[type[DraginoDevice], ...] = (
    Cpl03Lb,
    Ldds75,
    Lds02,
    Lht65n,
    Lt22222l,
    Lwl02,
    T68dl,
)


def _normalize(name: str) -> str:
    """Compare model names regardless of case and separators."""
    return "".join(char for char in name.lower() if char.isalnum())


_MODELS_BY_NAME: dict[str, type[DraginoDevice]] = {
    _normalize(name): model for model in DEVICES for name in model.NAMES
}


class DraginoDeviceCollection(DeviceCollection[DraginoDevice]):
    """Create Dragino models from catalog identifiers, falling back to the model name.

    The fallback covers devices the catalogs list under another identifier,
    such as a ChirpStack catalog entry added later than this integration.
    """

    DEVICES = DEVICES

    def _create_device(self, descriptor: DeviceDescriptor) -> DraginoDevice | None:
        if (device := super()._create_device(descriptor)) is not None:
            return device
        if BRAND_IDS.get(descriptor.stack) != descriptor.brand_id:
            return None
        model = _MODELS_BY_NAME.get(_normalize(descriptor.model or descriptor.model_id))
        return model(descriptor) if model is not None else None

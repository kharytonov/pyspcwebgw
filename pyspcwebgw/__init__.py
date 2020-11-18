"""Python wrapper for the Lundix SPC Web Gateway REST API."""
import logging
from urllib.parse import urljoin
from asyncio import ensure_future

from .area import Area
from .zone import Zone
from .const import AreaMode
from .utils import async_request
from .websocket import AIOWSClient

_LOGGER = logging.getLogger(__name__)


class SpcWebGateway:
    """Alarm system representation."""

    def __init__(self, loop, session, api_url, ws_url, async_callback):
        """Initialize the client."""
        self._loop = loop
        self._session = session
        self._api_url = api_url
        self._ws_url = ws_url
        self._info = None
        self._areas = {}
        self._zones = {}
        self._websocket = None
        self._async_callback = async_callback

    @property
    def info(self):
        """Retrieve basic panel info."""
        return self._info

    @property
    def areas(self):
        """Retrieve all available areas."""
        return self._areas

    @property
    def zones(self):
        """Retrieve all available zones."""
        return self._zones

    def start(self):
        """Connect websocket to SPC Web Gateway."""
        self._websocket = AIOWSClient(loop=self._loop,
                                      session=self._session,
                                      url=self._ws_url,
                                      async_callback=self._async_ws_handler)
        self._websocket.start()

    async def async_load_parameters(self):
        """Fetch area and zone info from SPC to initialize."""
        self._info = await self._async_get_panel_info()
        zones = await self._async_get_zones()
        areas = await self._async_get_areas()

        if not zones or not areas:
            return False

        for spc_area in areas:
            area = Area(self, spc_area)
            area_zones = [Zone(area, z) for z in zones
                          if z['area'] == spc_area['id']]
            area.zones = area_zones
            self._areas[area.id] = area
            self._zones.update({z.id: z for z in area_zones})

        return True

    async def change_mode(self, area, new_mode):
        """Set/unset/part set an area."""
        if not isinstance(new_mode, AreaMode):
            raise TypeError("new_mode must be an AreaMode")

        AREA_MODE_COMMAND_MAP = {
            AreaMode.UNSET: 'unset',
            AreaMode.PART_SET_A: 'set_a',
            AreaMode.PART_SET_B: 'set_b',
            AreaMode.FULL_SET: 'set'
        }
        if not isinstance(area, Area):
            area = self._areas.get(area)

        url = urljoin(self._api_url, "spc/area/{area_id}/{command}".format(
            area_id=area.id, command=AREA_MODE_COMMAND_MAP[new_mode]))

        data = await async_request(self._session.put, url)
        await area.update_state(self)
        return data

    async def _async_ws_handler(self, data):
        """Process incoming websocket message."""

        sia_message = data['data']['sia']
        spc_id = sia_message['sia_address']
        sia_code = sia_message['sia_code']

        _LOGGER.debug("SIA code is %s for ID %s", sia_code, spc_id)

        if sia_code in Area.SUPPORTED_SIA_CODES:
            if len(self._areas) == 1:
                entity = list(self._areas.values())[0]
            else:
                entity = self._areas.get(spc_id, None)
        elif sia_code in Zone.SUPPORTED_SIA_CODES:
            entity = self._zones.get(spc_id, None)
        else:
            _LOGGER.debug("Not interested in SIA code %s", sia_code)
            return
        if not entity:
            _LOGGER.error("Received message for unregistered ID %s", spc_id)
            return
        else:
            await entity.update_state(self, sia_code)

        if self._async_callback:
            ensure_future(self._async_callback(entity))

    async def _async_get_zones(self):
        """Get the data for all resourced of a specific type """
        url = urljoin(self._api_url, "spc/zone")
        data = await async_request(self._session.get, url)
        if data:
            return [item for item in data['data']["zone"]]

    async def _async_get_areas(self):
        """Get the data for all resourced of a specific type """
        url = urljoin(self._api_url, "spc/area")
        data = await async_request(self._session.get, url)
        if data:
            return [item for item in data['data']["area"]]

    async def _async_get_panel_info(self):
        """Get the data for all resourced of a specific type """
        url = urljoin(self._api_url, "spc/panel")
        data = await async_request(self._session.get, url)
        if data:
            return data['data']["panel"]

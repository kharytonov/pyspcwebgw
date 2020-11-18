import logging
from urllib.parse import urljoin

from pyspcwebgw.const import AreaMode
from pyspcwebgw.utils import _load_enum, async_request

_LOGGER = logging.getLogger(__name__)


class Area:
    """Represents and SPC alarm system area."""
    SUPPORTED_SIA_CODES = ('CG', 'NL', 'OG', 'BV', 'OP')

    def __init__(self, gateway, spc_area):
        self._gateway = gateway
        self._id = spc_area['id']
        self._name = spc_area['name']
        self._verified_alarm = False
        self.zones = None

        self.update(spc_area)

    def __str__(self):
        return '{id}: {name}. Mode: {mode}, last changed by {last}.'.format(
            name=self.name, id=self.id,
            mode=self.mode, last=self.last_changed_by)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def verified_alarm(self):
        return self._verified_alarm

    @property
    def mode(self):
        return self._mode

    @property
    def last_changed_by(self):
        return self._last_changed_by

    def update(self, api_data, sia_code=None):
        _LOGGER.debug("Update area %s", self.id)

        self._mode = _load_enum(AreaMode, api_data['mode'])
        self._verified_alarm = sia_code == 'BV'
        if self._mode == AreaMode.UNSET:
            self._last_changed_by = api_data.get('last_unset_user_name', 'N/A')
        else:
            self._last_changed_by = api_data.get('last_set_user_name', 'N/A')

    async def update_state(self, gw, sia_code=None):
        url = urljoin(gw._api_url, "spc/area/{}".format(self.id))
        data = await async_request(gw._session.get, url)
        if data:
            data = data['data']['area'][0]
            self.update(data)

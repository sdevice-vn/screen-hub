"""Ghép cặp: phát hiện qua mDNS -> nhập mã 6 số đang hiện trên màn hình -> cấp khóa riêng cho thiết bị."""
from __future__ import annotations

import logging
import secrets
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.components import network
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_ID, CONF_HOST, CONF_KEY, CONF_PORT, DEVICE_HTTP_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ScreenHubConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host = ""
        self._port = DEVICE_HTTP_PORT
        self._device_id = ""
        self._name = "Màn hình HA"

    async def _fetch_info(self) -> bool:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(f"http://{self._host}:{self._port}/info",
                                   timeout=aiohttp.ClientTimeout(total=5)) as r:
                info = await r.json()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return False
        self._device_id = info.get("id", "")
        self._name = info.get("name", self._name)
        return bool(self._device_id)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors = {}
        if user_input:
            self._host = user_input.get(CONF_HOST, "").strip()
            if not self._host:
                # Chưa có màn hình thật: tạo mục "xem thử" để dùng được panel cấu hình
                await self.async_set_unique_id("preview")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Màn hình HA (xem thử)", data={
                    CONF_DEVICE_ID: "preview", CONF_HOST: "", CONF_PORT: DEVICE_HTTP_PORT,
                    CONF_KEY: secrets.token_urlsafe(24)})
            if await self._fetch_info():
                await self.async_set_unique_id(self._device_id)
                self._abort_if_unique_id_configured()
                return await self.async_step_pair()
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Optional(CONF_HOST, default=""): str}),
            errors=errors)

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        self._host = str(discovery_info.ip_address)
        self._port = discovery_info.port or DEVICE_HTTP_PORT
        props = discovery_info.properties
        self._device_id = props.get("id", "")
        self._name = props.get("name", self._name)
        if not self._device_id:
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(self._device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host, CONF_PORT: self._port})
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_pair()

    async def async_step_pair(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors = {}
        if user_input:
            key = secrets.token_urlsafe(24)
            ha_host = await network.async_get_source_ip(self.hass, target_ip=self._host)
            body = {"code": user_input["code"].strip(), "key": key,
                    "ha_host": ha_host, "ha_port": self.hass.config.api.port}
            session = async_get_clientsession(self.hass)
            try:
                async with session.post(f"http://{self._host}:{self._port}/pair", json=body,
                                        timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 200:
                        return self.async_create_entry(title=self._name, data={
                            CONF_DEVICE_ID: self._device_id, CONF_HOST: self._host,
                            CONF_PORT: self._port, CONF_KEY: key})
                    errors["base"] = "invalid_code" if r.status in (401, 403) else "cannot_connect"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="pair", data_schema=vol.Schema({vol.Required("code"): str}),
            description_placeholders={"name": self._name}, errors=errors)

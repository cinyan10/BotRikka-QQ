import asyncio
import logging

import re
import socket

from rcon.source import Client
from rcon.source import rcon

from config import RCON_PASSWORD, SERVER_LIST
from utils.configs.steam import STEAMID

logger = logging.getLogger(__name__)


def send_rcon(address: tuple, command, *args, password=RCON_PASSWORD):
    ip, port = address
    try:
        with Client(ip, port, passwd=password, timeout=2.0) as client:
            response = client.run(command, *args)
            return response
    except socket.timeout:
        logger.info(f"sync rcon querying {address} timeout")
        return None


async def send_rcon_async(address: tuple, command, *args, password=RCON_PASSWORD):
    ip, port = address
    try:
        response = await rcon(command, *args, host=ip, port=port, passwd=password, timeout=2)
        return response
    except socket.timeout:
        logger.info(f"querying {address} timeout")
        return None


async def rcon_server_status(address: tuple, password=RCON_PASSWORD) -> dict or None:
    response = await send_rcon_async(address, 'status', password=password)
    if response:
        status_data = parse_status_string(response)
        status_data['address'] = f"{address[0]}:{address[1]}"
        return status_data
    else:
        return None


async def rcon_servers_info(servers: list[tuple] = SERVER_LIST, password=RCON_PASSWORD):
    tasks = [rcon_server_status(server, password) for server in servers]
    responses = await asyncio.gather(*tasks)
    return responses


async def rcon_all_servers(command, *args, servers: list[tuple] = SERVER_LIST, password=RCON_PASSWORD):
    tasks = [send_rcon_async(server, command, *args, password=password) for server in servers]
    responses = await asyncio.gather(*tasks)
    return responses


def parse_status_string(status_string) -> dict:
    """
    This function parses a server status string from a Source engine game server (like CS:GO) and returns a dictionary with the following keys:
    - 'server_name': The name of the server.
    - 'version': The version of the server.
    - 'os': The operating system the server is running on.
    - 'type': The type of the server (e.g., 'community dedicated').
    - 'map': The current map on the server.
    - 'player_count': The number of human players currently on the server.
    - 'max_players': The maximum number of players that the server can accommodate.
    - 'bot_count': The number of dc_bot players currently on the server.
    - 'players': A list of dictionaries, each representing a player currently on the server. Each dictionary has the following keys:
        - 'name': The name of the player.
        - 'steamid': The Steam ID of the player.
        - 'duration': The time the player has been connected to the server.
        - 'ping': The player's ping.
        - 'loss': The player's packet loss.
        - 'state': The player's state (e.g., 'active').
        - 'rate': The player's rate.
        - 'ip': The IP address of the player.
    """
    result = {}

    match = re.search(r'hostname: (.+)', status_string)
    if match:
        result['server_name'] = match.group(1)

    match = re.search(r'version : (.+?)/', status_string)
    if match:
        result['version'] = match.group(1)

    match = re.search(r'os {6}: {2}(.+)', status_string)
    if match:
        result['os'] = match.group(1)

    match = re.search(r'type {4}: {2}(.+)', status_string)
    if match:
        result['type'] = match.group(1)

    match = re.search(r'map {5}: (.+)', status_string)
    if match:
        result['map'] = match.group(1)

    match = re.search(r'players : (\d+) humans', status_string)
    if match:
        result['player_count'] = int(match.group(1))

    match = re.search(r'players : .+ \((\d+)/', status_string)
    if match:
        result['max_players'] = int(match.group(1))

    match = re.search(r'players : .+ (\d+) bots', status_string)
    if match:
        result['bot_count'] = int(match.group(1))

    player_data = re.findall(r'#*"(.+)" (STEAM_.+?) (.+)', status_string)
    result['players'] = [
        {
            'name': name,
            'steamid': uniqueid,
            'duration': connected.split()[0],
            'ping': connected.split()[1],
            'loss': connected.split()[2],
            'state': connected.split()[3],
            'rate': connected.split()[4],
            'ip': connected.split()[5].split(':')[0]
        }
        for name, uniqueid, connected in player_data
    ]

    return result


if __name__ == '__main__':
    task = rcon_all_servers('sm_whitelist_add', f'"{STEAMID}"')
    print(asyncio.run(task))
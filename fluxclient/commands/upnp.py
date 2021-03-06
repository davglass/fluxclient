
from getpass import getpass, getuser
from uuid import UUID
import argparse
import sys

from .misc import (get_or_create_default_key, setup_logger,
                   network_config_helper)

PROG_DESCRIPTION = "Flux upnp tool allow user change device settings."
PROG_EPILOG = """Upnp tool support
  'Grant access permission from password'
  'Manage access control list'
  'Change device password'
  'Change device network'
"""


def quit_program(upnp, logger):
    """Quit"""
    sys.exit(0)


def change_device_name(upnp, logger):
    """Change device name"""
    name = input("New device name: ").strip()
    if name:
        upnp.rename(name)
        logger.error("Done.")
    else:
        logger.error("No name given.")


def change_device_password(upnp, logger):
    """Change device password"""
    old_pass = getpass("Old password: ")
    new_pass = getpass("New password: ")
    if getpass("Confirm new password: ") != new_pass:
        logger.error("New password not match")
        return
    if len(new_pass) < 3:
        logger.error("Password too short")
        return
    upnp.modify_password(old_pass, new_pass)


def change_network_settings(upnp, logger):
    """Change network settings"""
    settings = network_config_helper.run()
    upnp.modify_network(**settings)


def get_wifi_list(upnp, logger):
    """Get wifi list"""
    logger.info("%17s %5s %23s %s", "bssid", "rssi", "security", "ssid")
    for r in upnp.get_wifi_list():
        logger.info("%17s %5s %23s %s", r["bssid"], r["rssi"], r["security"],
                    r["ssid"])

    logger.info("--\n")


def add_trust(upnp, logger):
    """Add an ID to trusted list"""

    filename = input("Keyfile (keep emptry to use current session key): ")
    if filename:
        with open(filename, "r") as f:
            aid = upnp.add_trust(getuser(), f.read())
    else:
        aid = upnp.add_trust(getuser(),
                             upnp.client_key.public_key_pem.decode())

    logger.info("Key added with Access ID: %s\n", aid)


def list_trust(upnp, logger):
    """List trusted ID"""

    logger.info("=" * 79)
    logger.info("%40s  %s", "access_id", "label")
    logger.info("-" * 79)
    for meta in upnp.list_trust():
        logger.info("%40s  %s", meta["access_id"], meta.get("label"))
    logger.info("=" * 79 + "\n")


def remove_trust(upnp, logger):
    """Remove trusted ID"""
    access_id = input("Access id to remove: ")
    upnp.remove_trust(access_id)
    logger.info("Access ID %s REMOVED.\n", access_id)


def run_commands(upnp, logger):
    from fluxclient.upnp import UpnpError

    tasks = [
        quit_program,
        change_device_name,
        change_device_password,
        change_network_settings,
        get_wifi_list,
        add_trust,
        list_trust,
        remove_trust,
    ]

    while True:
        logger.info("Upnp tool: Choose task id")
        for i, t in enumerate(tasks):
            logger.info("  %i: %s", i, t.__doc__)
        logger.info("")

        try:
            r = input("> ").strip()
            if not r:
                continue

            try:
                i = int(r, 10)
                t = tasks[i]
            except (IndexError, ValueError):
                logger.error("Unknow task: '%s'", r)
                continue
            t(upnp, logger)
        except UpnpError as e:
            logger.error("Error '%s'", e)
        except KeyboardInterrupt as e:
            logger.info("\n")
            return

        logger.info("")


def fast_add_trust(upnp, logger):
    from fluxclient.upnp import UpnpError

    try:
        upnp.add_trust(getuser(),
                       upnp.client_key.public_key_pem.decode())
        logger.info("authorized.")
        return 0
    except UpnpError as e:
        logger.error("Error '%s'", e)
        return 1


def main(params=None):
    parser = argparse.ArgumentParser(description=PROG_DESCRIPTION,
                                     epilog=PROG_EPILOG)
    parser.add_argument(dest='target', type=str,
                        help="Device uuid or ipaddress to connect to. "
                             "IP address can be '192.168.1.1' or "
                             "'192.168.1.1:23811'.")
    parser.add_argument('--key', dest='client_key', type=str, default=None,
                        help='Client identify key (RSA key with pem format)')
    parser.add_argument('-a', '--auth-only', dest='auth_only',
                        action='store_const', const=True, default=False,
                        help='Do a quick authorize and exit rather then enter '
                             'the interaction shell')
    parser.add_argument('-p', '--password', dest='password', type=str,
                        help='Use password in argument instead. A password '
                             'prompt will not appear.')
    parser.add_argument('--verbose', dest='verbose', action='store_const',
                        const=True, default=False, help='Verbose output')

    options = parser.parse_args(params)
    logger = setup_logger(__name__, debug=options.verbose)

    from fluxclient.robot.misc import is_uuid
    from fluxclient.upnp import UpnpTask

    client_key = get_or_create_default_key(options.client_key)

    if is_uuid(options.target):
        upnp = UpnpTask(UUID(hex=options.target), client_key)
    else:
        upnp = UpnpTask(UUID(int=0), client_key, ipaddr=options.target)

    if not upnp.authorized:
        if options.password is None:
            password = getpass("Device Password: ")
        else:
            password = options.password
        upnp.authorize_with_password(password)

    logger.info("\n"
                "Serial: %s (uuid={%s})\n"
                "Model: %s\n"
                "Version: %s\n"
                "IP Address: %s\n", upnp.serial, upnp.uuid, upnp.model_id,
                upnp.version, upnp.ipaddr)

    if options.auth_only:
        return fast_add_trust(upnp, logger)
    else:
        run_commands(upnp, logger)


if __name__ == "__main__":
    sys.exit(main())

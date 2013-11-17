"""
storlever.mngr.network.netif
~~~~~~~~~~~~~~~~

This module implements the class of network interface

:copyright: (c) 2013 by jk.
:license: GPLv3, see LICENSE for more details.

"""

import time
import os

from storlever.lib.command import check_output
from storlever.lib.exception import StorLeverError
from storlever.lib import logger
import logging
import ifconfig
from storlever.lib.confparse import properties


IFUP = "/sbin/ifup"
IFDOWN = "/sbin/ifdown"
IF_CONF_PATH = "/etc/sysconfig/network-scripts/"


class EthInterface(object):
    """contains all methods to manage the user and group in linux system"""

    def __init__(self, name, ifconfig_interface):

        self.name = name
        ifcfg_file_name = "ifcfg-" + name
        self.conf_file_path = os.path.join(IF_CONF_PATH, ifcfg_file_name)

        # get the config file
        if os.path.exists(self.conf_file_path):
            self.conf = properties(self.conf_file_path)
        else:
            # create default if no config file
            ip = ifconfig_interface.ip
            mac = ifconfig_interface.mac
            netmask = ifconfig_interface.netmask
            up = ifconfig_interface.is_up()
            if up:
                onboot = "yes"
            else:
                onboot = "no"
            self.conf = properties(IPADDR=ip, NETMASK=netmask,
                                   HWADDR=mac, ONBOOT=onboot)

        # get the interface state object
        self.ifconfig_interface = ifconfig_interface

    def get_ip_config(self):
        ip = self.conf.get("IPADDR", "")
        netmask = self.conf.get("NETMASK", "")
        gateway = self.conf.get("GATEWAY", "")
        return ip, netmask, gateway

    def get_mac(self):
        if self.ifconfig_interface is not None:
            return self.ifconfig_interface.get_mac()
        else:
            return self.conf.get("HWADDR", "00:00:00:00:00:00")

    def set_ip_config(self, ip="", netmask="", gateway="", user="unknown"):
        self.conf["IPADDR"] = ip
        self.conf["NETMASK"] = netmask
        self.conf["GATEWAY"] = gateway

        # write to config file
        self.conf.apply_to(self.conf_file_path)

        # restart this interface
        if self.ifconfig_interface is not None and \
                self.ifconfig_interface.is_up():

            check_output([IFDOWN, self.name])
            check_output([IFUP, self.name])

        # log the operation
        logger.log(logging.INFO, logger.LOG_TYPE_CONFIG,
                   "Network interface (%s) is configured with (IP:%s, Netmask:%s, \
                 Gateway:%s) by user(%s)" %
                   (self.name, ip, netmask, gateway, user))

    def up(self, user="unknown"):
        if self.ifconfig_interface is None:
            raise StorLeverError("Interface(%s) is invalid" % self.name, 400)

        self.conf["ONBOOT"] = "yes"
        self.conf.apply_to(self.conf_file_path)
        self.ifconfig_interface.up()

        # log the operation
        logger.log(logging.INFO, logger.LOG_TYPE_CONFIG,
                   "Network interface (%s) is up by user(%s)" %
                   (self.name, user))

    def down(self, user="unknown"):
        if self.ifconfig_interface is None:
            raise StorLeverError("Interface(%s) is invalid" % self.name, 400)

        self.conf["ONBOOT"] = "no"
        self.conf.apply_to(self.conf_file_path)
        self.ifconfig_interface.down()

        # log the operation
        logger.log(logging.INFO, logger.LOG_TYPE_CONFIG,
                   "Network interface (%s) is up by user(%s)" %
                   (self.name, user))

    def get_state_info(self):
        """return the current state of the net interface

        This function would return a dict include the following keys:
        "valid"  Bool this interface is valid or not, if a interface does not
                  exist in system but has a config file, it's considered to
                  be invalid. When it's invalid, all the other fileds in
                  the return dict has no sense.
        "up"  Bool    This interface is up in system or not
        "speed"  Int the speed the current link, if the link is down, it's 0
        "duplex" Bool the current link is duplex or not
        "auto"  Bool the interface support auto-negotiation or not
        "link_up" Bool the link is up or down
        "is_master" Bool this interface is the master of a bond group

        """
        state = {
            "vaild": False,
            "up": False,
            "speed": 0,
            "duplex": False,
            "auto": False,
            "link_up": False,
            "is_master": False
        }

        if self.ifconfig_interface is not None:
            state["valid"] = True
            state["up"] = self.ifconfig_interface.is_up()
            state["is_master"] = self.ifconfig_interface.is_master()
            state["speed"], state["duplex"], state["auto"], state["link_up"] = \
                self.ifconfig_interface.get_link_info()

        return state

    def get_statistic_info(self):
        # get timestamp
        now = time.time()
        # if valid, get the statistic from system, or return a fake
        if self.ifconfig_interface is not None:
            stat = self.ifconfig_interface.get_stats()
        else:
            stat = {"rx_bytes":0, "rx_packets":0, "rx_errs":0, "rx_drop":0,
                    "rx_fifo":0, "rx_frame":0, "rx_compressed":0,
                    "rx_multicast":0, "tx_bytes":0, "tx_packets":0,
                    "tx_errs":0, "tx_drop":0, "tx_fifo":0, "tx_colls":0,
                    "tx_carrier":0, "tx_compressed":0}

        stat["time"] = now

        return stat



"""
storlever.mngr.network.dnsmgr
~~~~~~~~~~~~~~~~

This module implements some functions of DNS for linux network.

:copyright: (c) 2013 by jk.
:license: GPLv3, see LICENSE for more details.

"""


from storlever.lib.lock import lock
from storlever.mngr.system.cfgmgr import cfg_mgr
from storlever.lib import logger
import logging
from storlever.lib.exception import StorLeverError

RESOLVE_FILE = "/etc/resolv.conf"


class DnsManager(object):
    """contains all methods to manage dns configure"""

    def __init__(self):
        # need a mutex to protect name servers config
        self.lock = lock()

    def get_name_servers(self):
        # read the file
        servers = []
        with self.lock:
            with open(RESOLVE_FILE, "r") as config_file:
                lines = config_file.readlines();

        storlever_begin = False
        for line in lines:
            if "# begin storlever\n" in line:
                storlever_begin = True
            elif "# end storlever\n" in line:
                storlever_begin = False
            elif storlever_begin:
                line_part = line.split()
                if line_part[0] == "nameserver":
                    servers.append(line_part[1])

        return servers

    def set_name_servers(self, servers, user="unknown"):

        if not isinstance(servers, list):
            raise StorLeverError("servers must be type of list", 400)

        with self.lock:
            with open(RESOLVE_FILE, "r") as f:
                lines = f.readlines()

        if "# begin storlever\n" in lines:
            before_storlever = lines[0:lines.index("# begin storlever\n")]
        else:
            before_storlever = lines[0:-1]
            if not before_storlever[-1].endswith("\n"):
                before_storlever[-1] += "\n"

        if "# end storlever\n" in lines:
            after_storlever = lines[lines.index("# end storlever\n") + 1:-1]
        else:
            after_storlever = []

        with self.lock:
            with open(RESOLVE_FILE, "w") as f:
                f.writelines(before_storlever)
                f.write("# begin storlever\n")
                for server_ip in servers:
                    f.write("nameserver %s\n" % server_ip)
                f.write("# end storlever\n")
                f.writelines(after_storlever)

        # log the operation
        logger.log(logging.INFO, logger.LOG_TYPE_CONFIG,
                   "Network DNS name server list is updated by user(%s)" %
                   (user))

def dns_mgr():
    """return the global user manager instance"""
    return DnsManager

DnsManager = DnsManager()

# register cfg file
cfg_mgr().register_config_file(RESOLVE_FILE)









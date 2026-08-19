import logging
import os
import random

logger = logging.getLogger(__name__)


class ProxyGetter:
    def __init__(self, proxy_file_name="proxy_list.txt"):
        self.proxy_list = []
        if os.path.isabs(proxy_file_name):
            self.pathed_file_name = proxy_file_name
        else:
            self.pathed_file_name = os.path.join(os.getcwd(), "proxy", proxy_file_name)
        self.build_proxy_list()

    def build_proxy_list(self):
        try:
            if not os.path.exists(self.pathed_file_name):
                print(f"Proxy file not found: {self.pathed_file_name}")
                print("Running without proxies (direct connection).")
                return
            if self.pathed_file_name.endswith(".txt"):
                self.build_proxy_list_txt()
            else:
                print("File type not supported")
        except Exception as e:
            logger.exception(e)
            print(f"Warning: Could not load proxies from {self.pathed_file_name}. Running without proxies.")

    def build_proxy_list_txt(self):
        with open(self.pathed_file_name, "r") as fp:
            proxy_list = [line.strip() for line in fp if line.strip()]

        for proxy in proxy_list:
            proxy_parts = proxy.split(":")
            if len(proxy_parts) == 4:
                ip, port, username, password = proxy_parts
                if username.lower() != "username":
                    self.proxy_list.append(
                        {
                            "server": f"http://{ip}:{port}",
                            "username": username,
                            "password": password,
                        }
                    )
                else:
                    logger.warning(f"Skipping proxy with placeholder username: {proxy}")
            elif len(proxy_parts) == 2:
                ip, port = proxy_parts
                self.proxy_list.append(
                    {
                        "server": f"http://{ip}:{port}",
                        "username": "",
                        "password": "",
                    }
                )
            else:
                logger.warning(f"Invalid proxy format: {proxy}")

    def get_proxy_as_dict(self) -> dict:
        if not self.proxy_list:
            return {}

        proxy = self.proxy_list.pop(-1)
        self.proxy_list.insert(0, proxy)
        return proxy

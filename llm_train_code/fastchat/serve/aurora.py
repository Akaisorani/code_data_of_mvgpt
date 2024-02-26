import json

import requests


class AuroraClient:
    def __init__(self):
        self.env = "pre"
        self.request_path = ""
        self.base_url = ""

    def doPost(self, full_url, headers, param_dict):
        if full_url is None or full_url == '':
            full_url = self.base_url + "/" + self.request_path
        response = requests.post(full_url, data=json.dumps(param_dict, ensure_ascii=False).encode("utf8"), headers=headers)
        return response

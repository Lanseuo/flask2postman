from __future__ import print_function

import re
from time import time
from uuid import uuid4

from flask2postman.utils import trim, var_re

methods_order = ["GET", "POST", "PUT", "PATCH", "DELETE", "COPY", "HEAD",
                 "OPTIONS", "LINK", "UNLINK", "PURGE"]


def get_time():
    return int(round(time() * 1000))


class Collection:
    def __init__(self, name, base_url, all, static, add_folders):
        self._folders = []
        self._requests = []

        self.name = name
        self.base_url = base_url
        self.all = all
        self.static = static
        self.static = static
        self.add_folders = add_folders

        self.id = str(uuid4())
        self.timestamp = get_time()

    @classmethod
    def from_flask(cls, name, base_url, all, static, add_folders, current_app):
        collection = cls(name, base_url, all, static, add_folders)

        for rule in current_app.url_map.iter_rules():
            if rule.endpoint == "static" and not static:
                continue

            folder = None
            if add_folders:
                try:
                    blueprint_name, _ = rule.endpoint.split('.', 1)
                except ValueError:
                    pass
                else:
                    folder = collection.get_folder(blueprint_name)

            endpoint = current_app.view_functions[rule.endpoint]
            description = trim(endpoint.__doc__)

            for method in rule.methods:
                if method in ["OPTIONS", "HEAD"] and not all:
                    continue

                request = Request.from_werkzeug(rule, method, base_url)
                request.description = description
                if collection.folders and folder:
                    folder.add_request(request)
                collection.add_request(request)

        return collection

    def reorder_requests(self):
        def _get_key(request):
            return str(methods_order.index(request.method)) + request.name
        self._requests = sorted(self._requests, key=_get_key)

    def add_folder(self, folder):
        folder.collection_id = self.id
        self._folders.append(folder)

    def find_folder(self, name):
        for folder in self._folders:
            if folder.name == name:
                return folder

    def get_folder(self, name):
        folder = self.find_folder(name)
        if not folder:
            folder = Folder(name)
            self.add_folder(folder)
        return folder

    def add_request(self, request):
        request.collection_id = self.id
        self._requests.append(request)
        self.reorder_requests()

    @property
    def order(self):
        return [request.id for request in self._requests if not request._folder]

    @property
    def requests(self):
        return [request.to_dict() for request in self._requests]

    @property
    def folders(self):
        return [folder.to_dict() for folder in self._folders]

    def to_dict(self):
        d = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        d.update(requests=self.requests, order=self.order, folders=self.folders)
        return d


class Folder:
    def __init__(self, name):
        self._requests = []

        self.id = str(uuid4())
        self.name = name

    def reorder_requests(self):
        def _get_key(request):
            return str(methods_order.index(request.method)) + request.name
        self._requests = sorted(self._requests, key=_get_key)

    def add_request(self, request):
        request._folder = self
        self._requests.append(request)
        self.reorder_requests()

    @property
    def order(self):
        return [request.id for request in self._requests]

    def to_dict(self):
        d = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        d["collectionId"] = d.pop("collection_id")
        d.update(order=self.order)
        return d


class Request:
    def __init__(self, name, url, method, collection_id="", data=None,
                 data_mode="params", description="", headers=""):
        self._folder = None

        self.id = str(uuid4())
        self.collection_id = collection_id
        self.data = data
        if self.data is None:
            self.data = []
        self.data_mode = data_mode
        self.description = description
        self.headers = headers
        self.method = method
        self.name = name
        self.time = get_time()
        self.url = url

    def to_dict(self):
        d = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        d["collectionId"] = d.pop("collection_id")
        d["dataMode"] = d.pop("data_mode")
        return d

    @classmethod
    def from_werkzeug(cls, rule, method, base_url):
        name = rule.endpoint.rsplit('.', 1)[-1]
        name = name.split("_", 1)[-1]
        name = name.replace("_", " ")

        url = base_url + rule.rule
        for match in re.finditer(var_re, url):
            var = match.group("var")
            var_name = "{{" + match.group("var_name") + "}}"
            url = url.replace(var, var_name)
        return cls(name, url, method)

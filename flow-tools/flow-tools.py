#!/usr/bin/env python
# encoding: utf-8
#
#    Copyright (c) 2013-2014+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2013-2014 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    Cocaine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import cStringIO
import uuid

import msgpack

from cocaine.services import Service
from cocaine.asio.service import Locator
from cocaine.worker import Worker
from cocaine.asio.engine import asynchronous
from cocaine.logging import Logger
from cocaine.tools.actions import profile
from cocaine.tools.actions import runlist
from cocaine.tools.actions import group
from cocaine.tools.actions import crashlog
from cocaine.tools.actions import app


from userdb import UserDB
from hostdb import HostDB
from nodecluster import NodeCluster

ITEM_IS_ABSENT = -100
VERSION_DELEMITER = "_"

log = Logger()
storage = Service("storage")
locator = Locator()

LOGS_NAMESPACE = "flow_upload_logs"
HOSTS_NAMESPACE = "flow_hosts"
db = UserDB(storage, "KEY", "flow_users")
hostdb = HostDB(storage, HOSTS_NAMESPACE)


class UploadLog(object):
    def __init__(self, depth=10, on_flush=None):
        self.current = list()
        self.buffer = cStringIO.StringIO()
        self.depth = depth
        self.on_flush = on_flush

    def write(self, value):

        self.current.append("%s\n" % value)
        if len(self.current) >= self.depth:
            self.flush()

    def flush(self):
        data = ''.join(self.current)
        self.buffer.write(data)
        self.current = list()
        if self.on_flush is not None:
            self.on_flush(data)

    def getall(self):
        return self.buffer.getvalue()


def unpacker(decoder):
    def dec(func):
        def wrapper(request, response):
            raw_req = yield request.read()
            decoded_req = decoder(raw_req)
            yield func(decoded_req, response)
        return wrapper
    return dec


def appname_to_name_version(appname):
    """Convert appname to name and version"""
    try:
        name, version = appname.rsplit(VERSION_DELEMITER, 1)
    except ValueError:
        log.error("%s is incorrect" % appname)
    return name, version


def appname_from_name_version(name, version):
    """Generate appname from name and version"""
    return "%s_%s" % (name, version)


# profiles
@unpacker(msgpack.unpackb)
@asynchronous
def profile_read(name, response):
    try:
        pf = yield profile.View(storage, name).execute()
        response.write(pf)
    except Exception as err:
        log.error(str(err))
        response.error(ITEM_IS_ABSENT, "Profile %s is missing" % name)
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def profile_list(_, response):
    try:
        pf = yield profile.List(storage).execute()
        log.info("Profiles %s" % str(pf))
        response.write(pf)
    except Exception as err:
        log.error(str(err))
        response.error(ITEM_IS_ABSENT, "Unable to list profiles")
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def profile_remove(name, response):
    try:
        yield profile.Remove(storage, name).execute()
    except Exception as err:
        log.error(str(err))
        response.error(ITEM_IS_ABSENT, "Unable to remove profile")
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def profile_upload(task, response):
    try:
        profilename = task["profilename"]
        profilebody = task["profile"]
        yield profile.Upload(storage, profilename, profilebody).execute()
    except Exception as err:
        log.error("Unable to upload profile %s" % err)
        response.error(-99, "Unable to upload profile %s" % err)
    finally:
        response.close()


# runlist
@unpacker(msgpack.unpackb)
@asynchronous
def runlist_read(name, response):
    try:
        pf = yield runlist.View(storage, name).execute()
        response.write(pf)
    except Exception as err:
        log.error(str(err))
        response.error(ITEM_IS_ABSENT, "Runlist %s is missing" % name)
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def runlist_list(_, response):
    try:
        pf = yield runlist.List(storage).execute()
        response.write(pf)
    except Exception as err:
        log.error(str(err))
        response.error(ITEM_IS_ABSENT, "Unable to list runlists")
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def runlist_remove(name, response):
    try:
        yield runlist.Remove(storage, name).execute()
    except Exception as err:
        log.error(str(err))
        response.error(ITEM_IS_ABSENT, "Runlist %s is missing" % name)
    finally:
        response.close()


# hosts

@unpacker(msgpack.unpackb)
@asynchronous
def host_list(_, response):
    try:
        # hosts = yield storage.find(HOSTS_NAMESPACE, HOSTS_TAG)
        hosts = yield hostdb.hosts()
        response.write(hosts)
    except Exception as err:
        log.error(str(err))
        response.error(ITEM_IS_ABSENT, "Unable to read hosts")
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def host_add(name, response):
    try:
        # yield storage.write(HOSTS_NAMESPACE, name, name, HOSTS_TAG)
        yield hostdb.add(name)
    except Exception as err:
        log.error(str(err))
        response.error(ITEM_IS_ABSENT, "Unable to write host")
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def host_remove(name, response):
    try:
        # yield storage.remove(HOSTS_NAMESPACE, name)
        yield hostdb.remove(name)
    except Exception as err:
        log.error(str(err))
        response.error(ITEM_IS_ABSENT, "Unable to remove host")
    finally:
        response.close()


# groups
@unpacker(msgpack.unpackb)
@asynchronous
def group_list(_, response):
    try:
        groups = yield group.List(storage).execute()
        response.write(groups)
    except Exception as err:
        log.error(repr(err))
        response.error(-100, "Unable to read groups")
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def group_create(name, response):
    try:
        yield group.Create(storage, name).execute()
    except Exception as err:
        log.error(repr(err))
        response.error(-100, "Unable to read groups")
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def group_read(name, response):
    try:
        gcontent = yield group.View(storage, name).execute()
        response.write(gcontent)
    except Exception as err:
        log.error(repr(err))
        response.error(-100, "Unable to read groups")
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def group_remove(name, response):
    try:
        yield group.Remove(storage, name).execute()
    except Exception as err:
        log.error(repr(err))
        response.error(-100, "Unable to read groups")
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def group_pushapp(info, response):
    log.info(str(info))
    name = info["name"]
    appname = info["app"]
    weight = int(info["weight"])
    log.info(str(info))
    try:
        yield group.AddApplication(storage, name, appname, weight).execute()
    except Exception as err:
        log.error(repr(err))
        response.error(-100, "Unable to push app %s" % name)
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def group_popapp(info, response):
    name = info["name"]
    appname = info["app"]
    try:
        yield group.RemoveApplication(storage, name, appname).execute()
    except Exception as err:
        log.error(repr(err))
        response.error(-100, "Unable to pop app")
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def group_refresh(name, response):
    try:
        hosts = yield hostdb.hosts()
        for host in hosts:
            l = Locator()
            l.connect(host, 10053, 120, True)
            yield group.Refresh(l, storage, name).execute()
    except Exception as err:
        log.error(repr(err))
        response.error(-100, "Unable to refresh %s" % err)
    finally:
        response.close()


# crashlogs
@unpacker(msgpack.unpackb)
@asynchronous
def crashlog_list(name, response):
    try:
        crashlogs = yield crashlog.List(storage, name).execute()
    except Exception as err:
        log.error(repr(err))
        response.error(-100, "Unknown error")
    else:
        response.write(crashlogs)
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def crashlog_view(info, response):
    try:
        name = info['name']
        timestamp = info['timestamp']
        data = yield crashlog.View(storage, name, timestamp).execute()
        encoded = msgpack.unpackb(data)
    except Exception as err:
        log.error(repr(err))
        response.error(-100, "Unknown error %s" % err)
    else:
        response.write(encoded)
    finally:
        response.close()


# Users
@unpacker(msgpack.unpackb)
@asynchronous
def user_exists(name, response):
    r = yield db.exists(name)
    response.write(r)
    response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def user_signup(info, response):
    r = yield db.create(info)
    response.write(r)
    response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def user_signin(info, response):
    try:
        name = info['name']
        password = info['password']
        r = yield db.login(name, password)
        response.write(r)
    except KeyError as err:
        response.error(-100, "Parametr %s is missing" % repr(err))
    except Exception as err:
        response.error(-99, "Unknown error %s" % repr(err))
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def user_remove(name, response):
    yield db.remove(name)
    response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def user_list(_, response):
    users = yield db.users()
    response.write(users)
    response.close()


# apps
@unpacker(msgpack.unpackb)
@asynchronous
def user_upload(info, response):
    upload_ID = uuid.uuid4().hex
    response.write("%s\n" % upload_ID)
    try:
        user = info["user"]
        appname = appname_from_name_version(info["app"], info["version"])
        path = info["path"]
        docker = info["docker"]
        registry = info["registry"]

        buildlog = UploadLog(depth=5, on_flush=response.write)
        buildlog.write("User %s, app %s, id %s\n" % (user,
                                                     appname,
                                                     upload_ID))

        try:
            user_exists = yield db.exists(user)
            if not user_exists:
                raise ValueError("User %s doesn't exist" % user)

            apps = yield app.List(storage).execute()
            if appname in apps:
                log.error("App %s already exists" % appname)
                raise ValueError("App %s already exists" % appname)

            uploader = app.DockerUpload(storage, path,
                                        appname, None,
                                        docker, registry,
                                        on_read=buildlog.write)
            yield uploader.execute()
            yield db.write_app_info(user, appname)
        except Exception as err:
            buildlog.write("Error: %s\n" % str(err))
            raise err
        finally:
            buildlog.flush()
            logdata = buildlog.getall()
            log.debug("Saving uploadlog into storage")
            yield db.write_buildlog(user, upload_ID, logdata)
            log.debug("Uploadlog has been saved successfully")
        response.write("Done")
    except KeyError as err:
        response.error(-500, "Missing argument %s" % str(err))
    except Exception as err:
        log.error(repr(err))
        response.error(-100, repr(err))
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def user_apps_list(username, response):
    def output(appname):
        try:
            n, v = appname_to_name_version(appname)
            return {"name": n, "version": v}
        except ValueError:
            return None

    all_apps = yield app.List(storage).execute()
    user_apps = yield db.user_apps(username)

    set_all_apps = frozenset(all_apps)
    set_user_apps = frozenset(user_apps)

    res = None
    if set_user_apps.issubset(set_all_apps):
        res = user_apps
    else:
        diff = set_user_apps.difference(set_all_apps)
        log.error("Application info is inconsistent %s" % ' '.join(diff))

        inter = set_user_apps.intersection(set_all_apps)
        res = inter

    response.write(filter(lambda x: x is not None,
                          map(output, res)))
    response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def user_buildlog_list(username, response):
    try:
        keys = yield db.list_buildlog(username)
        response.write(keys)
    except Exception as err:
        log.error(str(err))
        response.error(-100, repr(err))
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def user_buildlog_read(key, response):
    try:
        data = yield db.read_buildlog(key)
        response.write(data)
    except Exception as err:
        log.error(str(err))
        response.error(-100, repr(err))
    finally:
        response.close()


# apps

@unpacker(msgpack.unpackb)
@asynchronous
def app_info(task, response):
    info = dict()
    try:
        name = task["appname"]
        version = task["version"]
        username = task["username"]
        # todo: without version - search by mask? regex?
        appname = appname_from_name_version(name, version)

        if username:
            # not admin - all apps
            user_apps = yield app.List(storage).execute()
        else:
            user_apps = yield db.user_apps(username)

        if appname not in user_apps:
            raise ValueError("App %s doesn't exist" % appname)

        hosts = yield hostdb.hosts()
        for host in hosts:
            appinstance = None
            try:
                appinstance = Service(appname, blockingConnect=False)
                yield appinstance.connect(host=host)
                info[host] = yield appinstance.info()
            except Exception as err:
                log.error("Unable to connect to app %s host %s" % (appname,
                                                                   host))
            finally:
                if appinstance is not None:
                    appinstance.disconnect()
    except KeyError as err:
        response.error(-500, "Missing argument %s" % str(err))
    except Exception as err:
        log.error("Unknown error %s" % repr(err))
        response.error(-100, "Unknown error %s" % repr(err))
    else:
        response.write(info)
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def app_deploy(task, response):
    s = list()
    f = list()
    try:
        name = task["appname"]
        version = task['version']
        appname = appname_from_name_version(name, version)
        profilename = task["profile"]
        runlistname = task["runlist"]
        weight = task.get("weight", 0)

        # get routing groups
        groups = yield group.List(storage).execute()
        if name not in groups:
            log.info("Create routing group %s" % name)
            # create routing group for given application
            yield group.Create(storage, name).execute()
        # add application into routing group
        log.info("Add %s to groups %s with weight %d" % (appname,
                                                         name,
                                                         weight))
        yield group.AddApplication(storage, name, appname, weight).execute()

        log.info("Add %s to runlist %s" % (appname, runlistname))
        yield runlist.AddApplication(storage,
                                     runlistname,
                                     appname,
                                     profilename, force=True).execute()
        hosts = yield hostdb.hosts()
        cluster = NodeCluster(hosts, response.write)
        (s, f) = yield cluster.start_app(appname, profilename)
    except Exception as err:
        log.error("Unknown error %s" % repr(err))
        response.error(-100, "Unknown error %s" % repr(err))
    else:
        response.write("Done")
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def app_stop(task, response):
    s = list()
    f = list()
    try:
        name = task["appname"]
        version = task["version"]
        appname = appname_from_name_version(name, version)
        hosts = yield hostdb.hosts()
        cluster = NodeCluster(hosts, response.write)
        (s, f) = yield cluster.stop_app(appname)
    except Exception as err:
        log.error("Unknown error %s" % repr(err))
        response.error(-100, "Unknown error %s" % repr(err))
    else:
        response.write("Done %d/%d" % (len(s), len(f)))
    finally:
        response.close()


@unpacker(msgpack.unpackb)
@asynchronous
def app_start(task, response):
    s = list()
    f = list()
    try:
        name = task["appname"]
        profilename = task["profile"]
        version = task["version"]
        appname = appname_from_name_version(name, version)
        hosts = yield hostdb.hosts()
        cluster = NodeCluster(hosts, response.write)
        (s, f) = yield cluster.start_app(appname, profilename)
    except Exception as err:
        log.error("Unknown error %s" % repr(err))
        response.error(-100, "Unknown error %s" % repr(err))
    else:
        response.write("Done %d/%d" % (len(s), len(f)))
    finally:
        response.close()


binds = {
    # profiles
    "profile-read": profile_read,
    "profile-list": profile_list,
    "profile-remove": profile_remove,
    "profile-upload": profile_upload,
    # runlists
    "runlist-read": runlist_read,
    "runlist-list": runlist_list,
    "runlist-remove": runlist_remove,
    # hosts
    "host-add": host_add,
    "host-list": host_list,
    "host-remove": host_remove,
    # groups
    "group-list": group_list,
    "group-create": group_create,
    "group-read": group_read,
    "group-remove": group_remove,
    "group-pushapp": group_pushapp,
    "group-popapp": group_popapp,
    "group-refresh": group_refresh,
    # crashlogs
    "crashlog-list": crashlog_list,
    "crashlog-view": crashlog_view,
    # users
    "user-exists": user_exists,
    "user-signup": user_signup,
    "user-signin": user_signin,
    "user-remove": user_remove,
    "user-list": user_list,
    "user-upload": user_upload,
    "user-app-list": user_apps_list,
    "user-buildlog-list": user_buildlog_list,
    "user-buildlog-read": user_buildlog_read,
    # app
    "app-info": app_info,
    "app-deploy": app_deploy,
    "app-start": app_start,
    "app-stop": app_stop,
}

API = {"Version": 1,
       "Methods": binds.keys()}


def api(request, response):
    yield request.read()
    response.write(API)
    response.close()

if __name__ == '__main__':
    W = Worker()
    W.on("API", api)
    W.run(binds)

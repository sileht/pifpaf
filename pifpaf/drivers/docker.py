# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import shlex

from pifpaf import drivers


PORT_REGEX = re.compile(
    r'(?P<bind>[^:]*):(?P<published>[^-]*)->(?P<exposed>[^/]*)/(?P<type>.*)'
)


class DockerDriver(drivers.Driver):

    DEFAULT_IMAGE = ""
    DEFAULT_ARGS = ""

    @classmethod
    def get_options(cls):
        return [
            {"param_decls": ["--image"],
             "default": cls.DEFAULT_IMAGE,
             "help": "image to use"},
            {"param_decls": ["--args"],
             "default": cls.DEFAULT_ARGS,
             "help": "args to pass to the docker image"},
        ]

    def __init__(self, image=DEFAULT_IMAGE, args=DEFAULT_ARGS, **kwargs):
        """Spawn a docker instance."""
        super(DockerDriver, self).__init__(**kwargs)
        self.image = image
        self.args = shlex.split(args)

    def _setUp(self):
        super(DockerDriver, self)._setUp()
        self.putenv("IMAGE", self.image)

        _, stdout = self._exec(
            ["docker", "run", "-d", "-P", "--rm", self.image] + self.args,
            stdout=True
        )
        self.container_id = stdout.decode().strip()
        self.addCleanup(self._exec, ["docker", "stop", self.container_id])

        self.putenv("CONTAINER_ID", self.container_id)

        _, stdout = self._exec([
            "docker", "ps",
            "-f", "id=%s" % self.container_id,
            "--format={{.Ports}}"
        ], stdout=True)
        self.ports = stdout.decode()
        self.putenv("CONTAINER_PORTS", self.ports)

        # NOTE(sileht): ports looks like:
        # 0.0.0.0:32808->8300/tcp, 0.0.0.0:32791->8301/udp,
        # 0.0.0.0:32807->8301/tcp

        m = None
        for i, raw_port in reversed(list(enumerate(self.ports.split(',')))):
            raw_port = raw_port.strip()
            m = PORT_REGEX.match(raw_port)
            if m:
                setattr(self, "port_%d" % i, m.group("published"))
                self.putenv("DOCKER_RAW_PORT_%d" % i, raw_port)
                self.putenv("DOCKER_PORT_TYPE_%d" % i, m.group("type"))
                self.putenv("DOCKER_BIND_%d" % i, m.group("bind"))
                self.putenv("DOCKER_PORT_EXPOSED_%d" % i, m.group("exposed"))
                self.putenv("DOCKER_PORT_%d" % i, m.group("published"))
        if m:
            self.port = m.group("published")
            self.url = "docker://%s:%s/" % (
                m.group('bind'), m.group("published")
            )
            self.putenv("DOCKER_RAW_PORT", raw_port)
            self.putenv("DOCKER_BIND", m.group("bind"))
            self.putenv("DOCKER_PORT_TYPE", m.group("type"))
            self.putenv("DOCKER_PORT_EXPOSED", m.group("exposed"))
            self.putenv("DOCKER_PORT", m.group("published"))
            self.putenv("URL", self.url)

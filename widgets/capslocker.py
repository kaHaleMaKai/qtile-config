# -*- coding: utf-8 -*-
# Copyright (C) 2018 Juan Riquelme González
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from libqtile.widget import base

import re
import subprocess
import notify2


class CapsLockIndicator(base.ThreadPoolText):
    """Really simple widget to show the current Caps Lock state."""

    orientations = base.ORIENTATION_HORIZONTAL
    defaults = [('update_interval', 0.5, 'Update Time in seconds.')]

    def __init__(self, **config):
        base.ThreadPoolText.__init__(self, "", **config)
        self.add_defaults(self.defaults)
        self.lock_msg = "| A⇬ |"
        self.is_locked = None
        self.notification = notify2.Notification("Caps_Lock on", self.lock_msg)
        self.notification.timeout = -1
        self.notification.urgency = notify2.URGENCY_CRITICAL

    def get_state(self):
        """Return a list with the current state of the keys."""
        try:
            output = self.call_process(['xset', 'q'])
        except subprocess.CalledProcessError as err:
            output = err.output.decode()
        if not output.startswith("Keyboard"):
            return
        m = re.search(r"Caps\s+Lock:\s*(?P<state>\w*)", output)
        if not m:
            return
        return m.groupdict()["state"] == "on"

    def poll(self):
        """Poll content for the text box."""
        new_state = self.get_state()
        if self.is_locked != new_state:
            if new_state:
                self.notification.show()
            else:
                self.notification.close()
        self.is_locked = new_state
        if new_state:
            return self.lock_msg
        else:
            return ""

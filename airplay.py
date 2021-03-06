# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 Martin S. <opensuse@sukimashita.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL 
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import gi
from gi.repository import GObject
from gi.repository import Gio
gi.require_version('Totem','1.0')
from gi.repository import Totem
gi.require_version('Peas','1.0')
from gi.repository import Peas

import sys
import platform
import time
from AirPlayService import AirPlayService

def _get_dbus_proxy():
	return Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SESSION,
		Gio.DBusProxyFlags.NONE, None,
		"org.freedesktop.DBus",
		"/org/freedesktop/DBus",
		"org.freedesktop.DBus", None)

class AirPlayPlugin (GObject.GObject, Peas.Activatable):
	__gobject_name__ = 'AirPlayPlugin'
	
	object = GObject.property(type = GObject.GObject)

	def __init__ (self):
		self.totem = None

	def do_activate (self):
		self.monitor_bus()
		try:
			self.construct()
		except:
			print >> sys.stderr, "Failed activating airplay"
			return
		

	def monitor_bus(self):
		dbusobj = _get_dbus_proxy()
		dbusobj.connect("g-signal", self.on_dbus_signal)
	
	def on_dbus_signal(self, proxy, sender_name, signal_name, params):
		if signal_name == "NameOwnerChanged":
			name, old_owner, new_owner = params.unpack()
			if name == DBUS_DVB_SERVICE:
				if old_owner == "": 
					self.construct()
				elif new_owner == "": 
					self.deactivate()
	def construct(self):
		self.totem_object = self.object
		self.service = AirPlayTotemPlayer(
		    totem=self.totem_object,
		    name="Totem on %s" % (platform.node()))

	def do_deactivate (self):
		self.service = None

class AirPlayTotemPlayer(AirPlayService):
	def __init__(self, totem, name=None, host="0.0.0.0", port=22555):
		self.location = None
		self.totem = totem
		AirPlayService.__init__(self, name, host, port)

	def __del__(self):
		self.totem.action_stop()
		AirPlayService.__del__(self)

	# this returns current media duration and current seek time
	def get_scrub(self):
		# return self.totem.stream-length, self.totem.current-time
		duration = float(self.totem.get_property('stream-length') / 1000)
		position = float(self.totem.get_property('current-time') / 1000)
		return duration, position

	def is_playing(self):
		return self.totem.is_playing()

	# this must seek to a certain time
	def set_scrub(self, position):
		if self.totem.is_seekable():
			GObject.idle_add(self.totem.action_seek_time, int(float(position) * 1000), False)

	# this only sets the location and start position, it does not yet start to play
	def play(self, location, position):
		# start position is in percent
		self.location	= [location, position]

	# stop the playback completely
	def stop(self, info):
		GObject.idle_add(self.totem.action_stop)

	# reverse HTTP to PTTH
	def reverse(self, info):
		pass

	# playback rate, 0.0 - 1.0
	def rate(self, speed):
		if (int(float(speed)) >= 1):
			if self.location is not None:
				timeout = 5
				# start playback and loading of media
				GObject.idle_add(self.totem.add_to_playlist_and_play, self.location[0], "AirPlay Video", False)
				# wait until stream-length is loaded and is not zero
				duration = 0
				while (int(duration) == 0 and timeout > 0):
					time.sleep(1)
					duration = float(self.totem.get_property('stream-length') / 1000)
					timeout -= 1
				# we also get a start time from the device
				targetoffset = float(duration * float(self.location[1]))
				position = float(self.totem.get_property('current-time') / 1000)
				# only seek to it if it's above current time, since the video is already playing
				if (targetoffset > position):
					self.set_scrub(targetoffset)

			if (not self.totem.is_playing()):
				GObject.idle_add(self.totem.action_play)

			del self.location
			self.location = None
		else:
			GObject.idle_add(self.totem.action_pause)


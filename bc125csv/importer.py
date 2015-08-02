from __future__ import print_function

import re
import csv
import sys
import string

from bc125csv.scanner import CTCSS_TONES, DCS_CODES, Channel


class ParseError(Exception):
	pass


class Importer(object):
	"""
	Convert CSV data read from a fileobject to channel objects.
	"""

	# Pre-compiled regular expressions
	RE_CTCSS = re.compile(r"^(?:ctcss)?\s*(\d{2,3}\.\d)\s*(?:hz)?$", re.I)
	RE_DCS = re.compile(r"^(?:dcs)?\s*(\d{2,3})$", re.I)
	RE_FREQ = re.compile(r"^(\d{1,4})(\s{0}\.\d+)?\s*(?:mhz)?$", re.I)

	def parse_tq(self, value):
		"""Parse a user-defined CTCSS tone or DCS code."""
		if value in ("", "none", "all"):
			return 0
		if value in ("search",):
			return 127
		if value in ("notone", "no tone"):
			return 240

		match = self.RE_CTCSS.match(value)
		if match:
			ctcss = match.group(1).lstrip("0")
			if ctcss in CTCSS_TONES:
				return CTCSS_TONES.index(ctcss) + 64

		match = self.RE_DCS.match(value)
		if match:
			dcs = match.group(1).zfill(3)
			if dcs in DCS_CODES:
				return DCS_CODES.index(dcs) + 128

	def parse_frequency(self, value):
		"""Converts user-entered frequency to nn.mmmm string format."""
		match = self.RE_FREQ.match(value)
		if match:
			return ".".join((
				match.group(1).lstrip("0"),
				(match.group(2) or "")[:5].lstrip(".").ljust(4, "0")
			))

	def parse_row(self, data):
		"""Parse a csv row to a channel object."""
		# Channel index
		try:
			index = int(data[0])
		except:
			raise ParseError("Invalid channel %s." % data[0])

		if index not in range(1, 501):
			raise ParseError("Invalid channel %d." % index)

		# Name
		valid = string.ascii_letters + string.digits + "!@#$%&*()-/<>.? "
		name = data[1]
		if not all(ch in valid for ch in name):
			raise ParseError("Invalid name %s." % name)

		# Frequency
		frequency = self.parse_frequency(data[2])
		if not frequency:
			raise ParseError("Invalid frequency %s." % data[2])

		# Modulation
		if len(data) > 3 and data[3]:
			modulation = data[3].upper()
			if modulation not in ("FM", "AM", "AUTO", "NFM"):
				raise ParseError("Invalid modulation %s." % modulation)
		else:
			modulation = "AUTO"

		# CTCSS/DCS
		if len(data) > 4 and data[4]:
			tq = self.parse_tq(data[4])
			if tq is None:
				raise ParseError("Invalid CTCSS/DCS %s." % data[4])
		else:
			tq = 0 # none

		# Delay
		if len(data) > 5 and data[5]:
			try:
				delay = int(data[5])
			except:
				raise ParseError("Invalid delay %s." % data[5])

			if delay not in (-10, -5, 0, 1, 2, 3, 4, 5):
				raise ParseError("Invalid delay %d." % delay)
		else:
			delay = 2

		# Lockout
		if len(data) > 6 and data[6]:
			lockout = data[6].lower()
			if lockout in ("0", "no", "false"):
				lockout = False
			elif lockout in ("1", "yes", "true"):
				lockout = True
			else:
				raise ParseError("Invalid lockout %s." % lockout)
		else:
			lockout = False

		# Priority
		if len(data) > 7 and data[7]:
			priority = data[7].lower()
			if priority in ("0", "no", "false"):
				priority = False
			elif priority in ("1", "yes", "true"):
				priority = True
			else:
				raise ParseError("Invalid priority %s." % priority)
		else:
			priority = False

		return Channel(**{
			"index":      index,
			"name":       name,
			"frequency":  frequency,
			"modulation": modulation,
			"tqcode":     tq,
			"delay":      delay,
			"lockout":    lockout,
			"priority":   priority,
		})

	def read(self, fh):
		# Parsed channels
		channels = {}
		# Number of encountered errors
		errors = 0

		def print_error(line, err):
			print("Error on line %d: %s" % (line, err), file=sys.stderr)
		
		# Read csv from fileobject
		csvreader = csv.reader(fh)
		for row, data in enumerate(csvreader):
			# Skip first row (header)
			if not row:
				continue

			# Empty line
			if not data:
				continue

			# Missing required information
			if len(data) < 3:
				continue

			# Trim whitespace
			data = list(map(str.strip, data))

			# Empty channel or comment
			if not data[0] or data[0].startswith("#"):
				continue

			try:
				channel = self.parse_row(data)
			except ParseError as err:
				print_error(row + 1, err)
				errors += 1
				continue

			if channel.index in channels:
				print_error(row + 1, "Channel %d was seen before." % \
					channel.index)
				errors += 1
				continue

			channels[channel.index] = channel

		if not errors:
			return channels

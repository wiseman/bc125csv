from __future__ import print_function

import os
import sys
import argparse

from bc125csv.scanner import Scanner, ScannerStub, DeviceLookup, SUPPORTED_MODELS
from bc125csv.importer import Importer
from bc125csv.exporter import Exporter

VERSION = "bc125csv version 1.0.0 Released Aug 02, 2015"
USAGE = VERSION + """

Copyright (c) 2015, fdev.nl. All rights reserved.
Released under the MIT license.

Uniden and Bearcat are registered trademarks of Uniden 
America Corporation. This application and its author 
are not affiliated with or endorsed by Uniden in any way.

Usage: %%(prog)s ACTION [OPTIONS]
-b, --banks BANKS    Only process given banks.
                     Separate multiple banks with spaces.
-e, --include-empty  Include empty channels in export.
-h, --help           Display this help and exit.
                     Use command help for detailed instructions.
-i, --input FILE     Read from file when importing.
-n, --no-scanner     Use a virtual scanner device.
-o, --output FILE    Write to file when exporting.
-r, --rate           Baud rate (default 9600).
-s, --sparse         Omit 'no' and 'none' values in export.
-v, --verbose        Be more verbose.
-V, --version        Output version information and exit.

Available actions are:
  verify  - Verify csv data (no device needed).
  import  - Import channels to the scanner in csv format.
  export  - Export channels from the scanner in csv format.
  shell   - Start an interactive shell with the device.
  help    - Display detailed help.

Compatible scanners: %(models)s

Disclaimer: While thoroughly tested, this software comes
with absolutely no warranty. Use at your own risk.

""" % dict(models=", ".join(SUPPORTED_MODELS))

HELP = USAGE + """
EXPORT FORMAT

The export format is a comma separated values file with header,
comments and empty lines to improve readability. Empty channels
are omitted by default, but can be included using the --include-empty 
option. Any 'no' and 'none' values in the CTCSS/DCS, Lockout and 
Priority columns can be omitted by using the --sparse option.

Channel,Name,Frequency,Modulation,CTCSS/DCS,Delay,Lockout,Priority

# Bank 1
1,PMR Channel 1,446.0062,FM,none,2,no,no
2,PMR Channel 2,446.0187,FM,no tone,2,no,no
3,Private channel,446.0187,FM,DCS 155,3,no,yes

# Bank 2
51,PMR Channel 3,446.0312,FM,no tone,3,no,no
52,Construction,446.0312,FM,114.8 Hz,1,no,yes
56,Hot Air Balloons,122.2500,AM,none,2,no,no


IMPORT FORMAT

The import format is the same as the export format, but forgiving:

 * CTCSS/DCS, Delay, Lockout and Priority values may be left empty,
 * no, false, 0 and <empty> may be used interchangeably,
 * yes, true and 1 may be used interchangeably,
 * CTCSS tones may be written as 114.8, 114.8Hz, CTCSS 114.8 Hz, etc,
 * DCS codes may be written as 26, 026, DCS026, DCS 026,
 * lines beginning with a '#' (comment line) or ',' (no channel) and 
   the first line (containing the header) are ignored,
 * additional columns are ignored,
 * frequencies are automatically rounded down to 4 decimal places.


SHELL

You can start an interactive shell to send commands to your scanner.
See the BC125AT Operation Specification for all available commands.

$ bc125csv shell
> MDL
< MDL,UBC125XLT
> VER
< VER,Version 1.00.06

You can also pipe commands into your scanner. The following example
enters programming mode, enables the backlight, and then exits
programming mode.


EXAMPLES

Exporting banks 1, 2 and 3:
%(prog)s export -s -b 1 2 3 > banks-123.csv

Importing from csv file:
%(prog)s import < channels.csv

Verify a csv file:
%(prog)s verify -v -i channels.csv

Enable backlight using the shell:
echo -en "PRG\\nBLT,AO\\nEPG" | %(prog)s shell
"""


def create_parser():
	"""Create an argument parser."""

	# Full control over the usage output
	class Usage(argparse.HelpFormatter):
		def format_help(self):
			return USAGE % dict(prog=self._prog)

	# Parse arguments passed by user
	parser = argparse.ArgumentParser(formatter_class=Usage)
	parser.add_argument("command", nargs="?", 
		choices=("verify", "import", "export", "shell", "help"))
	parser.add_argument("-b", "--banks", type=int, dest="banks", nargs="+",
		choices=range(1,11), default=range(1,11))
	parser.add_argument("-e", "--include-empty", action="store_true", 
		dest="empty")
	parser.add_argument("-i", "--input", dest="input")
	parser.add_argument("-n", "--no-scanner", action="store_true", 
		dest="noscanner")
	parser.add_argument("-o", "--output", dest="output")
	parser.add_argument("-r", "--rate", type=int, dest="rate",
		choices=(4800, 9600, 19200, 38400, 57600, 115200), default=9600)
	parser.add_argument("-s", "--sparse", action="store_true", dest="sparse")
	parser.add_argument("-v", "--verbose", action="store_true", dest="verbose")
	parser.add_argument("-V", "--version", action="store_true", dest="version")

	return parser

def main(args=None):
	"""
	Handle a command call.

	Arguments are taken from sys.stdin unless a list of arguments is given.
	"""
	parser = create_parser()
	params = parser.parse_args(args)

	# Output version string
	if params.version:
		print(VERSION)
		sys.exit()

	# No command given, print usage
	if not params.command:
		parser.print_usage()
		sys.exit()

	# Output detailed help
	if params.command == "help":
		print(HELP % dict(prog=parser.prog))
		sys.exit()

	# Helper function: only print with raised verbosity level
	def print_verbose(*args):
		if params.verbose:
			print(*args, file=sys.stderr)

	# Verify command
	if params.command == "verify":
		# Import from file instead of stdin
		if params.input and params.input != "-":
			if not os.path.isfile(params.input):
				sys.exit("Input file does not exist.")
			fh = open(params.input, "r")
		else:
			fh = sys.stdin

		importer = Importer()
		channels = importer.read(fh)

		if channels is None:
			sys.exit("\nThere are errors in your csv data.")

		print_verbose("No errors found.")
		sys.exit()

	# Virtual scanner requested, use a scanner stub
	if params.noscanner:
		print_verbose("Using virtual scanner device.")
		scanner = ScannerStub()

	# Look for a compatible device
	else: # pragma: no cover
		print_verbose("Searching for compatible devices...")

		lookup = DeviceLookup()
		device = lookup.get_device()

		if not device:
			sys.exit("No compatible scanner was found.")

		if not lookup.is_tty(device):
			sys.exit("Found a compatible scanner, but no serial tty.\n"
				"Please run the following commands with root privileges:\n"
				"modprobe usbserial vendor=0x{0} product=0x{1}"
				.format(device.get("ID_VENDOR_ID"), device.get("ID_MODEL_ID")))

		# Make sure device is writable by current user
		if not os.access(device.get("DEVNAME", ""), os.W_OK):
			sys.exit("Found a compatible scanner, but can not write to it.")

		scanner = Scanner(device.get("DEVNAME"), params.rate)

		try:
			model = scanner.get_model()
		except:
			sys.exit("Could not get model name from scanner.\n" 
				"Please try again or reconnect your device.")

		print_verbose("Found scanner", model)


	# Shell command
	if params.command == "shell":
		if isinstance(scanner, ScannerStub):
			print("Not all commands are emulated by the virtual scanner device.", 
				file=sys.stderr)

		# Commands piped into shell
		if not sys.stdin.isatty():
			for cmd in sys.stdin:
				# Strip of whitespace
				cmd = cmd.strip()
				if not cmd:
					continue
				print(scanner.writeread(cmd))
			sys.exit()

		# Enter interactive shell
		print_verbose("Starting interactive shell")
		get_input = input

		# Use raw_input() in Python 2
		if sys.version_info.major == 2: # pragma: no cover
			get_input = raw_input

		while True:
			try:
				cmd = get_input("> ")
			except (EOFError, KeyboardInterrupt):
				break
			print("<", scanner.writeread(cmd))

		print("")
		sys.exit()

	# Import command
	if params.command == "import":
		# Import from file instead of stdin
		if params.input and params.input != "-":
			if not os.path.isfile(params.input):
				sys.exit("Input file does not exist.")
			fh = open(params.input, "r")
		else:
			fh = sys.stdin

		importer = Importer()
		channels = importer.read(fh)
		if channels is None:
			sys.exit("\nThere are errors in your csv data.")

		if scanner.get_model() == "UBC125XLT": # pragma: no cover
			if any(channel.modulation == "NFM" for channel in channels.values()):
				sys.exit("NFM modulation is not supported on your device.")

		print_verbose("Entering programming mode")
		scanner.enter_programming()

		print_verbose("Importing into banks:", " ".join(map(str, params.banks)))

		for bank in params.banks:
			for index in range(bank * 50 - 49, bank * 50 + 1):
				if index in channels:
					channel = channels[index]
					print_verbose("Writing channel %d" % index)
					scanner.set_channel(channel)
				else:
					print_verbose("Deleting channel %d" % index)
					scanner.delete_channel(index)

		print_verbose("Leaving programming mode")
		scanner.exit_programming()


	# Export command
	if params.command == "export":
		# Export to file instead of stdout
		if params.output and params.output != "-":
			try:
				fh = open(params.output, "w")
			except:
				sys.exit("Could not open output file for writing.")
		else:
			fh = sys.stdout

		print_verbose("Entering programming mode")
		scanner.enter_programming()

		print_verbose("Exporting banks:", " ".join(map(str, params.banks)))

		# Get channels from device
		channels = {}
		for bank in params.banks:
			for index in range(bank * 50 - 49, bank * 50 + 1):
				print_verbose("Reading channel %d" % index)

				channel = scanner.get_channel(index)
				if channel or params.empty:
					channels[index] = channel

		print_verbose("Leaving programming mode")
		scanner.exit_programming()

		exporter = Exporter()
		exporter.write(channels, fh, params.sparse)

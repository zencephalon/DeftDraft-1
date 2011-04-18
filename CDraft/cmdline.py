# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# CDraft, a fork of PyRoom.
# Copyright (c) 2007 Nicolas P. Rougier & NoWhereMan
# Copyright (c) 2008 The Pyroom Team - See AUTHORS file for more information
# Copyright (c) 2011 Matthew Bunday
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.
# -----------------------------------------------------------------------------

"""
CDraft - A fork of PyRoom
=============================

Based on code posted on ubuntu forums by NoWhereMan (www.nowhereland.it)
(Ubuntu thread was "WriteRoom/Darkroom/?")

:copyright: 2007 Nicolas P. Rougier & NoWhereMan Copyright
:copyright: 2008 The PyRoom Team - See AUTHORS file for more information
:copyright: 2011 Matthew Bunday
:license: GNU General Public License, version 3 or later
"""

from optparse import OptionParser
import sys

import gtk

import CDraft
from basic_edit import BasicEdit
from cdraft_error import handle_error
from globals import state

__VERSION__ = CDraft.__VERSION__

def main():
    sys.excepthook = handle_error

    files = []

    # Get commandline args
    parser = OptionParser(usage = _('%prog [-v] \
[file1] [file2]...'),
                        version = '%prog ' + __VERSION__,
                        description = _('CDraft lets you edit text files \
simply and efficiently in a full-screen window, with no distractions.'))
    (options, args) = parser.parse_args()
    files = args

    # Create relevant buffers for file and load them
    state['edit_instance'] = BasicEdit()
    buffnum = 0
    if len(files):
        for filename in files:
            state['edit_instance'].open_file_no_chooser(filename)
            buffnum += 1
    else:
        state['edit_instance'].new_buffer()

    state['edit_instance'].set_buffer(buffnum)
    state['edit_instance'].status.set_text(
        _('Welcome to DeftDraft %s, type Alt-H for help.') % __VERSION__
    )
    gtk.main()

if __name__ == '__main__':
    main()

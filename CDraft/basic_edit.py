# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# DeftDraft, a fork of PyRoom.
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
This file provides all basic editor functionality.
"""

import gtk
import os
import urllib

from cdraft_error import CDraftError
from gui import GUI
from preferences import Preferences
import autosave
from globals import state, config

FILE_UNNAMED = _('* Unnamed *')

KEY_BINDINGS = '\n'.join([
    _('Control-H: Show help in a new buffer'),
    _('Control-I: Show buffer information'),
    _('Control-P: Shows Preferences dialog'),
    _('Control-M: Minimize PyRoom'),
    _('Control-N: Create a new buffer'),
    _('Control-O: Open a file in a new buffer'),
    _('Control-Q: Quit'),
    _('Control-S: Save current buffer'),
    _('Control-Shift-S: Save current buffer as'),
    _('Control-W: Close buffer and exit if it was the last buffer'),
    _('Control-Y: Redo last typing'),
    _('Control-Z: Undo last typing'),
    _('Control-Page Up: Switch to previous buffer'),
    _('Control-Page Down: Switch to next buffer'), ])

HELP = \
        _("""CDraft - distraction free writing
Copyright (c) 2007 Nicolas Rougier, NoWhereMan
Copyright (c) 2008 Bruno Bord and the PyRoom team
Copyright (c) 2011 Matthew Bunday

Welcome to CDraft and distraction-free writing.

To hide this help window, press Control-W.

CDraft stays out of your way with formatting options and buttons,
it is largely keyboard controlled, via shortcuts. You can find a list
of available keyboard shortcuts later.

If enabled in preferences, CDraft will save your files automatically every
few minutes.

Commands:
---------
%s

""") % KEY_BINDINGS

def get_likely_chooser_path(buffers, current):
    """determine where the user might want to start browsing open/save dialogs

    takes other buffer filenames into account, returns the closest one"""
    if len(buffers) > 0:
        # search in both directions for named buffers, backwards first
        directions = (
                (range(current, 0, -1)),
                (range(current, len(buffers), 1))
                )
        for direction in directions:
            for buf_num in direction:
                if buffers[buf_num].filename != FILE_UNNAMED:
                    return os.path.dirname(
                            os.path.abspath(
                                buffers[buf_num].filename
                                )
                            )

def dispatch(*args, **kwargs):
    """call the method passed as args[1] without passing other arguments"""
    def eat(accel_group, acceleratable, keyval, modifier):
        """eat all the extra arguments

        this is ugly, but it works with the code we already had
        before we changed to AccelGroup et al"""
        args[0]()
        pass
    return eat

def make_accel_group(edit_instance):
    keybindings = {
            'i': edit_instance.show_info,
            's': edit_instance.commit,
            'z': edit_instance.revert,
            'n': edit_instance.new_buffer,
            'o': edit_instance.open_file,
            'p': edit_instance.preferences.show,
            'q': edit_instance.dialog_quit,
            'w': edit_instance.close_dialog,
            'l': edit_instance.go_next,
            'h': edit_instance.go_prev,
            'j': edit_instance.go_down,
            'k': edit_instance.revert,
            'm': edit_instance.dialog_minimize,
            }
    keybindings2 = {
            'h': edit_instance.show_help,
            's': edit_instance.save_file,
            }
    ag = gtk.AccelGroup()
    for key, value in keybindings.items():
        ag.connect_group(
                ord(key),
                gtk.gdk.CONTROL_MASK,
                gtk.ACCEL_VISIBLE,
                dispatch(value)
                )
        for key, value in keybindings2.items():
            ag.connect_group(
                    ord(key),
                    gtk.gdk.MOD1_MASK,
                    gtk.ACCEL_VISIBLE,
                    dispatch(value)
                    )
            ag.connect_group(
                    ord('s'),
                    gtk.gdk.CONTROL_MASK|gtk.gdk.SHIFT_MASK,
                    gtk.ACCEL_VISIBLE,
                    dispatch(edit_instance.save_file_as)
                    )
            return ag

def define_keybindings(edit_instance):
    """define keybindings, respectively to keyboard layout"""
    keymap = gtk.gdk.keymap_get_default()
    basic_bindings = {
            gtk.keysyms.Page_Up: edit_instance.prev_buffer,
            gtk.keysyms.Page_Down: edit_instance.next_buffer,
            }
    translated_bindings = {}
    for key, value in basic_bindings.items():
        hardware_keycode = keymap.get_entries_for_keyval(key)[0][0]
        translated_bindings[hardware_keycode] = value
    return translated_bindings

class UndoableInsert(object):
    """something that has been inserted into our textbuffer"""
    def __init__(self, text_iter, text, length):
        self.offset = text_iter.get_offset()
        self.text = text
        self.length = length
        if self.length > 1 or self.text in ("\r", "\n", " "):
            self.mergeable = False
        else:
            self.mergeable = True

class UndoableDelete(object):
    """something that has ben deleted from our textbuffer"""
    def __init__(self, text_buffer, start_iter, end_iter):
        self.deleted_text = text_buffer.get_text(start_iter, end_iter)
        self.start = start_iter.get_offset()
        self.end = end_iter.get_offset()
        # need to find out if backspace or delete key has been used
        # so we don't mess up during redo
        insert_iter = text_buffer.get_iter_at_mark(text_buffer.get_insert())
        if insert_iter.get_offset() <= self.start:
            self.delete_key_used = True
        else:
            self.delete_key_used = False
        if self.end - self.start > 1 or self.deleted_text in ("\r", "\n", " "):
            self.mergeable = False
        else:
            self.mergeable = True

class TextSelection:
    def __init__(self, text="", bookmark_start = None):
        self.current = 0
        self.text = [text]
        self.terminal = ""
        self.bookmark_start = bookmark_start.get_offset()

    def get_text():
        text = ""
        for subtext in self.text:
            if type(subtext) == str:
                text += subtext
            else:
                text += subtext.get_text
            return text

class SimpleText:
    def __init__(self, text="", bookmark_start = None):
        self.text = text
        self.bookmark_start = bookmark_start.get_offset()

    def get_text():
        return self.text

class Text:
    def __init__(self, text="", bookmark_start = None):
        self.text = [SimpleText(text, bookmark_start)]
        self.bookmark_start = bookmark_start.get_offset()

    def get_text():
        text = ""
        for subtext in self.text:
            text += subtext.get_text()

    def current():
        for text in self.text:
            # recurse to the other texts




#class Text:
#    id = 0
#    def __init__(self, text="", parent = None, bookmark_start = None, bookmark_end = None):
#        self.text = text
#        self.id = Text.id
#        Text.id = Text.id + 1
#        self.committed = False
#        self.bookmark_start = bookmark_start.get_offset()
#        self.bookmark_end = bookmark_end.get_offset()
#        self.branches = []
#        self.curr_branch = None
#        self.parent = parent
#        if not self.parent is None:
#            self.depth = self.parent.depth + 1
#        else:
#            self.depth = 0
#
class UndoableBuffer(gtk.TextBuffer):
    """text buffer with added undo capabilities

    designed as a drop-in replacement for gtksourceview,
    at least as far as undo is concerned"""

    def __init__(self):
        """
        we'll need empty stacks for undo/redo and some state keeping
        """
        gtk.TextBuffer.__init__(self)
        self.modified = False
        self.text = Text("", self.get_iter_at_mark(self.get_mark("insert")))
        self.command = False
        self.connect('changed', self.on_changed)
        self.connect('delete-range', self.on_delete_range)
        self.connect('begin_user_action', self.on_begin_user_action)

    def change_text(self):
        self.set_text(self.text.get_text())
        #self.move_mark_by_name("insert", self.get_iter_at_offset(self.curr.bookmark_start - 1))
        #self.move_mark_by_name("selection_bound", self.get_iter_at_offset(self.curr.bookmark_end))


    #def go_next(self):
    #    if not self.curr.parent is None:
    #        if len(self.curr.parent.branches) == 1:
    #            return
    #        else:
    #            self.curr.parent.curr_branch = self.curr.parent.branches.index(self.curr)
    #            if len(self.curr.parent.branches) - 1 > self.curr.parent.curr_branch:
    #                self.curr.parent.curr_branch += 1
    #                self.curr = self.curr.parent.branches[self.curr.parent.curr_branch]
    #                self.change_text()
    #                return
    #            else:
    #                self.curr.parent.curr_branch -= len(self.curr.parent.branches)
    #                self.curr.parent.curr_branch += 1
    #                self.curr = self.curr.parent.branches[self.curr.parent.curr_branch]
    #                self.change_text()
    #                return

    #def go_down(self):
    #    if not self.curr.branches == []:
    #        self.curr = self.curr.branches[0]
    #        self.change_text()

    #def go_prev(self):
    #    if not self.curr.parent is None:
    #        if len(self.curr.parent.branches) == 1:
    #            return
    #        else:
    #            self.curr.parent.curr_branch = self.curr.parent.branches.index(self.curr)
    #            if 0 < self.curr.parent.curr_branch:
    #                self.curr.parent.curr_branch -= 1
    #                self.curr = self.curr.parent.branches[self.curr.parent.curr_branch]
    #                self.change_text()
    #                return
    #            else:
    #                self.curr.parent.curr_branch += len(self.curr.parent.branches)
    #                self.curr.parent.curr_branch -= 1
    #                self.curr = self.curr.parent.branches[self.curr.parent.curr_branch]
    #                self.change_text()
    #                return

    def commit_text(self):
        self.curr.committed = True

    def revert_to_parent(self):
        if not self.curr.parent is None:
            self.curr = self.curr.parent
            self.set_text(self.curr.text)
            self.place_cursor(self.get_iter_at_offset(self.curr.bookmark_end))

    def revise(self):
        cursor_position = self.get_iter_at_mark(self.get_mark("insert")).get_offset()
        text = self.get_text(start, end)

        def get_word(text, pos, end):
            if text[pos] == ' ' and (pos == end or text[pos] == ' '):
                k = pos - 1
                while text[k] != ' ' and k > 0:
                    k -= 1
                return get_word(text, k, end)
            if pos > 0:
                i = pos - 1
                while text[i] != ' ' and i > 0:
                    i -= 1
            else:
                i = 0

            if pos < end:
                j = pos
                while j < end and text[j] != ' ':
                    j += 1
            else:
                j = end

            if i != 0:
                i += 1
            return [i, j]
        i, j = get_word(text, cursor_position, len(text))



    def set_the_text(self):
        cursor_position = self.get_iter_at_mark(self.get_mark("insert"))
        #if self.curr.committed:
        #    start, end = self.get_bounds()
        #    t = Text(self.get_text(start, end), self.curr, cursor_position, cursor_position)
        #    t.bookmark_start = cursor_position.get_offset()
        #    t.bookmark_end = cursor_position.get_offset()
        #    self.curr.branches.append(t)
        #    self.curr = t
        #else:
        #    self.curr.text = self.get_text(self.get_start_iter(), self.get_end_iter())
        #    if self.curr.bookmark_end < cursor_position.get_offset():
        #        self.curr.bookmark_end = cursor_position.get_offset()

    def on_changed(self, textbuffer):
        if not self.command:
            self.set_the_text()

    def on_delete_range(self, text_buffer, start_iter, end_iter):
        print "hello"
        if not self.command:
            self.set_the_text()

    def on_begin_user_action(self, *args, **kwargs):
        pass

class BasicEdit(object):
    """editing logic that gets passed around"""

    def __init__(self):
        self.current = 0
        self.buffers = []
        self.config = config
        gui = GUI()
        state['gui'] = gui
        self.preferences = Preferences()
        try:
            self.recent_manager = gtk.recent_manager_get_default()
        except AttributeError:
            self.recent_manager = None
        self.status = gui.status
        self.revision_status = gui.revision_status
        self.window = gui.window
        self.window.add_accel_group(make_accel_group(self))
        self.textbox = gui.textbox
        self.UNNAMED_FILENAME = FILE_UNNAMED

        self.autosave_timeout_id = ''
        self.autosave_elapsed = ''

        self.textbox.connect('key-press-event', self.key_press_event)

        # Autosave timer object
        autosave.start_autosave(self)

        self.window.show_all()
        self.window.fullscreen()

        # Handle multiple monitors
        screen = gtk.gdk.screen_get_default()
        root_window = screen.get_root_window()
        mouse_x, mouse_y, mouse_mods = root_window.get_pointer()
        current_monitor_number = screen.get_monitor_at_point(mouse_x, mouse_y)
        monitor_geometry = screen.get_monitor_geometry(current_monitor_number)
        self.window.move(monitor_geometry.x, monitor_geometry.y)

        # Defines the glade file functions for use on closing a buffer or exit
        gladefile = os.path.join(state['absolute_path'], "interface.glade")
        builder = gtk.Builder()
        builder.add_from_file(gladefile)
        self.dialog = builder.get_object("SaveBuffer")
        self.dialog.set_transient_for(self.window)
        self.quitdialog = builder.get_object("QuitSave")
        self.quitdialog.set_transient_for(self.window)
        dic = {
                "on_button-close_clicked": self.unsave_dialog,
                "on_button-cancel_clicked": self.cancel_dialog,
                "on_button-save_clicked": self.save_dialog,
                "on_button-close2_clicked": self.quit_quit,
                "on_button-cancel2_clicked": self.cancel_quit,
                "on_button-save2_clicked": self.save_quit,
                }
        builder.connect_signals(dic)

        self.keybindings = define_keybindings(self)
        # this sucks, shouldn't have to call this here, textbox should
        # have its background and padding color from GUI().__init__() already
        gui.apply_theme()

    def key_press_event(self, widget, event):
        """ key press event dispatcher """
        self.show_revision_info()
        #self.revision_status.set_text(str(self.buffers[self.current].revise()))
        if event.state & gtk.gdk.CONTROL_MASK:
            if event.hardware_keycode in self.keybindings:
                self.keybindings[event.hardware_keycode]()
                return True
        return False

    def show_revision_info(self):
        #buf = self.buffers[self.current]
        #if buf.curr.committed:
        #    part = "(+) "
        #else:
        #    part = "( ) "
        #self.revision_status.set_text(part + str(buf.curr.depth) + " - " + str(len(buf.curr.branches)))
        self.revision_status.set_text("hello")

    def show_info(self):
        """ Display buffer information on status label for 5 seconds """

        buf = self.buffers[self.current]
        if buf.modified:
            status = _(' (modified)')
        else:
            status = ''
        self.status.set_text(_('Buffer %(buffer_id)d: %(buffer_name)s\
                %(status)s, %(char_count)d character(s), %(word_count)d word(s)\
                , %(lines)d line(s)') % {
                    'buffer_id': self.current + 1,
                    'buffer_name': buf.filename if int(config.get('visual', 'showpath')) else os.path.split(buf.filename)[1],
                    'status': status,
                    'char_count': buf.get_char_count(),
                    'word_count': self.word_count(buf),
                    'lines': buf.get_line_count(),
                    }, 5000)

    def go_next(self):
        buf = self.textbox.get_buffer()
        buf.command = True
        buf.go_next()
        buf.command = False

    def go_prev(self):
        buf = self.textbox.get_buffer()
        buf.command = True
        buf.go_prev()
        buf.command = False

    def go_down(self):
        buf = self.textbox.get_buffer()
        buf.command = True
        buf.go_down()
        buf.command = False

    def revert(self):
        buf = self.textbox.get_buffer()
        buf.command = True
        buf.revert_to_parent()
        buf.command = False

    def commit(self):
        buf = self.textbox.get_buffer()
        buf.commit_text()

    def ask_restore(self):
        """ask if backups should be restored

        returns True if proposal is accepted
        returns False in any other case (declined/dialog closed)"""
        restore_dialog = gtk.Dialog(
                title=_('Restore backup?'),
                parent=self.window,
                flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                buttons=(
                    gtk.STOCK_DISCARD, gtk.RESPONSE_REJECT,
                    gtk.STOCK_OPEN, gtk.RESPONSE_ACCEPT
                    )
                )
        question_asked = gtk.Label(
                _('''Backup information for this file has been found.
Open those instead of the original file?''')
                )
        question_asked.set_line_wrap(True)

        question_sign = gtk.image_new_from_stock(
                stock_id=gtk.STOCK_DIALOG_QUESTION,
                size=gtk.ICON_SIZE_DIALOG
                )
        question_sign.show()

        hbox = gtk.HBox()
        hbox.pack_start(question_sign, True, True, 0)
        hbox.pack_start(question_asked, True, True, 0)
        hbox.show()
        restore_dialog.vbox.pack_start(
                hbox, True, True, 0
                )

        restore_dialog.set_default_response(gtk.RESPONSE_ACCEPT)
        restore_dialog.show_all()
        resp = restore_dialog.run()
        restore_dialog.destroy()
        return resp == -3

    def open_file(self):
        """ Open file """

        chooser = gtk.FileChooserDialog('PyRoom', self.window,
                gtk.FILE_CHOOSER_ACTION_OPEN,
                buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        chooser.set_default_response(gtk.RESPONSE_OK)
        buf = self.buffers[self.current]
        if buf.filename != FILE_UNNAMED:
            chooser.set_current_folder(
                    os.path.dirname(os.path.abspath(buf.filename)
                        ))
        else:
            chooser_path = get_likely_chooser_path(self.buffers, self.current)
            if chooser_path:
                chooser.set_current_folder(chooser_path)
        res = chooser.run()
        if res == gtk.RESPONSE_OK:
            self.open_file_no_chooser(chooser.get_filename())
        else:
            self.status.set_text(_('Closed, no files selected'))
        chooser.destroy()

    def open_file_no_chooser(self, filename):
        """ Open specified file """
        def check_backup(filename):
            """check if restore from backup is an option

            returns backup filename if there's a backup file and
                    user wants to restore from it, else original filename
            """
            fname = autosave.get_autosave_filename(filename)
            if os.path.isfile(fname):
                if self.ask_restore():
                    return fname
                else:
                    os.remove(fname)
            return filename
        buf = self.new_buffer()
        buf.filename = filename
        filename_to_open = check_backup(filename)

        try:
            buffer_file = open(filename_to_open, 'r')
            buf = self.buffers[self.current]
            #buf.begin_not_undoable_action()
            utf8 = unicode(buffer_file.read(), 'utf-8')
            buf.set_text(utf8)
            #buf.end_not_undoable_action()
            buffer_file.close()
        except IOError, (errno, strerror):
            errortext = _('Unable to open %(filename)s.') % {
                    'filename': filename_to_open
                    }
            if errno == 13:
                errortext += _(' You do not have permission to open \
                        the file.')
                if not errno == 2:
                    raise CDraftError(errortext)
        except:
            raise CDraftError(_('Unable to open %s\n') % filename_to_open)
        else:
            self.status.set_text(_('File %s open') % filename_to_open)

    def save_file(self):
        """ Save file """
        try:
            buf = self.buffers[self.current]
            if buf.filename != FILE_UNNAMED:
                buffer_file = open(buf.filename, 'w')
                txt = buf.get_text(buf.get_start_iter(),
                        buf.get_end_iter())
                buffer_file.write(txt)
                if self.recent_manager:
                    self.recent_manager.add_full(
                            "file://" + urllib.quote(buf.filename),
                            {
                                'mime_type':'text/plain',
                                'app_name':'cdraft',
                                'app_exec':'%F',
                                'is_private':False,
                                'display_name':os.path.basename(buf.filename),
                                }
                            )
                    buffer_file.close()
                #buf.begin_not_undoable_action()
                #buf.end_not_undoable_action()
                self.status.set_text(_('File %s saved') % buf.filename)
            else:
                self.save_file_as()
                return
        except IOError, (errno, strerror):
            errortext = _('Unable to save %(filename)s.') % {
                    'filename': buf.filename}
            if errno == 13:
                errortext += _(' You do not have permission to write to \
                        the file.')
                raise CDraftError(errortext)
        except:
            raise CDraftError(_('Unable to save %s\n') % buf.filename)
        buf.modified = False

    def save_file_as(self):
        """ Save file as """

        buf = self.buffers[self.current]
        chooser = gtk.FileChooserDialog('PyRoom', self.window,
                gtk.FILE_CHOOSER_ACTION_SAVE,
                buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        chooser.set_default_response(gtk.RESPONSE_OK)
        chooser.set_do_overwrite_confirmation(True)
        if buf.filename != FILE_UNNAMED:
            chooser.set_filename(buf.filename)
        else:
            chooser_path = get_likely_chooser_path(self.buffers, self.current)
            if chooser_path:
                chooser.set_current_folder(chooser_path)
        res = chooser.run()
        if res == gtk.RESPONSE_OK:
            buf.filename = chooser.get_filename()
            self.save_file()
        else:
            self.status.set_text(_('Closed, no files selected'))
        chooser.destroy()

    #XXX: This can't be the best way to do this.
    def word_count(self, buf):
        """ Word count in a text buffer """

        iter1 = buf.get_start_iter()
        iter2 = iter1.copy()
        iter2.forward_word_end()
        count = 0
        while iter2.get_offset() != iter1.get_offset():
            count += 1
            iter1 = iter2.copy()
            iter2.forward_word_end()
        return count

    def show_help(self):
        """ Create a new buffer and inserts help """
        buf = self.new_buffer()
        #buf.begin_not_undoable_action()
        buf.set_text(HELP)
        #buf.end_not_undoable_action()
        self.status.set_text("Displaying help. Press control W to exit and \
                continue editing your document.")

    def new_buffer(self):
        """ Create a new buffer """

        buf = UndoableBuffer()
        buf.filename = FILE_UNNAMED
        self.buffers.insert(self.current + 1, buf)
        buf.place_cursor(buf.get_end_iter())
        self.next_buffer()
        self.show_revision_info()
        return buf

    def close_dialog(self):
        """ask for confirmation if there are unsaved contents"""
        buf = self.buffers[self.current]
        if buf.modified:
            self.dialog.show()
        else:
            self.close_buffer()

    def cancel_dialog(self, widget, data=None):
        """dialog has been canceled"""
        self.dialog.hide()

    def unsave_dialog(self, widget, data =None):
        """don't save before closing"""
        self.dialog.hide()
        self.close_buffer()

    def save_dialog(self, widget, data=None):
        """save when closing"""
        self.dialog.hide()
        self.save_file()
        self.close_buffer()

    def close_buffer(self):
        """ Close current buffer """
        autosave_fname = autosave.get_autosave_filename(
                self.buffers[self.current].filename
                )
        if os.path.isfile(autosave_fname):
            try:
                os.remove(autosave_fname)
            except OSError:
                raise CDraftError(_('Could not delete autosave file.'))
        if len(self.buffers) > 1:
            self.buffers.pop(self.current)
            self.current = min(len(self.buffers) - 1, self.current)
            self.set_buffer(self.current)
        else:
            quit()

    def set_buffer(self, index):
        """ Set current buffer """

        if index >= 0 and index < len(self.buffers):
            self.current = index
            buf = self.buffers[index]
            self.textbox.set_buffer(buf)
            if hasattr(self, 'status'):
                self.status.set_text(
                        _('Switching to buffer %(buffer_id)d (%(buffer_name)s)')
                        % {'buffer_id': self.current + 1,
                            'buffer_name': buf.filename}
                        )

    def next_buffer(self):
        """ Switch to next buffer """
        if self.current < len(self.buffers) - 1:
            self.current += 1
        else:
            self.current = 0
        self.set_buffer(self.current)
        state['gui'].textbox.scroll_to_mark(
                self.buffers[self.current].get_insert(),
                0.0,
                )

    def prev_buffer(self):
        """ Switch to prev buffer """
        if self.current > 0:
            self.current -= 1
        else:
            self.current = len(self.buffers) - 1
        self.set_buffer(self.current)
        state['gui'].textbox.scroll_to_mark(
                self.buffers[self.current].get_insert(),
                0.0,
                )

    def dialog_quit(self):
        """the quit dialog"""
        count = 0
        ret = False
        for buf in self.buffers:
            if buf.modified:
                count = count + 1
        if count > 0:
            self.quitdialog.show()
        else:
            self.quit()

    def cancel_quit(self, widget, data=None):
        """don't quit"""
        self.quitdialog.hide()

    def save_quit(self, widget, data=None):
        """save before quitting"""
        self.quitdialog.hide()
        for buf in self.buffers:
            if buf.modified:
                if buf.filename == FILE_UNNAMED:
                    self.save_file_as()
                else:
                    self.save_file()
        self.quit()

    def quit_quit(self, widget, data=None):
        """really quit"""
        self.quitdialog.hide()
        self.quit()

    def quit(self):
        """cleanup before quitting"""
        autosave.stop_autosave(self)
        state['gui'].quit()

    def dialog_minimize(self):
        """ Minimize (iconify) the window """
        state['gui'].iconify()


import functools
import re

import sublime
import sublime_plugin


def match_line(regex, text, case_sensitive, invert_search=False):
    flags = 0
    if not case_sensitive:
        flags |= re.IGNORECASE

    match = re.search(regex, text, flags)
    return bool(match) ^ invert_search


def itersplit(sep, s):
    exp = re.compile(sep)
    pos = 0
    old_start = 0
    from_begin = False
    while True:
        m = exp.search(s, pos)
        if not m:
            if pos < len(s):
                if not from_begin:
                    yield s[pos:]
                else:
                    yield s[old_start:]
            break
        if pos < m.start() and not from_begin:
            yield s[pos:m.end()]
        elif from_begin:
            yield s[old_start:m.start()]
        elif m.start() == 0:
            # pattern is found at beginning, reverse yielding slices
            from_begin = True
        pos = m.end()
        old_start = m.start()


class FilterLinesCommand(sublime_plugin.WindowCommand):

    def run(self):
        settings = sublime.load_settings('Filter Lines.sublime-settings')

        search_text = ''
        if settings.get('preserve_search', True):
            search_text = settings.get('latest_search', '')

        invert_search = settings.get('invert_search', False)

        prompt = ("Filter file for lines %s regex: " %
                  ('not matching' if invert_search else 'matching'))

        sublime.active_window().show_input_panel(
            prompt, search_text, self.on_regex, None, None)

    def on_regex(self, regex):
        if self.window.active_view():
            settings = sublime.load_settings('Filter Lines.sublime-settings')
            if settings.get('preserve_search', True):
                settings.set('latest_search', regex)
                sublime.save_settings('Filter Lines.sublime-settings')

            if settings.get('custom_separator', False):
                f = functools.partial(self.on_separator, regex)
                default_sep = settings.get('default_custom_separator',
                                           r'(\n|\r\n|\r)')
                sublime.active_window().show_input_panel(
                    'Custom regex separator', default_sep,
                    f, None, None)
            else:
                self.window.active_view().run_command(
                    "filter_matching_lines", {"regex": regex})

    def on_separator(self, regex, separator):
        self.window.active_view().run_command(
            "filter_matching_lines", {"regex": regex, "separator": separator})


class FilterMatchingLinesCommand(sublime_plugin.TextCommand):

    def run(self, edit, regex, separator=None):
        sublime.status_message('Filtering...')
        settings = sublime.load_settings('Filter Lines.sublime-settings')
        case_sensitive = settings.get('case_sensitive_search', True)
        invert_search = settings.get('invert_search', False)
        self.filter_to_new_buffer(edit, regex, case_sensitive, invert_search,
                                  separator)
        sublime.status_message('')

    def filter_to_new_buffer(self, edit, regex, case_sensitive, invert_search,
                             separator):
        results_view = self.view.window().new_file()
        results_view.set_name('Filter Results')
        results_view.set_scratch(True)
        results_view.settings().set(
            'word_wrap', self.view.settings().get('word_wrap'))

        region = sublime.Region(0, self.view.size())
        if not separator:
            lines = (self.view.substr(r)
                     for r in self.view.split_by_newlines(region))
        else:
            lines = itersplit(separator, self.view.substr(region))

        text = ''
        for line in lines:
            if match_line(regex, line, case_sensitive, invert_search):
                if not separator:
                    line += '\n'
                text += line

        results_view.run_command(
            'append', {'characters': text, 'force': True,
                       'scroll_to_end': False})

        if results_view.size() > 0:
            results_view.set_syntax_file(self.view.settings().get('syntax'))
        else:
            message = ('Filtering lines for "%s" %s\n\n0 matches\n' % (regex,
                       '(case-sensitive)' if case_sensitive else
                       '(not case-sensitive)'))
            results_view.run_command(
                'append', {'characters': message, 'force': True,
                           'scroll_to_end': False})

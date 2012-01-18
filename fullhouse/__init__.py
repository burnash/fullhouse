import re
import os.path

class SourceParserError(Exception):
    pass

class AssetNotFoundError(Exception):
    pass


class SourceParser(object):
    def __init__(self, source, filename):
        self.source = source
        self.pos = 0
        self.filename = filename
        self.lines = []
        self.length = len(source)

    def _parse_single_line_comment(self):
        chars = []
        while True:
            c = self._get_next()
            if c is None or c == "\n" or c == "\r":
                break
            chars.append(c)
        if chars:
            self.lines.append(''.join(chars))

    def _parse_multiline_comment(self):
        # Should be everything to */
        chars = []
        while True:
            c = self._get_next()
            if c is None:
                raise SourceParserError("Premature EOF at %s" % self.filename)
            elif c == '/' and chars[-1] == '*':
                chars.pop()
                break
            chars.append(c)
        self.lines.append(''.join(chars))

    def _parse_string(self, terminator):
        prev_char = None
        while True:
            c = self._get_next()
            if c is None:
                break
            if c == terminator and prev_char != "\\":
                break
            prev_char = c

    def _get_next(self):
        if self.pos < self.length:
            c = self.source[self.pos]
            self.pos += 1
        else:
            c = None
        return c

    def _go_back(self):
        self.pos -= 1

    def extract(self):
        while True:
            c = self._get_next()
            if c is None:
                break
            elif c == '/':
                nextc = self._get_next()
                if nextc == '/':
                    self._parse_single_line_comment()
                elif nextc == '*':
                    self._parse_multiline_comment()
                else:
                    self._go_back()
            elif c == '"':
                self._parse_string('"')
            elif c == "'":
                self._parse_string("'")

        return "\n".join(self.lines)


class Directive(object):
    pass


class RequireDirective(Directive):
    def __init__(self, args):
        self.args = args

    def get_source_url(self):
        return self.args

    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.args)


_directive_re = re.compile(r'=[ \t]*(\w+)[ \t]+(.*)$')

class CommentParser(object):
    """Returns list of directives"""
    dispatch = {'require': RequireDirective}

    def __init__(self, source):
        source = source.strip()
        directives = []

        for line in source.splitlines():
            m = _directive_re.match(line.strip())
            if m:
                directive_name = m.group(1)
                try:
                    directive_cls = self.dispatch[directive_name]
                    directive = directive_cls(m.group(2))
                except KeyError:
                    # TODO: warn on typos
                    pass

                directives.append(directive)

        self._directives = directives

    def directives(self):
        return self._directives


class FullHouseAsset(object):
    _script_template = "<script src=\"%s\"></script>"
    def __init__(self, filename, assets_paths, asset_url, debug=False):
        self.filename = filename
        self.asset_url = asset_url
        for path in assets_paths:
            try:
                f = open(os.path.join(path, filename))
                comment_text = SourceParser(f.read(), filename).extract()
                self.directives = CommentParser(comment_text).directives()

            except IOError:
                continue
            break
        else:
            raise AssetNotFoundError('File not found: %s', filename)

    def as_tag_list(self):
        MAGIC_HACK = 'js'
        tags = [self._script_template % \
                    os.path.join(self.asset_url, MAGIC_HACK, d.get_source_url()) \
            for d in self.directives]
        # Include self
        tags.append(self._script_template %
                    os.path.join(self.asset_url, MAGIC_HACK, self.filename))
        return "\n".join(tags)

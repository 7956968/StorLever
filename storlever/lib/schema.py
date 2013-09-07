"""
Copyright (c) 2012 Vladimir Keleshev, <vladimir@keleshev.com>

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from inspect import getargspec
from functools import wraps


__version__ = '0.2.0'


class SchemaError(Exception):

    """Error during Schema validation."""

    def __init__(self, autos, errors):
        self.autos = autos if type(autos) is list else [autos]
        self.errors = errors if type(errors) is list else [errors]
        Exception.__init__(self, self.code)

    @property
    def code(self):
        def uniq(seq):
            seen = set()
            seen_add = seen.add
            return [x for x in seq if x not in seen and not seen_add(x)]
        a = uniq(i for i in self.autos if i is not None)
        e = uniq(i for i in self.errors if i is not None)
        if e:
            return '\n'.join(e)
        return '\n'.join(a)


def handle_default(init):

    """Add default handling to __init__ method; meant for decorators"""

    def init2(self, *args, **kw):
        # get default from the ``default`` keyword argument
        if 'default' in kw:
            self.default = kw['default']
            del(kw['default'])
        # if auto_default is set, get default from first argument
        elif hasattr(self, 'auto_default') and self.auto_default:
            self.default = args[0]
            if hasattr(self.default, 'default'):
                self.default = self.default.default
            elif type(self.default) == type:
                self.default = self.default()
        # normal init
        init(self, *args, **kw)
        # validate default
        if hasattr(self, 'default'):
            try:
                self.default = self.validate(self.default)
            except SchemaError:
                raise ValueError('%s does not validate its default: %s' % (
                    self, self.default))
    return init2


class And(object):

    @handle_default
    def __init__(self, *args, **kw):
        self._args = args
        assert len(args)
        assert list(kw) in (['error'], [])
        self._error = kw.get('error')

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join(repr(a) for a in self._args))

    def validate(self, data):
        for s in [Schema(s, error=self._error) for s in self._args]:
            data = s.validate(data)
        return data


class Or(And):

    def validate(self, data):
        x = SchemaError([], [])
        for s in [Schema(s, error=self._error) for s in self._args]:
            try:
                return s.validate(data)
            except SchemaError as _x:
                x = _x
        raise SchemaError(['%r did not validate %r' % (self, data)] + x.autos,
                         [self._error] + x.errors)


class Use(object):

    @handle_default
    def __init__(self, callable_, error=None):
        assert callable(callable_)
        self._callable = callable_
        self._error = error

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._callable)

    def validate(self, data):
        try:
            return self._callable(data)
        except SchemaError as x:
            raise SchemaError([None] + x.autos, [self._error] + x.errors)
        except BaseException as x:
            f = self._callable.__name__
            raise SchemaError('%s(%r) raised %r' % (f, data, x), self._error)


def priority(s):
    if type(s) in (list, tuple, set, frozenset):
        return 6
    if type(s) is dict:
        return 5
    if hasattr(s, 'validate'):
        return 4
    if type(s) is type:
        return 3
    if callable(s):
        return 2
    else:
        return 1


class Schema(object):

    @handle_default
    def __init__(self, schema, error=None):
        self._schema = schema
        self._error = error

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._schema)

    def validate(self, data):
        s = self._schema
        e = self._error
        if type(s) in (list, tuple, set, frozenset):
            data = Schema(type(s), error=e).validate(data)
            return type(s)(Or(*s, error=e).validate(d) for d in data)
        if type(s) is dict:
            data = Schema(dict, error=e).validate(data)
            new = type(data)()
            x = None
            coverage = set() # non-optional schema keys that were matched
            for key, value in data.items():
                valid = False
                skey = None
                for skey in sorted(s, key=priority):
                    svalue = s[skey]
                    try:
                        nkey = Schema(skey, error=e).validate(key)
                        try:
                            nvalue = Schema(svalue, error=e).validate(value)
                        except SchemaError as _x:
                            x = _x
                            raise
                    except SchemaError:
                        pass
                    else:
                        coverage.add(skey)
                        valid = True
                        break
                if valid:
                    new[nkey] = nvalue
                elif skey is not None:
                    if x is not None:
                        raise SchemaError(['key %r is required' % key] +
                                          x.autos, [e] + x.errors)
                    else:
                        raise SchemaError('key %r is required' % skey, e)
            required = set(k for k in s if type(k) is not Optional)
            # missed keys
            if not required.issubset(coverage):
                raise SchemaError('missed keys %r' % (required - coverage), e)
            # wrong keys
            if len(new) != len(data):
                raise SchemaError('wrong keys %r in %r' % (new, data), e)
            # default for optional keys
            for k in set(s) - required - coverage:
                try:
                    new[k.default] = s[k].default
                except AttributeError:
                    pass
            return new
        if hasattr(s, 'validate'):
            try:
                return s.validate(data)
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%r.validate(%r) raised %r' % (s, data, x),
                                 self._error)
        if type(s) is type:
            if isinstance(data, s):
                return data
            else:
                raise SchemaError('%r should be instance of %r' % (data, s), e)
        if callable(s):
            f = s.__name__
            try:
                if s(data):
                    return data
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%s(%r) raised %r' % (f, data, x),
                                  self._error)
            raise SchemaError('%s(%r) should evaluate to True' % (f, data), e)
        if s == data:
            return data
        else:
            raise SchemaError('%r does not match %r' % (s, data), e)


class Optional(Schema):

    """Marker for an optional part of Schema."""

    auto_default = True


class Default(Schema):

    """Wrapper automatically adding a default value if possible"""

    auto_default = True


if __name__ == '__main__':
    # example
    schema = Schema({"key1": str,       # key1 should be string
                     "key2": int,       # key2 should be int
                     "key3": Use(int),  # key3 should be in or int in string
                     "key4": And(int, lambda n: 0 < n < 100),   # key4 should be int between 1-99
                     Optional("key5"): Default(str, default="value5"),  # key5 is optional,
                                                                        # should be str and default value is "value 5"
                     Optional(str): object})      # for keys we don't care

    from pprint import pprint

    # should pass the validation
    pprint(schema.validate({"key1": "value1",
                            "key2": 222,
                            "key3": "333",
                            "key4": 44,
                            "key_none": None,
                            "key_none2": "null"}))

    # all following cases should fail
    import traceback

    try:
        schema.validate({"key1": "value1"})   # missing key
    except Exception:
        print traceback.format_exc()

    try:
        schema.validate({"key1": "value1",
                         "key2": 222,
                         "key3": 333,
                         "key4": 444})   # number too large
    except Exception:
        print traceback.format_exc()

    try:
        schema.validate({"key1": "value1",
                         "key2": 222,
                         "key3": 333,
                         "key4": 44,
                         "key5": 555})   # wrong type
    except Exception:
        print traceback.format_exc()
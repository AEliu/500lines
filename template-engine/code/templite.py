"""A simple Python template renderer, for a nano-subset of Django syntax."""

# Coincidentally named the same as http://code.activestate.com/recipes/496702/

# there classes, TempliteSyntaxError CodeBuilder & Templite

import re


class TempliteSyntaxError(ValueError):
    """Raised when a template has a syntax error."""
    pass
    # 从ValueError继承过来，exception ValueError Raised when a built-in operation or function receives an argument that has the right type but an inappropriate value, and the situation is not described by a more precise exception such as IndexError.


# object is a base for all classes. 
# python3 中默认继承这个类
class CodeBuilder(object):
    """Build source code conveniently."""

    def __init__(self, indent=0):
        self.code = []
        self.indent_level = indent
        # 两个属性，code 和 indent_level
        # 初始化时用

    def __str__(self):
        return "".join(str(c) for c in self.code)
        # return a string object of conbine the elements in code[]
        # str.join(iterable)
        # iterable: objects of any classes you define with an __iter__() or __getitem__() method.
        # str(c) for c in self.code is a generator object
        # join() is a method of strings. That method takes any iterable and iterates over it and joins the contents together. 
        # https://stackoverflow.com/questions/14447081/python-generator-objects-and-join/14447119#14447119

    def add_line(self, line):
        """Add a line of source to the code.

        Indentation and newline will be added for you, don't provide them.

        """
        self.code.extend([" " * self.indent_level, line, "\n"])
        # " " * self.indent_level, 自带缩进
        # list.extend(L) Extend the list by appending all the items in the given list. Equivalent to a[len(a):] = L.
        # By contrast, list.appedn(L), Add an item L to the end of the list. 
        # 都加到code列表中了



    def add_section(self):
        """Add a section, a sub-CodeBuilder."""
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        # 加到code里了又
        return section

    INDENT_STEP = 4      # PEP8 says so!

    def indent(self):
        """Increase the current indent for following lines."""
        self.indent_level += self.INDENT_STEP
        # 加4各空格

    def dedent(self):
        """Decrease the current indent for following lines."""
        self.indent_level -= self.INDENT_STEP


    def get_globals(self):
        """Execute the code, and return a dict of globals it defines."""
        # A check that the caller really finished all the blocks they started.
        assert self.indent_level == 0
        # Get the Python source as a single string.
        python_source = str(self)
        # Execute the source, defining globals, and return them.
        global_namespace = {}
        exec(python_source, global_namespace)
        # global_namespace全局变量
        return global_namespace


class Templite(object):
    """A simple template renderer, for a nano-subset of Django syntax.

    Supported constructs are extended variable access::

        {{var.modifer.modifier|filter|filter}}

    loops::

        {% for var in list %}...{% endfor %}

    and ifs::

        {% if var %}...{% endif %}

    Comments are within curly-hash markers::

        {# This will be ignored #}

    Construct a Templite with the template text, then use `render` against a
    dictionary context to create a finished string::

        templite = Templite('''
            <h1>Hello {{name|upper}}!</h1>
            {% for topic in topics %}
                <p>You are interested in {{topic}}.</p>
            {% endif %}
            ''',
            {'upper': str.upper},
        )
        text = templite.render({
            'name': "Ned",
            'topics': ['Python', 'Geometry', 'Juggling'],
        })

    """
    def __init__(self, text, *contexts):
        """Construct a Templite with the given `text`.

        `contexts` are dictionaries of values to use for future renderings.
        These are good for filters and global values.

        """
        self.context = {}
        for context in contexts:
            # contexts is a tuple
            self.context.update(context)
            # Update the dictionary with the key/value pairs from other, overwriting existing keys. Return None.
            # update() accepts either another dictionary object or an iterable of key/value pairs (as tuples or other iterables of length two). If keyword arguments are specified, the dictionary is then updated with those key/value pairs: d.update(red=1, blue=2).

        self.all_vars = set()
        self.loop_vars = set()

        # We construct a function in source form, then compile it and hold onto
        # it, and execute it to render the template.
        code = CodeBuilder()

        code.add_line("def render_function(context, do_dots):")
        code.indent() 
        # 以后的增加4个空格
        vars_code = code.add_section()
        # section = CodeBuilder(self.indent_level)
        # self.code.append(section)
        code.add_line("result = []")
        # create a list of strings, and join them together at the end. 
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")
        # Names in Python can be local to a function, global to a module, or built-in to Python. Looking up a local name is faster than looking up a global or a built-in. 

        buffered = []
        def flush_output():
            """Force `buffered` to the code builder."""
            if len(buffered) == 1:
                code.add_line("append_result(%s)" % buffered[0])
            elif len(buffered) > 1:
                code.add_line("extend_result([%s])" % ", ".join(buffered))
            del buffered[:]
            # 清空列表， 不能用 del buffered

        ops_stack = []

        # Split the text to form a list of tokens.
        # (?s) means dot matches all
        # .*? nongreedy
        # If capturing parentheses are used in pattern, then the text of all groups in the pattern are also returned as part of the resulting list.
        # 有括号，保留匹配部分，留在列表里，此处是tekens
        tokens = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", text)

        for token in tokens:
            if token.startswith('{#'):
                # Comment: ignore it and move on.
                continue
            elif token.startswith('{{'):
                # An expression to evaluate.
                # eg. {{name|upper}}\ {{ product.price|format_price }}\ {{ product.name }} {{name}}
                expr = self._expr_code(token[2:-2].strip())
                buffered.append("to_str(%s)" % expr)
                # 1. {{name}} expr = self._expr_code('name')
                #    self._variable('name', self.all_vars)
                #    self.all_vars.add(name), now self.all_vars == {'name'}， code == 'c_name'
                #    buffered == ["to_str(c_name)", ]
                # 2. {{name|upper}}， expr = self._expr_code('name|upper')
                #    code = self._expr_code('name') == 'c_name'
                #    self._variable('upper', self.all_vars), self.all_vars == {'upper'}
                #    code = "c_%s(%s)" % (func, code) == "c_upper(c_name)"
                #    buffered == ["to_str(c_name)", "to_str(c_upper(c_name))"]
                # 3. {{ product.name }}, expr = self._expr_code('product.name') 
                #    code = self._expr_code("product") = 'c_product'
                #    args = ", ".join(repr(d) for d in dots[1:]) == "'name'"
                #    expr == code = "do_dots(%s, %s)" % (code, args) == "do_dots(c_product, 'name')"
                #    buffered == ["to_str(c_name)", "to_str(c_upper(c_name))", "to_str(do_dots(c_product, 'name'))"]
            elif token.startswith('{%'):
                # Action tag: split into words and parse further.
                # 支持 if & for
                flush_output()
                words = token[2:-2].strip().split()
                if words[0] == 'if':
                    # An if statement: evaluate the expression to determine if.
                    if len(words) != 2:
                        self._syntax_error("Don't understand if", token)
                    ops_stack.append('if')
                    code.add_line("if %s:" % self._expr_code(words[1]))
                    code.indent()
                elif words[0] == 'for':
                    # A loop: iterate over expression result.
                    if len(words) != 4 or words[2] != 'in':
                        self._syntax_error("Don't understand for", token)
                    ops_stack.append('for')
                    self._variable(words[1], self.loop_vars)
                    code.add_line(
                        "for c_%s in %s:" % (
                            words[1],
                            self._expr_code(words[3])
                        )
                    )
                    code.indent()
                elif words[0].startswith('end'):
                    # Endsomething.  Pop the ops stack.
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)
                    end_what = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    start_what = ops_stack.pop()
                    if start_what != end_what:
                        self._syntax_error("Mismatched end tag", end_what)
                    code.dedent()
                else:
                    self._syntax_error("Don't understand tag", words[0])
            else:
                # Literal content.  If it isn't empty, output it.
                if token:
                    buffered.append(repr(token))

        if ops_stack:
            self._syntax_error("Unmatched action tag", ops_stack[-1])

        flush_output()

        for var_name in self.all_vars - self.loop_vars:
            vars_code.add_line("c_%s = context[%r]" % (var_name, var_name))
            # r% 'name'
            # 在开头的位置插入从字典里的取值

        code.add_line("return ''.join(result)")
        code.dedent()
        self._render_function = code.get_globals()['render_function']

    def _expr_code(self, expr):
        """Generate a Python expression for `expr`."""
        if "|" in expr:
            pipes = expr.split("|")
            code = self._expr_code(pipes[0])
            for func in pipes[1:]:
                self._variable(func, self.all_vars)
                code = "c_%s(%s)" % (func, code)
        elif "." in expr:
            dots = expr.split(".")
            code = self._expr_code(dots[0])
            args = ", ".join(repr(d) for d in dots[1:])
            code = "do_dots(%s, %s)" % (code, args)
        else:
            self._variable(expr, self.all_vars)
            code = "c_%s" % expr
        return code

    def _syntax_error(self, msg, thing):
        """Raise a syntax error using `msg`, and showing `thing`."""
        raise TempliteSyntaxError("%s: %r" % (msg, thing))

    def _variable(self, name, vars_set):
        """Track that `name` is used as a variable.

        Adds the name to `vars_set`, a set of variable names.

        Raises an syntax error if `name` is not a valid name.

        """
        if not re.match(r"[_a-zA-Z][_a-zA-Z0-9]*$", name):
            self._syntax_error("Not a valid name", name)
        vars_set.add(name)

    def render(self, context=None):
        """Render this template by applying it to `context`.

        `context` is a dictionary of values to use in this rendering.

        """
        # Make the complete context we'll use.
        render_context = dict(self.context)
        if context:
            render_context.update(context)
        return self._render_function(render_context, self._do_dots)

    def _do_dots(self, value, *dots):
        """Evaluate dotted expressions at runtime."""
        for dot in dots:
            try:
                value = getattr(value, dot)
            except AttributeError:
                value = value[dot]
            if callable(value):
                value = value()
        return value

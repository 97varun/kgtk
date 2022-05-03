"""
SQLStore to support Kypher queries over KGTK graphs.
"""

import re
from   functools import lru_cache

from   kgtk.exceptions import KGTKException
from   kgtk.kypher.utils import *


### Indexing support

# The functions and classes below support the following:
# - extensible representation of arbitrary index objects (such as column, multi-column, text indexes, etc.)
# - support for parsing concise index specs that can be supplied on the command line, for example,
#   '... --idx text:node1,node2/text ...' to specify a full-text search index on a graph column
# - support for storing and retrieving index objects to database info tables
# - support for comparing indexes for equivalence and subsumption
# - support for generating SQL definition/deletion statements specific to a particular index type
# - mapping macro index modes onto their respective index sets or actions
# - TO DO: detect modes such as 'mode:attgraph' automatically from computing some quick statistics

INDEX_MODE_NONE        = 'mode:none'
INDEX_MODE_AUTO        = 'mode:auto'
INDEX_MODE_AUTO_TEXT   = 'mode:autotext'
INDEX_MODE_CLEAR       = 'mode:clear'
INDEX_MODE_CLEAR_TEXT  = 'mode:cleartext'
INDEX_MODE_EXPERT      = 'mode:expert'

# graph modes:
INDEX_MODE_GRAPH       = 'mode:graph'
INDEX_MODE_MONO_GRAPH  = 'mode:monograph'
INDEX_MODE_VALUE_GRAPH = 'mode:valuegraph'
INDEX_MODE_TEXT_GRAPH  = 'mode:textgraph'

# legacy modes:
INDEX_MODE_PAIR        = 'mode:node1+label'
INDEX_MODE_TRIPLE      = 'mode:triple'
INDEX_MODE_QUAD        = 'mode:quad'

INDEX_MODES = {
    # macro modes:
    INDEX_MODE_NONE:        INDEX_MODE_NONE,
    INDEX_MODE_AUTO:        INDEX_MODE_AUTO,
    INDEX_MODE_AUTO_TEXT:   INDEX_MODE_AUTO_TEXT,
    INDEX_MODE_CLEAR:       INDEX_MODE_CLEAR,
    INDEX_MODE_CLEAR_TEXT:  INDEX_MODE_CLEAR_TEXT,
    INDEX_MODE_EXPERT:      INDEX_MODE_EXPERT,

    # graph modes:
    INDEX_MODE_GRAPH:       ['index:node1,label,node2', 'index:label', 'index:node2,label,node1'],
    INDEX_MODE_MONO_GRAPH:  ['index:node1,label,node2', 'index:node2,label,node1'],
    INDEX_MODE_VALUE_GRAPH: ['index:node1'],
    INDEX_MODE_TEXT_GRAPH:  ['index:node1', 'text:node2//tokenize=trigram'],
    
    # legacy modes:
    INDEX_MODE_PAIR:        ['index:node1', 'index:label'],
    INDEX_MODE_TRIPLE:      ['index:node1', 'index:label', 'index:node2'],
    INDEX_MODE_QUAD:        ['index:node1', 'index:label', 'index:node2', 'index:id'],
}

def get_normalized_index_mode(index_spec):
    """Normalize 'index_spec' to one of the legal macro modes such as 'mode:auto', etc.,
    or a list of individual index specs corresponding to the mode.  If 'index_spec' is a
    custom spec such as 'node1,node2', for example, it will also be converted to a list.
    """
    norm_spec = None
    spec_type = get_index_spec_type(index_spec)
    if spec_type and spec_type.lower() == 'mode':
        # we have an explicit mode, look it up and ensure it is valid:
        parse = tokenize_index_spec(index_spec)
        if len(parse) == 2 and parse[1][1] == 'text':
            norm_spec = INDEX_MODES.get('mode:' + parse[1][0].lower())
        if norm_spec is None:
            raise KGTKException(f'unsupported index mode: {index_spec}')
    else:
        # we might have a bare mode such as 'auto' or 'none', try to look it up as a mode
        # (to use a bare mode as a column name, explicitly use the appropriate index type):
        norm_spec = INDEX_MODES.get('mode:' + index_spec.strip().lower(), [index_spec])
        # enforce that clear-modes are fully qualified for some extra protection:
        if norm_spec in (INDEX_MODE_CLEAR, INDEX_MODE_CLEAR_TEXT):
            raise KGTKException(f"index mode '{index_spec}' needs to be explicitly qualified")
    return norm_spec

# we use /<option> as the option syntax instead of the --<option> syntax used on the command line
# for more concise representation, and to visually separate these specs from other command options:
INDEX_TOKENIZER_REGEX = re.compile(
    '|'.join([r'(?P<optsepsep>//)\s*',            # '//' (needs to come before single '/')
              r'(?P<optsep>/)\s*',                # '/'
              r'(?P<typesep>:)\s*',               # ':'
              r'(?P<valuesep>=)\s*',              # '='
              r'(?P<sep>[,()])\s*',               # (',', '(', ')')
              r'(?P<text>[^,()/:=`"\s]+)',        # non-special-char text tokens
              r'`(?P<quote_1>([^`]*``)*[^`]*)`',  # `-quoted tokens
              r'"(?P<quote_2>([^"]*"")*[^"]*)"',  # "-quoted tokens
              r'(?P<whitespace>\s+)',             # whitespace separates but is ignored
    ]))

INDEX_SPEC_TYPE_SEPARATOR = ':'

@lru_cache(maxsize=None)
def tokenize_expression(expression, regex=INDEX_TOKENIZER_REGEX):
    """Tokenize expression into a list of '(token, type)' tuples where type is one of 'text' or 'sep'.
    Tokens are split at separators and whitespace unless prevented by quoting (all defined by 'regex').
    Quoting is performed just like identifier quoting in SQL or Cypher using either a backtick or
    double quote where an explicit quote can be inserted by doubling it.
    """
    tokens = []
    total_match = 0
    for m in regex.finditer(expression):
        ms, me = m.span()
        token = m.group(m.lastgroup)
        toktype = m.lastgroup.split('_')[0]
        total_match += (me - ms)
        if toktype == 'quote':
            quote = expression[ms]
            # unescape quotes:
            token = token.replace(quote+quote, quote)
            toktype = 'text'
        if toktype != 'whitespace':
            tokens.append((token, toktype))
    # make sure we didn't skip any garbage:
    if total_match < len(expression):
        raise KGTKException('illegal expression syntax')
    return tokens

def tokenize_index_spec(index_spec, regex=INDEX_TOKENIZER_REGEX):
    """Tokenizes 'index_spec' (unless it is already tokenized) and returns all
    text tokens classified as one of ('text', 'type', 'option', 'global-option').
    All separator tokens are interpreted and then filtered out.
    """
    if not isinstance(index_spec, list):
        index_spec = tokenize_expression(index_spec, regex=regex)
    index_spec = [list(x) for x in index_spec]
    last = len(index_spec) - 1
    tokens = []
    for i, (token, toktype) in enumerate(index_spec):
        if toktype == 'typesep':
            if i > 0 and index_spec[i-1][1] == 'text':
                index_spec[i-1][1] = 'type'
            else:
                raise KGTKException('illegal index spec syntax')
        elif toktype in ('optsep', 'optsepsep'):
            if i < last and index_spec[i+1][1] == 'text':
                index_spec[i+1][1] = 'option' if toktype == 'optsep' else 'global-option'
            else:
                raise KGTKException('illegal index spec syntax')
        elif toktype == 'valuesep':
            value = '' # an option followed by non-text means the empty value
            if i < last and index_spec[i+1][1] == 'text':
                value = index_spec[i+1][0]
                index_spec[i+1][1] = 'value'
            if i > 0 and index_spec[i-1][1].endswith('option'):
                # if we have a value, we represent it with a tuple:
                index_spec[i-1][0] = (index_spec[i-1][0], value)
            else:
                raise KGTKException('illegal index spec syntax')
    for token, toktype in index_spec:
        if toktype in ('text', 'type', 'option', 'global-option'):
            tokens.append((token, toktype))
    return tokens

def get_index_spec_type(index_spec):
    """Return 'index_spec's type if it starts with one, otherwise return None.
    This will also return None for some syntatically incorrect specs, but these
    errors should be caught during full parsing of the spec.
    """
    seppos = index_spec.find(INDEX_SPEC_TYPE_SEPARATOR)
    if seppos >= 0:
        tokens = tokenize_expression(index_spec[0:seppos+1])
        if len(tokens) == 2 and tokens[0][1] == 'text' and tokens[1][1] == 'typesep':
            return tokens[0][0]
    return None

def parse_index_spec(index_spec, regex=INDEX_TOKENIZER_REGEX):
    """Parse 'index_spec' (a string or tokenized list) into an initial sdict representation.
    Local and global option values are parsed and appropriately assigned.  Index-specific
    'parse_spec' methods can do any further normalizations if necessary.
    """
    tokens = tokenize_index_spec(index_spec, regex=regex)
    parse = sdict['type': None, 'columns': sdict(), 'options': {}]
    column_options = None
    for (token, toktype) in tokens:
        if toktype == 'text':
            column_options = {}
            parse.columns[token] = column_options
        elif toktype in ('option', 'global-option'):
            opt, value = (token, True) if isinstance(token, str) else token
            try:
                import ast
                value = ast.literal_eval(value) # dwim booleans and numbers
            except:
                pass                            # everything else is considered a string
            if toktype == 'global-option':
                parse.options[opt] = value
            elif column_options is not None:
                column_options[opt] = value
            else:
                raise KGTKException('illegal index spec syntax')
        elif toktype == 'type':
            if parse.type is None and len(parse.columns) == 0 and len(parse.options) == 0:
                parse.type = token
            else:
                raise KGTKException('illegal index spec syntax')
        else:
            raise KGTKException('index spec parsing error')
    return parse


class TableIndex(object):
    """Represents objects to describe and manipulate database table indexes (aka indices).
    """

    def __init__(self, table, index_spec):
        """Create an index object for 'table' based on 'index_spec' which can be
        represented as an sdict object, string version of an sdict object, or valid
        and parsable index_spec short form (.e.g., 'index: node1, node2').
        """
        self.table = table
        self.index = index_spec
        self.index = self.get_index()

    def __repr__(self):
        """Create an eval-able repr that will recreate 'self' identically.
        """
        return f"{type(self).__name__}({repr(self.table)}, {self.index})"

    def __eq__(self, other):
        return (type(self) == type(other)
                and self.index == other.index
                and self.get_table_name() == other.get_table_name())

    @classmethod
    def encode(self, index_tree):
        """Return a string encoding of 'index_tree' that can be stored to the DB.
        """
        return repr(index_tree)

    @classmethod
    def decode(self, index_expr):
        """Convert 'index_expr' (a string encoding of an index tree created by 'encode')
        back into the corresponding index object(s).
        """
        return eval(index_expr)

    def get_index(self):
        """Return the parsed index for 'self'.
        """
        index = self.index
        if isinstance(index, sdict):
            pass
        elif isinstance(index, str):
            if index.startswith('sdict['):
                index = eval(index)
            else:
                index = self.parse_spec(index)
        else:
            raise KGTKException(f'illegal index spec: {index}')
        self.index = index
        if type(self).__name__ != self.INDEX_TYPES.get(index.type):
            # minor hackery to instantiate to the right class depending on the index spec:
            if index.type not in self.INDEX_TYPES:
                raise KGTKException(f'unsupported index spec type: {index.type}')
            klass = eval(self.INDEX_TYPES[index.type])
            # change-class (pretend we're in Lisp):
            self.__class__ = klass
        return index

    INDEX_TYPES = {'index': 'StandardIndex', 'text': 'TextIndex', 'sql': 'SqlIndex', 'vector': 'VectorIndex'}
    DEFAULT_INDEX_TYPE = 'index'

    def get_index_type_name(self):
        return next(k for k,v in self.INDEX_TYPES.items() if v == self.__class__.__name__)

    @classmethod
    def get_index_type_class(self, index_type):
        class_name = self.INDEX_TYPES.get(index_type)
        if class_name is None:
            raise KGTKException(f'unsupported index spec type: {index_type}')
        else:
            return eval(class_name)

    def parse_spec(self, index_spec):
        """Parse a short-form string 'index_spec' and return the result as an sdict.
        This simply dispatches to the appropriate index subclasses.
        """
        spec_type = get_index_spec_type(index_spec) or self.DEFAULT_INDEX_TYPE
        klass = self.get_index_type_class(spec_type)
        return klass(self.table, index_spec).index

    def get_table_name(self):
        if hasattr(self.table, '_name_'):
            return self.table._name_
        elif isinstance(self.table, str):
            return self.table
        else:
            raise KGTKException('illegal table type')

    def get_name(self):
        """Return the SQL name to be used for this index
        """
        raise KGTKException('not implemented')

    def get_create_script(self):
        """Return a list of SQL statements required to create this index.
        """
        raise KGTKException('not implemented')

    def get_drop_script(self):
        """Return a list of SQL statements required to delete this index.
        """
        raise KGTKException('not implemented')

    def has_primary_column(self, column):
        """Return True if this index has 'column' as its first indexed column.
        """
        for key in self.index.columns.keys():
            return key == column

    def subsumes_columns(self, columns):
        """Return True if 'columns' are a prefix of this index's columns,
        that is, it might handle a superset of lookup requests.  Note that
        this does not consider the type of index or any options such as 'unique',
        so actual subsumption is determined only by the respective 'subsumes'.
        """
        index_columns = self.index.columns.keys()
        columns = [columns] if isinstance(columns, str) else columns
        for idx_column, column in zip(index_columns, columns):
            if idx_column != column:
                return False
        return len(columns) <= len(index_columns)

    def subsumes(self, index):
        """Return True if 'self' subsumes or is more general than 'index',
        that is it can handle a superset of lookup requests.
        This does not (yet) consider any options such as 'unique'.
        """
        return self.table == index.table and self.subsumes_columns(index.index.columns.keys())

    def redefines(self, index):
        """Return True if 'self' is different from 'index' and redefines it.
        """
        return False

    
class StandardIndex(TableIndex):
    """Standard column indexes created via 'CREATE INDEX...'.
    """

    def parse_spec(self, index_spec):
        """Parse a standard table 'index_spec' such as, for example:
        'index: node1, label, node2 //unique' or 'node1, label, node2' 
        ('index' is the default index spec type if not supplied).
        """
        parse = parse_index_spec(index_spec)
        type_name = self.get_index_type_name()
        if parse.type is None:
            parse.type = type_name
        if parse.type != type_name:
            raise KGTKException(f'mismatched index spec type: {parse.type}')
        return parse

    def get_name(self):
        """Return the global SQL name to be used for this index.
        """
        table_name = self.get_table_name()
        column_names = '_'.join(self.index.columns.keys())
        index_name = '%s_%s_idx' % (table_name, column_names)
        return index_name

    def get_create_script(self):
        """Return a list of SQL statements required to create this index.
        """
        table_name = self.get_table_name()
        index_name = self.get_name()
        options = self.index.options
        columns = self.index.columns
        column_names = list(columns.keys())
        unique = 'UNIQUE ' if options.get('unique', False) or columns[column_names[0]].get('unique', False) else ''
        column_names = ', '.join([sql_quote_ident(col) for col in column_names])
        statements = [
            f'CREATE {unique}INDEX {sql_quote_ident(index_name)} ON {sql_quote_ident(table_name)} ({column_names})',
            # do this unconditionally for now, given that it only takes about 10% of index creation time:
            f'ANALYZE {sql_quote_ident(index_name)}',
        ]
        return statements

    def get_drop_script(self):
        """Return a list of SQL statements required to delete this index.
        """
        statements = [
            f'DROP INDEX {sql_quote_ident(self.get_name())}'
        ]
        return statements

    def subsumes(self, index):
        """Return True if 'self' subsumes or is more general than 'index',
        that is it can handle a superset of lookup requests.
        This does not (yet) consider any options such as 'unique'.
        """
        return (self.table == index.table
                and isinstance(index, (StandardIndex, SqlIndex))
                and self.subsumes_columns(index.index.columns.keys()))


# TextIndex NOTES:
# - all columns will be indexed unless excluded with 'unindexed'
# - tables are contentless, since we need to match to the source table via rowid anyway
# - trigram seems to be the most powerful tokenizer, so we use that as the default, however,
#   it uses extra space, and it requires SQLite 3.34.0 which requires Python 3.9 or later
# - we support optional names on indexes, which allows us to easily redefine them and to
#   have multiple indexes on the same source
# - indexing scores are between -20 and 0, if we rerank with pagerank, that needs to be
#   considered, for example, additive weighting with log(pagerank) seems like an option
# - matching on node IDs works too and doesn't require special tokenizer options
# - we should have a //strip or //preproc option to specify a custom preprocessing function

# Index/tokenizer performance tradeoffs:
# - case-insensitive trigram (default): fast textmatch, fast textlike, fast textglob, more space
# - case-sensitive trigram: fast textmatch, fast textglob, no textlike, more space than case-insensitive
# - ascii, unicode61: fast textmatch on whole words, also prefixes if //prefix is specified,
#   no textlike, no textglob, less space
    
class TextIndex(TableIndex):
    """Specialized indexes to support full-text search via SQLite's FT5.
    """

    COLUMN_OPTIONS    = ('unindexed')
    TABLE_OPTIONS     = ('tokenize', 'prefix', 'content', 'columnsize', 'detail', 'name')
    
    DEFAULT_TOKENIZER = 'trigram'
    # not all of these apply to all tokenizers, but we don't model that for now:
    TOKENIZE_OPTIONS  = ('categories', 'tokenchars', 'separators', 'remove_diacritics', 'case_sensitive')
    
    def parse_spec(self, index_spec):
        """Parse a full-text 'index_spec' such as, for example:
        'text:node1/unindexed,node2//name=labidx//prefix=2//tokenize=trigram'
        The 'unindexed' option should be rare and is just shown for illustration.
        """
        parse = parse_index_spec(index_spec)
        if parse.type != self.get_index_type_name():
            raise KGTKException(f'mismatched index spec type: {parse.type}')
        for key in parse.options.keys():
            if not (key in self.TABLE_OPTIONS or key in self.TOKENIZE_OPTIONS):
                raise KGTKException(f'unhandled text index option: {key}')
        if 'tokenize' not in parse.options:
            for subopt in self.TOKENIZE_OPTIONS:
                if parse.options.get(subopt) is not None:
                    raise KGTKException(f'missing tokenize option for {subopt}')
        # use content-less indexes linked to graph by default (override with //content):
        content = parse.options.get('content')
        if not content:    # None, False, ''
            parse.options['content'] = self.get_table_name()
        elif content is True:
            del parse.options['content']
        return parse

    def get_name(self):
        """Return the global SQL name to be used for this index.
        """
        table_name = self.get_table_name()
        index_name = self.index.options.get('name')
        if index_name is None:
            import shortuuid
            # generate a name based on the index itself instead of external state
            # (minor gamble on uniqueness with shortened key):
            index_name = shortuuid.uuid(repr(self)).lower()[0:10] + '_'
        return f'{table_name}_txtidx_{index_name}'

    def get_create_script(self):
        """Return a list of SQL statements required to create this index.
        """
        table_name = self.get_table_name()
        index_name = self.get_name()
        columns = self.index.columns
        column_names = ', '.join([sql_quote_ident(col) for col in columns.keys()])
        column_names_with_options = ', '.join(
            [sql_quote_ident(col) + (' UNINDEXED' if columns[col].get('unindexed', False) else '')
             for col in columns.keys()])
        
        options = self.index.options
        index_options = []
        if 'tokenize' in options:
            tokopt = str(options.get('tokenize'))
            for subopt in self.TOKENIZE_OPTIONS:
                value = options.get(subopt)
                if value is not None:
                    value = str(int(value)) if isinstance(value, bool) else str(value)
                    tokopt += f""" {subopt} {sql_quote_ident(value, "'")}"""
            tokopt = f"""tokenize={sql_quote_ident(tokopt)}"""
            index_options.append(tokopt)
        else:
            tokopt = f"""tokenize={sql_quote_ident(self.DEFAULT_TOKENIZER)}"""
            index_options.append(tokopt)
        if 'prefix' in options:
            index_options.append(f"""prefix={sql_quote_ident(str(options.get('prefix')))}""")
        if 'content' in options:
            index_options.append(f"""content={sql_quote_ident(str(options.get('content')))}""")
        if 'columnsize' in options:
            index_options.append(f"""columnsize={sql_quote_ident(str(options.get('columnsize')))}""")
        if 'detail' in options:
            index_options.append(f"""detail={options.get('detail')}""")
        if index_options:
            column_names_with_options += (', ' + ', '.join(index_options))
        
        statements = [
            f'CREATE VIRTUAL TABLE {sql_quote_ident(index_name)} USING FTS5 ({column_names_with_options})',
            f'INSERT INTO {sql_quote_ident(index_name)} ({column_names}) SELECT {column_names} FROM {table_name}',
        ]
        return statements

    def get_drop_script(self):
        """Return a list of SQL statements required to delete this index.
        """
        statements = [
            f'DROP TABLE {sql_quote_ident(self.get_name())}'
        ]
        return statements

    def subsumes(self, index):
        """Return True if 'self' subsumes or is more general than 'index',
        that is it can handle a superset of lookup requests.
        """
        # for now we require strict equivalence:
        return self == index

    def redefines(self, index):
        """Return True if 'self' is different from 'index' and redefines it.
        Text indexes redefine based on a defined and equal name to another text index.
        """
        return (isinstance(index, TextIndex)
                and self != index
                and self.index.options.get('name') is not None
                and self.index.options['name'] == index.index.options.get('name'))

    
class SqlIndex(TableIndex):
    """Handle SQL CREATE INDEX statements.
    """

    def parse_spec(self, index_spec):
        """Parse an SQL 'index_spec' such as, for example:
        'sql: CREATE UNIQUE INDEX "graph_1_node1_idx" on graph_1 ("node1")'
        This supports the subset of creation statement this module produces.
        """
        tokens = tokenize_expression(index_spec)
        type_name = self.get_index_type_name()
        if get_index_spec_type(index_spec) != type_name:
            raise KGTKException(f'not an SQL index spec: {index_spec}')
        definition = index_spec[index_spec.find(':')+1:].strip()
        parse = sdict['type': type_name, 'columns': sdict(), 'options': {}, 'definition': definition]
        tokens = tokens[2:]
        tokens = list(reversed(tokens))
        try:
            if tokens.pop()[0].upper() != 'CREATE':
                raise Exception()
            token = tokens.pop()[0].upper()
            if token == 'UNIQUE':
                parse.options['unique'] = True
                token = tokens.pop()[0].upper()
            if token != 'INDEX':
                raise Exception()
            # 'IF NOT EXISTS' would go here:
            parse.options['name'] = tokens.pop()[0]
            if tokens.pop()[0].upper() != 'ON':
                raise Exception()
            parse.options['table'] = tokens.pop()[0]
            if tokens.pop()[0] != '(':
                raise Exception()
            column_options = None
            for token, toktype in reversed(tokens):
                tokens.pop()
                if token == ')':
                    break
                if toktype == 'text':
                    if column_options is None:
                        column_options = {}
                        parse.columns[token] = column_options
                    else:
                        # 'COLLATION', 'ASC', 'DESC' would go here:
                        raise Exception()
                elif token == ',' and toktype == 'sep':
                    column_options = None
                else:
                    raise Exception()
            if len(tokens) > 0:
                raise Exception()
        except:
            raise KGTKException(f'illegal or unhandled SQL index spec: {index_spec}')
        if self.table is not None and self.table != parse.options['table']:
            raise KGTKException(f'table in index object does not match index definition')
        return parse

    def get_table_name(self):
        if self.table is None:
            return self.index.options['table']
        else:
            return super().get_table_name()

    def get_name(self):
        """Return the global SQL name to be used for this index.
        """
        return self.index.options['name']

    def get_create_script(self):
        """Return a list of SQL statements required to create this index.
        """
        return [self.index.definition,
                f'ANALYZE {sql_quote_ident(self.get_name())}',
        ]

    def get_drop_script(self):
        """Return a list of SQL statements required to delete this index.
        """
        statements = [
            f'DROP INDEX {sql_quote_ident(self.get_name())}'
        ]
        return statements

    def subsumes(self, index):
        """Return True if 'self' subsumes or is more general than 'index',
        that is it can handle a superset of lookup requests.
        This does not (yet) consider any options such as 'unique'.
        """
        return (self.table == index.table
                and isinstance(index, (SqlIndex, StandardIndex))
                and self.subsumes_columns(index.index.columns.keys()))


class VectorIndex(TableIndex):
    """Specialized indexes needed for numeric vectors.  Since these are not really
    SQL indexes, this abuses the current SQL table-centric model a little bit.
    We should refactor if we stick with this.
    """

    def parse_spec(self, index_spec):
        """Parse a vector table 'index_spec' such as, for example:
        'vector:node2' or 'vector: node2/fmt=auto/nn=faiss,node1;oemb/fmt=numpy'.
        """
        # TO DO:
        # - generalize option definition and checking
        # - support 'node2' as the default column
        parse = parse_index_spec(index_spec)
        type_name = self.get_index_type_name()
        if parse.type is None:
            parse.type = type_name
        if parse.type != type_name:
            raise KGTKException(f'mismatched index spec type: {parse.type}')
        return parse

    def get_name(self):
        """Return the global name to be used for this index (not really used).
        """
        table_name = self.get_table_name()
        index_name = self.index.options.get('name')
        if index_name is None:
            import shortuuid
            # generate a name based on the index itself instead of external state
            # (minor gamble on uniqueness with shortened key):
            index_name = shortuuid.uuid(repr(self)).lower()[0:10] + '_'
        return f'{table_name}_vecidx_{index_name}'

    def get_create_script(self):
        """Return a list of SQL statements required to create this index.
        Since this is not an SQL index, we return the empty list here.
        """
        return []

    def get_drop_script(self):
        """Return a list of SQL statements required to delete this index.
        Since this is not an SQL index, we return the empty list here.
        """
        return []

    def subsumes(self, index):
        """Return True if 'self' subsumes or is more general than 'index',
        that is it can handle a superset of lookup requests.
        """
        return False
    
"""
>>> TableIndex('graph1', 'node1, label, node2')
StandardIndex('graph1', sdict['type': 'index', 'columns': sdict['node1': {}, 'label': {}, 'node2': {}], 'options': {}])
>>> _.get_create_script()
['CREATE INDEX "graph1_node1_label_node2_idx" ON "graph1" ("node1", "label", "node2")',
 'ANALYZE "graph1_node1_label_node2_idx"']

>>> TableIndex('graph2', 'text:node1,node2//tokenize=trigram//case_sensitive//name=myidx')
TextIndex('graph2', sdict['type': 'text', 'columns': sdict['node1': {}, 'node2': {}], 'options': {'tokenize': 'trigram', 'case_sensitive': True, 'name': 'myidx', 'content': 'graph2'}])
>>> _.get_create_script()
['CREATE VIRTUAL TABLE "graph2_txtidx_myidx" USING FTS5 ("node1", "node2", tokenize="trigram case_sensitive \'1\'", content="graph2")', 
 'INSERT INTO "graph2_txtidx_myidx" ("node1", "node2") SELECT "node1", "node2" FROM graph2']

>>> TableIndex('graph_1', 'sql: CREATE UNIQUE INDEX "graph_1_node1_idx" on graph_1 ("node1")')
SqlIndex('graph_1', sdict['type': 'sql', 'columns': sdict['node1': {}], 'options': {'unique': True, 'name': 'graph_1_node1_idx', 'table': 'graph_1'}, 'definition': 'CREATE UNIQUE INDEX "graph_1_node1_idx" on graph_1 ("node1")'])
>>> _.get_create_script()
['CREATE UNIQUE INDEX "graph_1_node1_idx" on graph_1 ("node1")',
 'ANALYZE "graph_1_node1_idx"']

>>> TableIndex('graph2', 'vector: node2/fmt=auto/nn=faiss/store=hd5')
VectorIndex('graph2', sdict['type': 'vector', 'columns': sdict['node2': {'fmt': 'auto', 'nn': 'faiss', 'store': 'hd5'}], 'options': {}])
>>> _.get_create_script()
[]
>>> 
"""
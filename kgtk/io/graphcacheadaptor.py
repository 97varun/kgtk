"""
Connect to a graph cache using the Kypher API.
"""

import attr
from pathlib import Path
import sys
import typing

import kgtk.kypher.api as kapi

@attr.s(slots=True, frozen=False)
class GraphCacheAdaptor:
    graph_cache_path: Path = attr.ib(validator=attr.validators.instance_of(Path)) # for feedback
    api: kapi.KypherApi = attr.ib(validator=attr.validators.instance_of(kapi.KypherApi))
    sql_store = attr.ib() # Problems defining this type.
    table_name: str = attr.ib(validator=attr.validators.instance_of(str))
    column_names: typing.List[str] = attr.ib()

    error_file: typing.TextIO = attr.ib(default=sys.stderr)
    verbose: bool = attr.ib(validator=attr.validators.instance_of(bool), default=False)

    cursor = attr.ib(default=None)

    is_open: bool = attr.ib(validator=attr.validators.instance_of(bool), default=True)


    @classmethod
    def open(cls,
             graph_cache_path: Path,
             file_path: Path,
             log_level: int = 1,
             index_mode: str = 'none',
             max_results: int = 10000,
             max_cache_size: int = 1000,
             error_file: typing.TextIO = sys.stderr,
             verbose: bool = False,
             )->typing.Optional['GraphCacheAdaptor']:

        api: kapi.KypherApi = kapi.KypherApi(graphcache=str(graph_cache_path),
                                             loglevel=log_level,
                                             index=index_mode,
                                             maxresults=max_results,
                                             maxcache=max_cache_size,
                                             )

        # Open the connection to the sqlite3 database file. This will
        # throw a KGTKException if the database file does not exist
        # or cannot be opened.
        sql_store = api.get_sql_store()

        # Check to see if the specified file exists in the database.
        # The result will be None or a dictionary.
        file_info = sql_store.get_file_info(str(file_path))
        if file_info is None:
            api.close()
            if verbose:
                print("Graph cache %s: file %s not found." % (repr(str(graph_cache_path)), repr(str(file_path))), file=error_file, flush=True)
            return None
        if verbose:
            print("Graph cache %s: file %s found." % (repr(str(graph_cache_path)), repr(str(file_path))), file=error_file, flush=True)
                          
        if "graph" not in file_info or file_info["graph"] is None:
            api.close()
            if verbose:
                print("Graph cache %s: table name not found for file %s" % (repr(str(graph_cache_path)), repr(str(file_path))), file=error_file, flush=True)
            return None
        table_name: str = file_info["graph"]

        if verbose:
            print("The table name is %s" % repr(table_name), file=error_file, flush=True)
            
        column_names: typing.List[str] = sql_store.get_table_header(table_name)

        # api.add_input(table_name, name="table", handle=True)

        return cls(graph_cache_path=graph_cache_path,
                   api=api,
                   sql_store=sql_store,
                   table_name=table_name,
                   column_names=column_names,
                   error_file=error_file,
                   verbose=verbose
                   )

    def close(self):
        if self.is_open:
            self.api.close()
            self.is_open = False

    def reader(adapter_self):
        from kgtk.io.kgtkreader import KgtkReader
        class GraphCacheReader(KgtkReader):
            
            def build_query(reader_self)->typing.Tuple[str, typing.List[str]]:
                query_list: typing.List[str] = list()
                parameters: typing.List[str] = list()

                query_list.append("SELECT ")

                idx: int
                col_name: str
                for idx, col_name in enumerate(adapter_self.column_names):
                    if idx == 0:
                        query_list.append(" ")
                    else:
                        query_list.append(", ")
                    query_list.append('"' + col_name + '"')

                query_list.append(" FROM " )
                query_list.append(adapter_self.table_name)

                if reader_self.input_filter is not None and len(reader_self.input_filter) > 0:
                    query_list.append(" WHERE ")
                    col_idx: int
                    col_values: typing.List[str]
                    first: bool = True
                    for col_idx, col_values in reader_self.input_filter.items():
                        if len(col_values) == 0:
                            continue;
                        if first:
                            first = False
                        else:
                            query_list.append(" AND ")
                        query_list.append('"' + adapter_self.column_names[col_idx] + '"')
                        if len(col_values) == 1:
                            query_list.append(" = ?")
                            parameters.append(list(col_values)[0])
                        else:
                            query_list.append(" IN (")
                            col_value: str
                            for idx, col_value in enumerate(sorted(list(col_values))):
                                if idx > 0:
                                    query_list.append(", ")
                                query_list.append("?")
                                parameters.append(col_value)
                            query_list.append(")")

                query: str = "".join(query_list)

                if adapter_self.verbose:
                    print("Query: %s" % repr(query), file=adapter_self.error_file, flush=True)
                    print("Parameters: [%s]" % ", ".join([repr(x) for x in parameters]), file=adapter_self.error_file, flush=True)
                
                return query, parameters

            def get_cursor(reader_self):
                cursor = adapter_self.sql_store.get_conn().cursor()
                query: str
                parameters: typing.List[str]
                query, parameters = reader_self.build_query()
                cursor.execute(query, parameters)
                return cursor


            def nextrow(reader_self)->typing.List[str]:
                if adapter_self.cursor is None:
                    adapter_self.cursor = reader_self.get_cursor()
                row = adapter_self.cursor.fetchone()
                if row is None:
                    adapter_self.close()
                    raise StopIteration
                return row

        return GraphCacheReader
        

def main():
    """Test the graph cache adaptor.
    """
    from argparse import ArgumentParser, Namespace
    import sys

    from kgtk.exceptions import KGTKException

    parser = ArgumentParser()
    parser.add_argument("--graph-cache", dest="graph_cache", type=str,
                        help="The graph cache file.", required=True)
    parser.add_argument("--input-file", dest="input_file", type=str,
                        help="The input file to find in the graph cache.", required=True)

    args: Namespace = parser.parse_args()

    print("The graph cache is %s" % repr(args.graph_cache), flush=True)
    print("The input file is %s" % repr(args.input_file), flush=True)

    try:
        gca: GraphCacheAdaptor = GraphCacheAdaptor.open(graph_cache_path=Path(args.graph_cache),
                                                        file_path=Path(args.input_file),
                                                        )
    except KGTKException as e:
        print("KGTKException: %s" % str(e), file=sys.stderr, flush=True)
        return

    if gca is None:
        print("%s not found in %s" % (repr(args.input_file), repr(args.graph_cache)), file=sys.stderr, flush=True)
        return

    print("The columns are: [%s]" % ", ".join(gca.column_names))
    print("", flush=True)

    gca.close()

if __name__ == "__main__":
    main()

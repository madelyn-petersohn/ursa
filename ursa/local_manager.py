import ray
from . import graph as ug


class Graph_manager(object):
    """
    This object manages all graphs in the system.

    Fields:
    graph_dict -- the dictionary of graphs.
                           The keys for the dictionary are the graph_ids, and
                           the values are the Graph objects.
    """
    def __init__(self):
        """
        The constructor for an Graph_collection object. Initializes some toy
        graphs as an example.
        """
        self.graph_dict = {}
        self._transaction_id = 0

    def update_transaction_id():
        """
        Updates the transaction ID with that of the global graph manager.
        """
        pass

    def create_graph(self, graph_id, new_transaction=True):
        """
        Create an empty graph.

        Keyword arguments:
        graph_id -- the name of the new graph.
        """
        if new_transaction:
            self._transaction_id += 1

        if not graph_id or graph_id == "":
            raise ValueError("Graph must be named something.")
        if graph_id in self.graph_dict:
            raise ValueError("Graph name already exists.")
        self.graph_dict[graph_id] = ug.Graph.remote(self._transaction_id)

    def _create_if_not_exists(self, graph_id):
        if graph_id not in self.graph_dict:
            print("Warning:", str(graph_id),
                  "is not yet in this Graph Collection. Creating...")

            self.create_graph(graph_id, new_transaction=False)

    def insert(self, graph_id, key, node, local_keys=set(), foreign_keys={}):
        """
        Adds data to the graph specified.

        Keyword arguments:
        graph_id -- the unique name of the graph.
        key -- the unique identifier of this data in the graph.
        node -- the data to add to the graph.
        local_keys -- A list of edges within this graph, if any.
        foreign_keys -- A dictionary: {graph id: key}
        """
        self._transaction_id += 1

        if type(foreign_keys) is not dict:
            raise ValueError(
                "Foreign keys must be labeled with a destination graph.")

        self._create_if_not_exists(graph_id)

        self.graph_dict[graph_id].insert.remote(key,
                                                node,
                                                local_keys,
                                                foreign_keys,
                                                self._transaction_id)

        try:
            local_keys = set([local_keys])
        except TypeError:
            local_keys = set(local_keys)

        _add_local_key_back_edges.remote(self._transaction_id,
                                         self.graph_dict[graph_id],
                                         key,
                                         local_keys)

        for other_graph_id in foreign_keys:
            self._create_if_not_exists(other_graph_id)

            _add_foreign_key_back_edges.remote(self._transaction_id,
                                               self.graph_dict[other_graph_id],
                                               key,
                                               graph_id,
                                               foreign_keys[other_graph_id])

    def delete_row(self, graph_id, key):
        """Deletes the user specified row and all associated edges
        """
        self._transaction_id += 1

        self.graph_dict[graph_id].delete.remote(key, self._transaction_id)

    def add_local_keys(self, graph_id, key, *local_keys):
        """Adds one or more local keys to the graph and key provided.
        """
        self._transaction_id += 1
        self.graph_dict[graph_id].add_local_keys.remote(self._transaction_id,
                                                        key,
                                                        *local_keys)

        _add_local_key_back_edges.remote(self._transaction_id,
                                         self.graph_dict[graph_id],
                                         key,
                                         local_keys)

    def add_foreign_keys(self, graph_id, key, other_graph_id, *foreign_keys):
        """Adds one or more foreign keys to the graph and key provided.
        """
        self._transaction_id += 1

        self.graph_dict[graph_id].add_foreign_keys.remote(
            self._transaction_id,
            key,
            other_graph_id,
            *foreign_keys)

        self._create_if_not_exists(other_graph_id)

        _add_foreign_key_back_edges.remote(self._transaction_id,
                                           self.graph_dict[other_graph_id],
                                           key,
                                           graph_id,
                                           foreign_keys)

    def node_exists(self, graph_id, key):
        """
        Determines whether or not a node exists in the graph.

        Keyword arguments:
        graph_id -- the unique name of the graph
        key -- the unique identifier of the node in the graph.

        Returns:
        True if both the graph exists and the node exists in the graph,
        false otherwise
        """
        return graph_id in self.graph_dict and \
            self.graph_dict[graph_id].row_exists.remote(key)

    def select_row(self, graph_id, key=None):
        return ray.get(self.graph_dict[graph_id].select_row.remote(
            self._transaction_id, key))[0]

    def select_local_keys(self, graph_id, key=None):
        return ray.get(self.graph_dict[graph_id].select_local_keys.remote(
            self._transaction_id, key))[0]

    def select_foreign_keys(self, graph_id, key=None):
        return ray.get(self.graph_dict[graph_id].select_foreign_keys.remote(
            self._transaction_id, key))[0]

    def get_graph(self, graph_id):
        """
        Gets the graph requested.

        Keyword arguments:
        graph_id -- the unique name of the graph.

        Returns:
        The Graph object for the graph requested.
        """
        return self.graph_dict[graph_id]


@ray.remote
def _add_local_key_back_edges(transaction_id, graph, key, local_keys):
    """Creates back edges for local keys in a given graph.

    This satisfies our bi-directionality invariant.

    Keyword arguments:
    graph -- the Graph object to add the back edges to.
    key -- the unique identifier of the Node to connect back edges to.
    list_of_foreign_keys -- the list of connections to create back edges for.
    """

    for back_edge_key in local_keys:
        graph.add_local_keys.remote(transaction_id, back_edge_key, key)


@ray.remote
def _add_foreign_key_back_edges(transaction_id, graph, key, graph_id, f_keys):
    """Creates back edges for foreign keys in a given graph.

    This satisfies our bi-directionality invariant.

    Keyword arguments:
    graph -- the Graph object of the other graph for the connections to
                   be added.
    key -- the key to connect the other graph keys to.
    graph_id -- the unique identifier of the graph to connect to.
    f_keys -- the keys in graph to connect to key.
    """
    for back_edge_key in f_keys:
        graph.add_foreign_keys.remote(transaction_id,
                                      back_edge_key,
                                      graph_id,
                                      key)

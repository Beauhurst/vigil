from collections.abc import Callable, Generator, Iterable
from functools import partial
from typing import Required, TypedDict

import rustworkx as rx

from ..conf import DEFAULT_MAX_TOKENS


class NodeData(TypedDict, total=False):
    path: Required[str]
    content: str
    token_estimate: int


def _resolve_path(parts: list[str]) -> str:
    """Join path parts with '__' and strip leading underscores.

    Reconstructs a flattened path from its components, as used in patch filenames.

    Example:
        >>> resolve_path(["", "src", "utils.py"])
        "src__utils.py"
    """
    return "__".join(parts).lstrip("_")


def _node_matches_path(node: NodeData, path: str) -> bool:
    """Check if a node's path matches the given path."""
    return node["path"] == path


def build_patch_tree(
    patches: Iterable[tuple[str, str]], estimate_tokens: Callable[[str], int]
) -> rx.PyDiGraph[NodeData, None]:
    """Build a hierarchical tree from patch filenames for token-aware grouping.

    Patch filenames use '__' as path separators (e.g. "src__utils__helpers.py.patch").
    This function reconstructs the directory hierarchy as a tree, aggregating token
    counts at each level so we can later find subtrees that fit within token limits.

    The `estimate_tokens` callable is injected to allow different tokenisation
    strategies (e.g. for testing or different models).

    Example:
        >>> patches = [("src__foo.patch", "..."), ("src__bar.patch", "...")]
        >>> tree = build_patch_tree(patches, estimate_tokens=len)
        >>> # root (total tokens)
        >>> # └── src (sum of children)
        >>> #     ├── foo.patch (leaf with content)
        >>> #     └── bar.patch (leaf with content)
    """

    # Create a directed graph to represent the tree
    tree = rx.PyDiGraph()

    # Add root node
    node_data: NodeData = {"path": ""}
    tree.add_node(node_data)

    # Process each patch
    for path, content in patches:
        token_estimate = estimate_tokens(content)

        # Split path by __ to get components, and add root
        path_parts = ["", *path.split("__")]

        # Build tree structure by creating intermediate nodes
        subtree_root_index = None

        while path_parts:
            # Build the current path by joining remaining parts with '__'
            resolved_path = _resolve_path(path_parts)
            # Check if this is the final leaf node (matches original path)

            _node_matches_resolved_path = partial(
                _node_matches_path, path=resolved_path
            )

            if (
                resolved_path == path
            ):  # is this a leaf, add a node with content and tokens
                node_index = tree.add_node(
                    {
                        "path": resolved_path,
                        "token_estimate": token_estimate,
                        "content": content,
                    }
                )

            elif filtered_nodes := tree.filter_nodes(_node_matches_resolved_path):
                node_index = filtered_nodes[0]
                # update token count, adding current tokens
                tree[node_index] = {
                    **tree[node_index],
                    "token_estimate": tree[node_index].get("token_estimate", 0)
                    + token_estimate,
                }
            else:  # intermediate node does not exist, add it
                node_index = tree.add_node(
                    {"path": resolved_path, "token_estimate": token_estimate}
                )

            if subtree_root_index and not tree.has_edge(node_index, subtree_root_index):
                # if subtree exists and it hasn't already been connected to this node,
                # add the connection
                tree.add_edge(node_index, subtree_root_index, None)

            # Track this node as the new subtree root for the next iteration
            subtree_root_index = node_index
            # Move up the tree by removing the most specific path component
            path_parts.pop()

    return tree


def find_subtrees_with_max_tokens(
    tree: rx.PyDiGraph[NodeData, None],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    from_node: int = 0,
) -> Generator[int]:
    """Yield node indices for the largest subtrees that fit within the token limit.

    Walks the tree top-down: if a node's total tokens fit, yield it; otherwise
    recurse into its children. This gives us the coarsest grouping possible
    whilst respecting the limit — we prefer fewer, larger chunks over many small ones.
    """
    children = [edge[1] for edge in tree.out_edges(from_node)]

    if tree[from_node]["token_estimate"] < max_tokens or not children:
        yield from_node
    else:
        for child_node_index in children:
            yield from find_subtrees_with_max_tokens(
                tree, max_tokens=max_tokens, from_node=child_node_index
            )


def _get_node_display_name(path: str) -> str:
    """Extract the display name for a node from its path."""
    if path == "":
        return "root"
    elif "__" in path:
        return path.split("__")[-1]
    else:
        return path


def _format_node_ascii(
    tree: rx.PyDiGraph[NodeData, None],
    *,
    max_depth: int,
    starting_node_index: int,
    node_index: int = 0,
    prefix: str = "",
    is_last: bool = True,
    depth: int = 0,
) -> Generator[str]:
    """Yield ASCII-formatted lines for a node and its descendants.

    Handles the recursion state (prefix, depth, connector characters) that
    `format_tree_ascii` doesn't expose to callers.
    """
    node_data = tree[node_index]
    path = node_data.get("path", "")
    token_estimate = node_data.get("token_estimate")

    is_root = node_index == starting_node_index

    # Get children
    children = [edge[1] for edge in tree.out_edges(node_index)]
    format_next_depth = depth < max_depth

    # Format current node
    if is_root:
        connector = ""
    elif is_last:
        connector = "└── "
    else:
        connector = "├── "

    node_name = _get_node_display_name(path)
    truncated = "..." if (not format_next_depth and children) else ""

    yield f"{prefix}{connector}{node_name}:{token_estimate}{truncated}"

    if format_next_depth:
        for i, child_index in enumerate(children):
            is_child_last = i == len(children) - 1

            if is_root:
                child_prefix = prefix
            elif is_last:
                child_prefix = prefix + "    "
            else:
                child_prefix = prefix + "│   "

            yield from _format_node_ascii(
                tree,
                max_depth=max_depth,
                starting_node_index=starting_node_index,
                node_index=child_index,
                prefix=child_prefix,
                is_last=is_child_last,
                depth=depth + 1,
            )


def format_tree_ascii(
    tree: rx.PyDiGraph[NodeData, None],
    *,
    max_depth: int = 3,
    starting_node_index: int = 0,
) -> str:
    """Render the patch tree as ASCII art for debugging and visualisation.

    Example:
        >>> tree = build_patch_tree([("src__main.py", "x" * 800)], estimate_tokens=len)
        >>> print(format_tree_ascii(tree))
        root:800
        └── src:800
            └── main.py:800
    """
    return "\n".join(
        _format_node_ascii(
            tree, max_depth=max_depth, starting_node_index=starting_node_index
        )
    )


def group_subtrees_into_optimal_fragments(
    tree: rx.PyDiGraph[NodeData, None],
    subtrees: Iterable[int],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Generator[list[int]]:
    """Greedily pack subtrees into groups that fit within the token limit.

    Iterates through subtrees in order, accumulating them into a group until
    adding the next would exceed `max_tokens`, then yields the group and starts
    a new one. Not optimal in the bin-packing sense, but fast and predictable.
    """
    running_group_token_estimate = 0
    running_group: list[int] = []

    for subtree_index in subtrees:
        token_estimate = tree[subtree_index]["token_estimate"]

        # Would adding this subtree exceed the limit?
        if running_group and running_group_token_estimate + token_estimate > max_tokens:
            # Yield current group and start a new one with this subtree
            yield running_group
            running_group = [subtree_index]
            running_group_token_estimate = token_estimate
        else:
            # Still fits, add to current group
            running_group.append(subtree_index)
            running_group_token_estimate += token_estimate

    # Yield any remaining subtrees in the final group
    if running_group:
        yield running_group


def get_subtree_leaf_data(
    tree: rx.PyDiGraph[NodeData, None], *, from_node: int = 0
) -> Generator[NodeData]:
    """Yield leaf nodes (those with content) from a subtree.

    The patch tree has intermediate nodes (path + token_estimate) and leaf nodes
    (also have content). We need the leaves to assemble the actual fragment text.
    """
    if tree[from_node].get("content"):
        yield tree[from_node]
    else:
        yield from [
            patch
            for edge in tree.out_edges(from_node)
            for patch in get_subtree_leaf_data(tree, from_node=edge[1])
        ]

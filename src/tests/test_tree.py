"""
Tests for the tree module.

Verifies tree construction from patches, subtree finding with token limits,
and ASCII formatting.
"""

from vigilia.lib.tree import (
    build_patch_tree,
    find_subtrees_with_max_tokens,
    format_tree_ascii,
    get_subtree_leaf_data,
    group_subtrees_into_optimal_fragments,
)


def test_build_patch_tree_single_file() -> None:
    """A single patch should create root -> file structure."""
    patches = [("foo.py", "content")]
    tree = build_patch_tree(patches, estimate_tokens=len)

    assert tree.num_nodes() == 2
    assert tree[0]["path"] == ""
    assert tree[0]["token_estimate"] == 7

    # Find the leaf node
    leaf_indices = [i for i in tree.node_indices() if tree[i].get("content")]
    assert len(leaf_indices) == 1
    assert tree[leaf_indices[0]]["path"] == "foo.py"
    assert tree[leaf_indices[0]]["content"] == "content"


def test_build_patch_tree_nested_path() -> None:
    """Nested paths should create intermediate nodes."""
    patches = [("src__utils__helpers.py", "x" * 100)]
    tree = build_patch_tree(patches, estimate_tokens=len)

    # root, src, utils, helpers.py
    assert tree.num_nodes() == 4

    paths = {tree[i]["path"] for i in tree.node_indices()}
    assert paths == {"", "src", "src__utils", "src__utils__helpers.py"}


def test_build_patch_tree_shared_prefix() -> None:
    """Files with shared prefixes should share intermediate nodes."""
    patches = [
        ("src__foo.py", "aaa"),
        ("src__bar.py", "bbbbb"),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    # root, src, foo.py, bar.py
    assert tree.num_nodes() == 4

    # src node should have combined token count
    src_indices = [i for i in tree.node_indices() if tree[i]["path"] == "src"]
    assert len(src_indices) == 1
    assert tree[src_indices[0]]["token_estimate"] == 8  # 3 + 5


def test_build_patch_tree_token_aggregation() -> None:
    """Token estimates should aggregate up the tree."""
    patches = [
        ("a__b__c.py", "x" * 10),
        ("a__b__d.py", "y" * 20),
        ("a__e.py", "z" * 5),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    root_data = tree[0]
    assert root_data["path"] == ""
    assert root_data["token_estimate"] == 35  # 10 + 20 + 5

    # Find 'a' node
    a_indices = [i for i in tree.node_indices() if tree[i]["path"] == "a"]
    assert tree[a_indices[0]]["token_estimate"] == 35

    # Find 'a__b' node
    ab_indices = [i for i in tree.node_indices() if tree[i]["path"] == "a__b"]
    assert tree[ab_indices[0]]["token_estimate"] == 30  # 10 + 20


def test_find_subtrees_whole_tree_fits() -> None:
    """When the whole tree fits, yield just the root."""
    patches = [("foo.py", "x" * 10)]
    tree = build_patch_tree(patches, estimate_tokens=len)

    subtrees = list(find_subtrees_with_max_tokens(tree, max_tokens=100))
    assert subtrees == [0]


def test_find_subtrees_splits_at_limit() -> None:
    """When root exceeds limit, yield children that fit."""
    patches = [
        ("a__x.py", "a" * 50),
        ("b__y.py", "b" * 50),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    # Root has 100 tokens, limit is 60, so should split
    subtrees = list(find_subtrees_with_max_tokens(tree, max_tokens=60))

    # Should yield the 'a' and 'b' subtrees
    assert len(subtrees) == 2
    subtree_paths = {tree[i]["path"] for i in subtrees}
    assert subtree_paths == {"a", "b"}


def test_find_subtrees_nodes_over_limit() -> None:
    """When a node exceeds the limit but has no children, yield it anyway."""
    patches = [
        ("a__big.py", "x" * 200),
        ("b__small.py", "y" * 10),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    # Limit of 50: 'a' subtree (200 tokens) exceeds it, but 'a__big.py' is a leaf
    # so it must be yielded regardless. 'b' subtree (10 tokens) fits easily.
    subtrees = list(find_subtrees_with_max_tokens(tree, max_tokens=50))

    assert len(subtrees) == 2
    subtree_paths = {tree[i]["path"] for i in subtrees}
    assert "a__big.py" in subtree_paths
    assert "b" in subtree_paths


def test_find_subtrees_deep_split() -> None:
    """Should recurse deeply when needed to find fitting subtrees."""
    patches = [
        ("a__b__c.py", "x" * 100),
        ("a__b__d.py", "y" * 100),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    # Limit of 150 means a__b (200 tokens) won't fit, but leaves will
    subtrees = list(find_subtrees_with_max_tokens(tree, max_tokens=150))

    assert len(subtrees) == 2
    subtree_paths = {tree[i]["path"] for i in subtrees}
    assert subtree_paths == {"a__b__c.py", "a__b__d.py"}


def test_find_subtrees_single_oversized_leaf() -> None:
    """A leaf that exceeds the limit should still be yielded."""
    patches = [("huge.py", "x" * 1000)]
    tree = build_patch_tree(patches, estimate_tokens=len)

    subtrees = list(find_subtrees_with_max_tokens(tree, max_tokens=100))

    # Should yield the leaf even though it exceeds limit
    assert len(subtrees) == 1
    assert tree[subtrees[0]]["path"] == "huge.py"


def test_format_tree_ascii_simple() -> None:
    """Basic ASCII formatting should show hierarchy."""
    patches = [("src__main.py", "x" * 100)]
    tree = build_patch_tree(patches, estimate_tokens=len)

    output = format_tree_ascii(tree)

    assert "root:100" in output
    assert "src:100" in output
    assert "main.py:100" in output
    assert "└──" in output or "├──" in output


def test_format_tree_ascii_multiple_children() -> None:
    """Multiple children should be formatted with correct connectors."""
    patches = [
        ("a.py", "x" * 10),
        ("b.py", "y" * 20),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    output = format_tree_ascii(tree)

    assert "root:30" in output
    assert "a.py:10" in output
    assert "b.py:20" in output


def test_format_tree_ascii_max_depth() -> None:
    """Depth limiting should truncate with ellipsis."""
    patches = [("a__b__c__d__e.py", "x" * 10)]
    tree = build_patch_tree(patches, estimate_tokens=len)

    output = format_tree_ascii(tree, max_depth=2)

    assert "root:10" in output
    assert "a:10" in output
    assert "b:10..." in output  # truncated with ellipsis
    assert "c:10" not in output


def test_format_tree_ascii_nested_structure() -> None:
    """Complex nested structures should render correctly."""
    patches = [
        ("src__lib__utils.py", "a" * 10),
        ("src__lib__helpers.py", "b" * 20),
        ("src__main.py", "c" * 5),
        ("tests__test_main.py", "d" * 15),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    output = format_tree_ascii(tree, max_depth=10)

    assert "root:50" in output
    assert "src:35" in output
    assert "lib:30" in output
    assert "utils.py:10" in output
    assert "helpers.py:20" in output
    assert "main.py:5" in output
    assert "tests:15" in output
    assert "test_main.py:15" in output


def test_group_subtrees_single_group() -> None:
    """When all subtrees fit together, yield one group."""
    patches = [
        ("a.py", "x" * 10),
        ("b.py", "y" * 20),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    subtrees = list(find_subtrees_with_max_tokens(tree, max_tokens=100))
    groups = list(group_subtrees_into_optimal_fragments(tree, subtrees, max_tokens=100))

    assert len(groups) == 1
    assert len(groups[0]) == 1  # root node


def test_group_subtrees_multiple_groups() -> None:
    """When subtrees exceed limit together, split into multiple groups."""
    patches = [
        ("a__x.py", "a" * 40),
        ("b__y.py", "b" * 40),
        ("c__z.py", "c" * 40),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    # Each subtree is 40 tokens, limit is 60, so can fit at most one per group
    subtrees = list(find_subtrees_with_max_tokens(tree, max_tokens=60))
    groups = list(group_subtrees_into_optimal_fragments(tree, subtrees, max_tokens=60))

    assert len(groups) == 3
    for group in groups:
        assert len(group) == 1


def test_group_subtrees_greedy_packing() -> None:
    """Subtrees should be greedily packed until limit is reached."""
    patches = [
        ("a__x.py", "a" * 20),
        ("b__y.py", "b" * 20),
        ("c__z.py", "c" * 20),
        ("d__w.py", "d" * 20),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    # Each subtree is 20 tokens, limit is 50, so can fit two per group
    subtrees = list(find_subtrees_with_max_tokens(tree, max_tokens=50))
    groups = list(group_subtrees_into_optimal_fragments(tree, subtrees, max_tokens=50))

    assert len(groups) == 2
    assert len(groups[0]) == 2
    assert len(groups[1]) == 2


def test_group_subtrees_empty_input() -> None:
    """Empty subtree list should yield no groups."""
    patches = [("a.py", "x")]
    tree = build_patch_tree(patches, estimate_tokens=len)

    groups = list(group_subtrees_into_optimal_fragments(tree, [], max_tokens=100))

    assert groups == []


def test_get_subtree_leaf_data_single_leaf() -> None:
    """A leaf node should yield its own data."""
    patches = [("foo.py", "content here")]
    tree = build_patch_tree(patches, estimate_tokens=len)

    # Find the leaf node
    leaf_index = next(i for i in tree.node_indices() if tree[i].get("content"))

    leaves = list(get_subtree_leaf_data(tree, from_node=leaf_index))

    assert len(leaves) == 1
    assert leaves[0]["path"] == "foo.py"
    assert leaves[0]["content"] == "content here"


def test_get_subtree_leaf_data_from_root() -> None:
    """Starting from root should yield all leaves."""
    patches = [
        ("a__x.py", "content a"),
        ("b__y.py", "content b"),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    leaves = list(get_subtree_leaf_data(tree, from_node=0))

    assert len(leaves) == 2
    contents = {leaf["content"] for leaf in leaves}
    assert contents == {"content a", "content b"}


def test_get_subtree_leaf_data_from_intermediate() -> None:
    """Starting from an intermediate node should yield only its descendants."""
    patches = [
        ("src__lib__utils.py", "utils content"),
        ("src__lib__helpers.py", "helpers content"),
        ("src__main.py", "main content"),
        ("tests__test.py", "test content"),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    # Find the 'src__lib' node
    lib_index = next(i for i in tree.node_indices() if tree[i]["path"] == "src__lib")

    leaves = list(get_subtree_leaf_data(tree, from_node=lib_index))

    assert len(leaves) == 2
    contents = {leaf["content"] for leaf in leaves}
    assert contents == {"utils content", "helpers content"}


def test_get_subtree_leaf_data_nested_structure() -> None:
    """Deeply nested structures should yield all leaves correctly."""
    patches = [
        ("a__b__c__d.py", "deep content"),
    ]
    tree = build_patch_tree(patches, estimate_tokens=len)

    leaves = list(get_subtree_leaf_data(tree, from_node=0))

    assert len(leaves) == 1
    assert leaves[0]["content"] == "deep content"
    assert leaves[0]["path"] == "a__b__c__d.py"

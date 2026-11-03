#![cfg(feature = "load-grammars")]

use tree_sitter::{Parser, Query, QueryCursor, StreamingIterator};

const SOURCE: &str = include_str!("fixtures/delphi.pas");

#[test]
fn delphi_project_and_package_syntax_parse_without_errors() {
    let language = tree_sitter_pascal::LANGUAGE.into();
    let mut parser = Parser::new();
    parser.set_language(&language).unwrap();
    for source in [
        include_str!("fixtures/delphi.dpr"),
        include_str!("fixtures/delphi.dpk"),
    ] {
        let tree = parser.parse(source, None).unwrap();
        assert!(
            !tree.root_node().has_error(),
            "{}",
            tree.root_node().to_sexp()
        );
    }
}

#[test]
fn delphi_queries_capture_generic_types_properties_and_methods() {
    let language = tree_sitter_pascal::LANGUAGE.into();
    let mut parser = Parser::new();
    parser.set_language(&language).unwrap();
    let tree = parser.parse(SOURCE, None).unwrap();
    assert!(
        !tree.root_node().has_error(),
        "{}",
        tree.root_node().to_sexp()
    );

    for name in [
        "highlights",
        "outline",
        "brackets",
        "indents",
        "textobjects",
    ] {
        let file = grammars::get_file(&format!("delphi/{name}.scm")).unwrap();
        let source = std::str::from_utf8(file.data.as_ref()).unwrap();
        let query = Query::new(&language, source).unwrap();
        let mut cursor = QueryCursor::new();
        let mut matches = cursor.matches(&query, tree.root_node(), SOURCE.as_bytes());
        let mut captures = Vec::new();
        while let Some(query_match) = matches.next() {
            for capture in query_match.captures() {
                captures.push((
                    query.capture_names()[capture.index as usize],
                    &SOURCE[capture.node.byte_range()],
                ));
            }
        }
        assert!(!captures.is_empty(), "{name} produced no captures");
        if name == "outline" {
            for symbol in ["Demo.Model", "TBox<T>", "Value", "TCounter.Increment"] {
                assert!(captures.contains(&("name", symbol)), "missing {symbol}");
            }
        }
        if name == "highlights" {
            assert!(captures.contains(&("property", "Value")));
            assert!(captures.contains(&("string", "'It''s Delphi'")));
        }
    }
}

#[test]
fn delphi_config_and_native_grammar_agree() {
    let config = grammars::load_config("delphi");
    assert_eq!(config.name.as_ref(), "Delphi");
    let grammar = grammars::native_grammars()
        .into_iter()
        .find(|(name, _)| Some(*name) == config.grammar.as_deref());
    assert!(grammar.is_some());
}

//! Russian display titles, separate from action IDs and persisted English history keys.

use std::{collections::HashMap, sync::LazyLock};

const CATALOGS: &[&str] = &[
    include_str!("action_labels/ru-1.tsv"),
    include_str!("action_labels/ru-2.tsv"),
    include_str!("action_labels/ru-3.tsv"),
    include_str!("action_labels/ru-4.tsv"),
];

static TITLES: LazyLock<HashMap<&'static str, &'static str>> = LazyLock::new(|| {
    CATALOGS
        .iter()
        .flat_map(|catalog| catalog.lines())
        .filter_map(|line| line.split_once('\t'))
        .collect()
});

/// Localizes built-in action presentation; unknown actions keep a readable fallback.
pub fn localized_action_name(name: &str) -> String {
    TITLES
        .get(name)
        .map(|title| (*title).to_owned())
        .unwrap_or_else(|| super::humanize_action_name(name))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_actions_have_russian_titles() {
        assert_eq!(
            localized_action_name("editor::GoToDefinition"),
            "Редактор: перейти к определению"
        );
        assert_eq!(
            localized_action_name("debugger::StepOver"),
            "Отладчик: шаг с обходом"
        );
        assert_eq!(
            localized_action_name("task::Spawn"),
            "Задачи: запустить задачу"
        );
    }

    #[test]
    fn unknown_actions_keep_their_readable_name() {
        assert_eq!(
            localized_action_name("custom::MySpecialCommand"),
            "custom: my special command"
        );
    }

    #[test]
    fn catalog_has_unique_identifiers_and_russian_labels() {
        let mut identifiers = std::collections::HashSet::new();
        for line in CATALOGS.iter().flat_map(|catalog| catalog.lines()) {
            let (identifier, title) = line.split_once('\t').expect("tab-separated catalog entry");
            assert!(
                identifiers.insert(identifier),
                "duplicate action: {identifier}"
            );
            assert!(
                title.chars().any(|letter| ('А'..='я').contains(&letter)),
                "untranslated action: {identifier}"
            );
            assert!(!title.contains('\t'), "invalid action title: {identifier}");
        }
    }
}

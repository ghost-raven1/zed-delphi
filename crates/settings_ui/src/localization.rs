use gpui::SharedString;
use heck::ToTitleCase as _;
use std::{collections::HashMap, sync::OnceLock};

fn catalog() -> &'static HashMap<String, String> {
    static CATALOG: OnceLock<HashMap<String, String>> = OnceLock::new();
    CATALOG.get_or_init(|| {
        serde_json::from_str(include_str!("localization/ru.json")).unwrap_or_else(|error| {
            log::error!("Invalid Russian settings catalog: {error}");
            HashMap::new()
        })
    })
}

/// Translate settings presentation without changing canonical titles or JSON keys.
pub(crate) fn text(source: &str) -> SharedString {
    match catalog().get(source) {
        Some(translated) => SharedString::new_static(translated.as_str()),
        None => source.to_owned().into(),
    }
}

pub(crate) fn static_text(source: &'static str) -> &'static str {
    catalog().get(source).map(String::as_str).unwrap_or(source)
}

/// Translate enum captions while the dropdown retains its original variant index.
pub(crate) fn option_text(source: &str) -> SharedString {
    let translated = match source.to_lowercase().as_str() {
        "on" | "enabled" => "Включено",
        "off" | "disabled" => "Выключено",
        "auto" | "automatic" => "Автоматически",
        "always" => "Всегда",
        "never" => "Никогда",
        "all" => "Все",
        "none" => "Нет",
        "default" => "По умолчанию",
        "system" => "Системная",
        "light" => "Светлая",
        "dark" => "Тёмная",
        "left" => "Слева",
        "right" => "Справа",
        "top" => "Сверху",
        "bottom" => "Снизу",
        "center" => "По центру",
        "start" => "В начале",
        "end" => "В конце",
        "first" => "Первый",
        "last" => "Последний",
        "small" => "Маленький",
        "medium" => "Средний",
        "large" => "Большой",
        "normal" => "Обычный",
        "compact" => "Компактный",
        "comfortable" => "Просторный",
        "manual" => "Вручную",
        "inherit" | "inherited" => "Наследовать",
        "vertical" => "Вертикально",
        "horizontal" => "Горизонтально",
        "open" => "Открыто",
        "closed" => "Закрыто",
        "selection" => "Выделение",
        "line" => "Строка",
        "word" => "Слово",
        "block" => "Блок",
        "smart" => "Умный",
        "relative" => "Относительные",
        "absolute" => "Абсолютные",
        "full" => "Полный",
        _ => {
            let title = source.to_title_case();
            return match catalog().get(source).or_else(|| catalog().get(&title)) {
                Some(translated) => SharedString::new_static(translated.as_str()),
                None => source.to_owned().into(),
            };
        }
    };
    translated.into()
}

/// Index both languages; persisted navigation and links continue using canonical text.
pub(crate) fn search_words(parts: &[&str]) -> Vec<String> {
    let mut words = Vec::new();
    for original in parts {
        let translated = text(original);
        for value in [*original, translated.as_ref()] {
            words.extend(
                value
                    .split(|character: char| !character.is_alphanumeric())
                    .filter(|word| !word.is_empty())
                    .map(str::to_lowercase),
            );
        }
    }
    words
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn russian_search_keeps_english_aliases() {
        let words = search_words(&["Font Size"]);
        assert!(words.iter().any(|word| word == "font"));
        assert!(words.iter().any(|word| word == "шрифта"));
    }

    #[test]
    fn unknown_text_and_identifiers_are_preserved() {
        assert_eq!(
            text("custom/path/File.pas").as_ref(),
            "custom/path/File.pas"
        );
        assert_eq!(text("buffer_font_size").as_ref(), "buffer_font_size");
        assert_eq!(static_text(""), "");
        assert_eq!(option_text("VSCode").as_ref(), "VSCode");
        assert_eq!(option_text("EditorWidth").as_ref(), "По ширине редактора");
    }

    #[test]
    fn catalog_is_valid_and_has_no_empty_translations() {
        let entries: HashMap<String, String> =
            serde_json::from_str(include_str!("localization/ru.json"))
                .expect("settings translations must be valid JSON");
        assert!(!entries.is_empty());
        assert!(
            entries
                .iter()
                .all(|(key, value)| key.is_empty() || !value.is_empty())
        );
    }
}

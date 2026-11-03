use collab_ui::collab_panel;
use gpui::{App, Menu, MenuItem, OsAction};
use project::DisableAiSettings;
use release_channel::ReleaseChannel;
use settings::Settings;
use terminal_view::terminal_panel;
use zed_actions::{Quit, assistant, debug_panel, dev, git_panel, project_panel};

pub fn app_menus(cx: &mut App) -> Vec<Menu> {
    let mut view_items = vec![
        MenuItem::action(
            "Увеличить масштаб",
            zed_actions::IncreaseBufferFontSize { persist: false },
        ),
        MenuItem::action(
            "Уменьшить масштаб",
            zed_actions::DecreaseBufferFontSize { persist: false },
        ),
        MenuItem::action(
            "Сбросить масштаб",
            zed_actions::ResetBufferFontSize { persist: false },
        ),
        MenuItem::action(
            "Сбросить весь масштаб",
            zed_actions::ResetAllZoom { persist: false },
        ),
        MenuItem::separator(),
        MenuItem::action(
            "Показать или скрыть левую панель",
            workspace::ToggleLeftDock,
        ),
        MenuItem::action(
            "Показать или скрыть правую панель",
            workspace::ToggleRightDock,
        ),
        MenuItem::action(
            "Показать или скрыть нижнюю панель",
            workspace::ToggleBottomDock,
        ),
        MenuItem::action("Показать или скрыть все панели", workspace::ToggleAllDocks),
        MenuItem::submenu(Menu {
            name: "Editor Layout".into(),
            display_name: Some("Расположение редакторов".into()),
            disabled: false,
            items: vec![
                MenuItem::action("Разделить сверху", workspace::SplitUp::default()),
                MenuItem::action("Разделить снизу", workspace::SplitDown::default()),
                MenuItem::action("Разделить слева", workspace::SplitLeft::default()),
                MenuItem::action("Разделить справа", workspace::SplitRight::default()),
            ],
        }),
        MenuItem::separator(),
        MenuItem::action("Панель проекта", project_panel::ToggleFocus),
        MenuItem::action("Структура кода", outline_panel::ToggleFocus),
        MenuItem::action("Совместная работа", collab_panel::ToggleFocus),
        MenuItem::action("Терминал", terminal_panel::Toggle),
        MenuItem::action("Отладчик", debug_panel::ToggleFocus),
    ];

    if !DisableAiSettings::get_global(cx).disable_ai {
        view_items.push(MenuItem::action("Панель агента", assistant::ToggleFocus));
    }

    view_items.extend([
        MenuItem::action("Панель Git", git_panel::ToggleFocus),
        MenuItem::separator(),
        MenuItem::action("Диагностика", diagnostics::Deploy),
        MenuItem::separator(),
    ]);

    if ReleaseChannel::try_global(cx) == Some(ReleaseChannel::Dev) {
        view_items.push(MenuItem::action(
            "Показать или скрыть инспектор GPUI",
            dev::ToggleInspector,
        ));
        view_items.push(MenuItem::separator());
    }

    vec![
        Menu {
            name: "Zed".into(),
            display_name: Some("Zed".into()),
            disabled: false,
            items: vec![
                MenuItem::action("О Zed", zed_actions::About),
                MenuItem::action("Проверить обновления", auto_update::Check),
                MenuItem::separator(),
                MenuItem::submenu(Menu::new("Settings").display_name("Настройки").items([
                    MenuItem::action("Открыть настройки", zed_actions::OpenSettings),
                    MenuItem::action("Открыть файл настроек", super::OpenSettingsFile),
                    MenuItem::action(
                        "Открыть настройки проекта",
                        zed_actions::OpenProjectSettings,
                    ),
                    MenuItem::action(
                        "Открыть файл настроек проекта",
                        super::OpenProjectSettingsFile,
                    ),
                    MenuItem::action("Открыть стандартные настройки", super::OpenDefaultSettings),
                    MenuItem::separator(),
                    MenuItem::action("Сочетания клавиш", zed_actions::OpenKeymap),
                    MenuItem::action("Открыть файл сочетаний клавиш", zed_actions::OpenKeymapFile),
                    MenuItem::action(
                        "Стандартные сочетания клавиш",
                        zed_actions::OpenDefaultKeymap,
                    ),
                    MenuItem::separator(),
                    MenuItem::action(
                        "Выбрать тему…",
                        zed_actions::theme_selector::Toggle::default(),
                    ),
                    MenuItem::action(
                        "Выбрать тему значков…",
                        zed_actions::icon_theme_selector::Toggle::default(),
                    ),
                ])),
                MenuItem::separator(),
                #[cfg(target_os = "macos")]
                MenuItem::os_submenu("Службы", gpui::SystemMenuType::Services),
                MenuItem::separator(),
                MenuItem::action("Расширения", zed_actions::Extensions::default()),
                #[cfg(not(target_os = "windows"))]
                MenuItem::action("Установить команду zed", install_cli::InstallCliBinary),
                MenuItem::separator(),
                #[cfg(target_os = "macos")]
                MenuItem::action("Скрыть Zed", super::Hide),
                #[cfg(target_os = "macos")]
                MenuItem::action("Скрыть остальные", super::HideOthers),
                #[cfg(target_os = "macos")]
                MenuItem::action("Показать все", super::ShowAll),
                MenuItem::separator(),
                MenuItem::action("Выйти из Zed", Quit),
            ],
        },
        Menu {
            name: "File".into(),
            display_name: Some("Файл".into()),
            disabled: false,
            items: vec![
                MenuItem::action("Новый файл", workspace::NewFile),
                MenuItem::action("Новое окно", workspace::NewWindow),
                MenuItem::separator(),
                #[cfg(not(target_os = "macos"))]
                MenuItem::action("Открыть файл…", workspace::OpenFiles),
                MenuItem::action(
                    if cfg!(not(target_os = "macos")) {
                        "Открыть папку…"
                    } else {
                        "Открыть…"
                    },
                    workspace::Open::default(),
                ),
                MenuItem::action("Недавние проекты…", zed_actions::OpenRecent::default()),
                MenuItem::action("Удалённый проект…", zed_actions::OpenRemote::default()),
                MenuItem::separator(),
                MenuItem::action("Добавить папку в проект…", workspace::AddFolderToProject),
                MenuItem::separator(),
                MenuItem::action("Сохранить", workspace::Save { save_intent: None }),
                MenuItem::action("Сохранить как…", workspace::SaveAs),
                MenuItem::action("Сохранить всё", workspace::SaveAll { save_intent: None }),
                MenuItem::separator(),
                MenuItem::action(
                    "Закрыть редактор",
                    workspace::CloseActiveItem {
                        save_intent: None,
                        close_pinned: true,
                    },
                ),
                MenuItem::action("Закрыть проект", workspace::CloseProject),
                MenuItem::action("Закрыть окно", workspace::CloseWindow),
            ],
        },
        Menu {
            name: "Edit".into(),
            display_name: Some("Правка".into()),
            disabled: false,
            items: vec![
                MenuItem::os_action("Отменить", editor::actions::Undo, OsAction::Undo),
                MenuItem::os_action("Повторить", editor::actions::Redo, OsAction::Redo),
                MenuItem::separator(),
                MenuItem::os_action("Вырезать", editor::actions::Cut, OsAction::Cut),
                MenuItem::os_action("Копировать", editor::actions::Copy, OsAction::Copy),
                MenuItem::action(
                    "Копировать без крайних пробелов",
                    editor::actions::CopyAndTrim,
                ),
                MenuItem::os_action("Вставить", editor::actions::Paste, OsAction::Paste),
                MenuItem::separator(),
                MenuItem::action("Найти", search::buffer_search::Deploy::find()),
                MenuItem::action("Найти в проекте", workspace::DeploySearch::default()),
                MenuItem::separator(),
                MenuItem::action(
                    "Закомментировать или раскомментировать строку",
                    editor::actions::ToggleComments::default(),
                ),
            ],
        },
        Menu {
            name: "Selection".into(),
            display_name: Some("Выделение".into()),
            disabled: false,
            items: vec![
                MenuItem::os_action(
                    "Выделить всё",
                    editor::actions::SelectAll,
                    OsAction::SelectAll,
                ),
                MenuItem::action(
                    "Расширить выделение",
                    editor::actions::SelectLargerSyntaxNode,
                ),
                MenuItem::action("Сузить выделение", editor::actions::SelectSmallerSyntaxNode),
                MenuItem::action(
                    "Выделить следующий элемент",
                    editor::actions::SelectNextSyntaxNode,
                ),
                MenuItem::action(
                    "Выделить предыдущий элемент",
                    editor::actions::SelectPreviousSyntaxNode,
                ),
                MenuItem::separator(),
                MenuItem::action(
                    "Добавить курсор выше",
                    editor::actions::AddSelectionAbove {
                        skip_soft_wrap: true,
                    },
                ),
                MenuItem::action(
                    "Добавить курсор ниже",
                    editor::actions::AddSelectionBelow {
                        skip_soft_wrap: true,
                    },
                ),
                MenuItem::action(
                    "Выделить следующее совпадение",
                    editor::actions::SelectNext {
                        replace_newest: false,
                    },
                ),
                MenuItem::action(
                    "Выделить предыдущее совпадение",
                    editor::actions::SelectPrevious {
                        replace_newest: false,
                    },
                ),
                MenuItem::action("Выделить все совпадения", editor::actions::SelectAllMatches),
                MenuItem::separator(),
                MenuItem::action("Переместить строку вверх", editor::actions::MoveLineUp),
                MenuItem::action("Переместить строку вниз", editor::actions::MoveLineDown),
                MenuItem::action("Дублировать выделение", editor::actions::DuplicateLineDown),
            ],
        },
        Menu {
            name: "View".into(),
            display_name: Some("Вид".into()),
            disabled: false,
            items: view_items,
        },
        Menu {
            name: "Go".into(),
            display_name: Some("Переход".into()),
            disabled: false,
            items: vec![
                MenuItem::action("Назад", workspace::GoBack),
                MenuItem::action("Вперёд", workspace::GoForward),
                MenuItem::separator(),
                MenuItem::action("Палитра команд…", zed_actions::command_palette::Toggle),
                MenuItem::separator(),
                MenuItem::action("Перейти к файлу…", workspace::ToggleFileFinder::default()),
                // MenuItem::action("Перейти к символу в проекте", project_symbols::Toggle),
                MenuItem::action(
                    "Перейти к символу в редакторе…",
                    zed_actions::outline::ToggleOutline,
                ),
                MenuItem::action(
                    "Перейти к строке или столбцу…",
                    editor::actions::ToggleGoToLine,
                ),
                MenuItem::separator(),
                MenuItem::action(
                    "Перейти к определению",
                    editor::actions::GoToDefinition::default(),
                ),
                MenuItem::action(
                    "Перейти к объявлению",
                    editor::actions::GoToDeclaration::default(),
                ),
                MenuItem::action(
                    "Перейти к определению типа",
                    editor::actions::GoToTypeDefinition::default(),
                ),
                MenuItem::action(
                    "Найти все ссылки",
                    editor::actions::FindAllReferences::default(),
                ),
                MenuItem::action(
                    "Показать входящие вызовы",
                    call_hierarchy::ShowIncomingCalls,
                ),
                MenuItem::action(
                    "Показать исходящие вызовы",
                    call_hierarchy::ShowOutgoingCalls,
                ),
                MenuItem::separator(),
                MenuItem::action(
                    "Следующая проблема",
                    editor::actions::GoToDiagnostic::default(),
                ),
                MenuItem::action(
                    "Предыдущая проблема",
                    editor::actions::GoToPreviousDiagnostic::default(),
                ),
            ],
        },
        Menu {
            name: "Run".into(),
            display_name: Some("Запуск".into()),
            disabled: false,
            items: vec![
                MenuItem::action(
                    "Запустить задачу",
                    zed_actions::Spawn::ViaModal {
                        reveal_target: None,
                    },
                ),
                MenuItem::action("Начать отладку", debugger_ui::Start),
                MenuItem::separator(),
                MenuItem::action("Изменить tasks.json…", zed_actions::OpenProjectTasks),
                MenuItem::action("Изменить debug.json…", zed_actions::OpenProjectDebugTasks),
                MenuItem::separator(),
                MenuItem::action("Продолжить", debugger_ui::Continue),
                MenuItem::action("Шаг с обходом", debugger_ui::StepOver),
                MenuItem::action("Шаг с заходом", debugger_ui::StepInto),
                MenuItem::action("Выйти из функции", debugger_ui::StepOut),
                MenuItem::separator(),
                MenuItem::action(
                    "Установить или убрать точку останова",
                    editor::actions::ToggleBreakpoint,
                ),
                MenuItem::action(
                    "Изменить точку останова",
                    editor::actions::EditLogBreakpoint,
                ),
                MenuItem::action(
                    "Удалить все точки останова",
                    debugger_ui::ClearAllBreakpoints,
                ),
            ],
        },
        Menu {
            name: "Window".into(),
            display_name: Some("Окно".into()),
            disabled: false,
            items: vec![
                MenuItem::action("Свернуть", super::Minimize),
                MenuItem::action("Развернуть", super::Zoom),
                MenuItem::separator(),
            ],
        },
        Menu {
            name: "Help".into(),
            display_name: Some("Справка".into()),
            disabled: false,
            items: vec![
                MenuItem::action(
                    "Открыть описание выпуска",
                    auto_update_ui::ViewReleaseNotesLocally,
                ),
                MenuItem::action(
                    "Просмотреть журнал телеметрии",
                    zed_actions::OpenTelemetryLog,
                ),
                MenuItem::action("Лицензии зависимостей", zed_actions::OpenLicenses),
                MenuItem::action("Открыть начальный экран", onboarding::ShowWelcome),
                MenuItem::separator(),
                MenuItem::action("Сообщить об ошибке…", zed_actions::feedback::FileBugReport),
                MenuItem::action("Предложить функцию…", zed_actions::feedback::RequestFeature),
                MenuItem::action("Написать разработчикам…", zed_actions::feedback::EmailZed),
                MenuItem::separator(),
                MenuItem::action(
                    "Документация",
                    super::OpenBrowser {
                        url: "https://zed.dev/docs".into(),
                    },
                ),
                MenuItem::action("Репозиторий Zed", feedback::OpenZedRepo),
                MenuItem::action(
                    "Zed в Twitter",
                    super::OpenBrowser {
                        url: "https://twitter.com/zeddotdev".into(),
                    },
                ),
                MenuItem::action(
                    "Присоединиться к команде",
                    super::OpenBrowser {
                        url: "https://zed.dev/jobs".into(),
                    },
                ),
            ],
        },
    ]
}
